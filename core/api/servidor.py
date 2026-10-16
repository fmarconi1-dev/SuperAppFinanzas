"""Servidor HTTP de la API (stdlib): rutas, autenticación y la cola de trabajo.

Escucha en ``127.0.0.1:8000``; nginx le pasa todo lo que empieza con
``/api/``. Rutas:

    GET  /api/health      → 200 {"ok": true}
    GET  /api/whatsapp    → verificación de la suscripción de Meta (hub.challenge)
    POST /api/whatsapp    → mensajes entrantes, firmados por Meta
    GET  /api/privacidad  → política de privacidad (Meta la pide para el modo Live)
    POST /api/briefing    → briefings de Gemini (Fase B), con Bearer SUPERAPP_API_TOKEN

**Flujo de un mensaje** (el orden importa):

1. Se verifica la firma sobre el cuerpo crudo. Si no coincide → 401.
2. Remitente distinto del autorizado → se ignora (se loguea enmascarado).
3. Dedupe: ``INSERT OR IGNORE`` del wamid. Meta reintenta hasta 7 días si no
   recibe 200 a tiempo, y un arranque en frío de Fly alcanza para eso.
4. Se responde 200 **enseguida** y el mensaje va a una cola con **un solo**
   hilo trabajador: los mensajes se procesan en orden (un "sí" nunca se
   adelanta al gasto que confirma) y sin dos escrituras compitiendo.
5. Si el procesamiento falla, la fila queda en ``resultado='error'`` y se le
   avisa a Franco por WhatsApp. El dedupe no puede convertir un fallo en
   silencio.

**Cola de salida (Fase B):** lo que el bot manda por su cuenta (los
briefings) solo es gratis dentro de la ventana de 24 h desde el último mensaje
de Franco. Si la ventana está abierta sale en el momento; si no, queda en
``whatsapp_salientes`` y sale apenas Franco escribe, antes de contestarle.
No hay un camino pago (ADR-0008).

`core/` no importa `places/`: la lógica de los comandos y del briefing llega
inyectada (`procesar`, `componer`), y quien la conecta es `api.py`.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import queue
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

from core.api import whatsapp_meta as wa
from core.context import set_current_workspace_id
from core.db import connect

log = logging.getLogger("superapp.api")

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
#: Un webhook de Meta pesa unos pocos KB; esto corta cualquier abuso.
MAX_CUERPO = 1_000_000

PRIVACIDAD_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Política de privacidad — SuperApp</title></head>
<body style="font-family:sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem;line-height:1.5">
<h1>Política de privacidad</h1>
<p>Esta aplicación es de uso personal. Su único usuario es su dueño.</p>
<p>Los mensajes de WhatsApp que recibe vienen solo del número autorizado por el
dueño. Se usan para registrar sus gastos, ingresos y consultas en su propia
base de datos, y no se comparten con terceros.</p>
<p>Los mensajes de cualquier otro número se descartan sin guardar su contenido.</p>
</body></html>
"""

Procesar = Callable[[sqlite3.Connection, str, int], Any]
Enviar = Callable[[wa.ConfigWhatsApp, str, str], list]
#: (conexión, texto de Gemini, tipo, user_id) → texto final. `ValueError` si no sirve.
Componer = Callable[[sqlite3.Connection, str, str, int], str]

#: Meta deja mandar texto gratis hasta 24 h después del último mensaje de
#: Franco. Se deja un margen para no mandar justo en el borde.
VENTANA = timedelta(hours=23, minutes=50)
AVISO_PENDIENTES = "📬 Te guardé esto mientras no hablábamos:"


def token_api_desde_entorno() -> Optional[str]:
    """`SUPERAPP_API_TOKEN`, o None si no está: sin default, la ruta responde 503."""
    return os.environ.get("SUPERAPP_API_TOKEN", "").strip() or None


@dataclass
class _Trabajo:
    mensaje: wa.MensajeEntrante
    cfg: wa.ConfigWhatsApp
    user_id: int


def ahora_ar() -> datetime:
    return datetime.now(ZONA)


def _enmascarar(numero: str) -> str:
    d = wa.digitos(numero)
    return d[:4] + "…" + d[-2:] if len(d) > 6 else "…"


class ServidorAPI(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        direccion: tuple[str, int],
        *,
        procesar: Procesar,
        enviar: Enviar = wa.enviar_texto,
        cargar_config: Callable[[], wa.ConfigWhatsApp] = wa.ConfigWhatsApp.desde_entorno,
        componer: Optional[Componer] = None,
        cargar_token_api: Callable[[], Optional[str]] = token_api_desde_entorno,
        db_path: Optional[Path] = None,
    ):
        super().__init__(direccion, _Manejador)
        self.procesar = procesar
        self.enviar = enviar
        self.cargar_config = cargar_config
        self.componer = componer
        self.cargar_token_api = cargar_token_api
        self.db_path = db_path
        # Un solo envío de la cola a la vez: si el hilo trabajador entrega
        # pendientes mientras llega un briefing nuevo, ninguno sale dos veces.
        self._lock_salida = threading.Lock()
        self.cola: "queue.Queue[_Trabajo]" = queue.Queue()
        self._trabajador = threading.Thread(target=self._trabajar, name="whatsapp", daemon=True)
        self._trabajador.start()

    # -- cola --------------------------------------------------------------

    def _trabajar(self) -> None:
        while True:
            trabajo = self.cola.get()
            try:
                self._procesar_uno(trabajo)
            except Exception:  # noqa: BLE001 — el hilo no puede morir; queda en el log
                log.exception("Error inesperado en el hilo de WhatsApp")
            finally:
                self.cola.task_done()

    def _procesar_uno(self, t: _Trabajo) -> None:
        m, cfg = t.mensaje, t.cfg
        # Franco acaba de escribir: la ventana de 24 h está abierta. Primero
        # sale lo que estaba guardado, después la respuesta a su mensaje.
        self.entregar_pendientes(cfg)
        # Se le pasa al canal el `from` tal como vino; el formato con que Meta
        # acepta el envío (en AR, sin el 9) lo resuelve `wa.enviar_texto`.
        destino = wa.digitos(m.remitente)
        if m.tipo != "text" or not m.texto:
            self._marcar(m.wamid, "ignorado")
            self._avisar(cfg, destino, "Por ahora solo entiendo mensajes de texto. "
                                       "Mandá *ayuda* para ver cómo cargar.")
            return

        # Los contextvars arrancan vacíos en cada hilo: el workspace se fija acá.
        set_current_workspace_id(cfg.workspace_id)
        conn = connect(self.db_path)
        try:
            respuesta = self.procesar(conn, m.texto, t.user_id)
            conn.execute(
                "UPDATE whatsapp_mensajes SET resultado = ?, transaccion_id = ? WHERE wamid = ?",
                (respuesta.resultado, respuesta.transaccion_id, m.wamid),
            )
        except Exception:
            log.exception("Falló el procesamiento del mensaje %s", m.wamid)
            conn.execute("UPDATE whatsapp_mensajes SET resultado = 'error' WHERE wamid = ?",
                         (m.wamid,))
            self._avisar(cfg, destino, "⚠️ Algo falló procesando tu mensaje. Antes de "
                                       "reenviarlo, mirá con *resumen* si quedó cargado.")
            return
        finally:
            conn.close()
            set_current_workspace_id(None)
        self._avisar(cfg, destino, respuesta.texto)

    def _avisar(self, cfg: wa.ConfigWhatsApp, destino: str, texto: str) -> None:
        try:
            self.enviar(cfg, destino, texto)
        except wa.CanalNoDisponible as e:
            # La carga ya está hecha (o no correspondía): lo que falló es la
            # respuesta. Queda en el log con el código de Meta.
            log.error("No se pudo responder por WhatsApp (código %s): %s", e.codigo, e)

    def _marcar(self, wamid: str, resultado: str) -> None:
        conn = connect(self.db_path)
        try:
            conn.execute("UPDATE whatsapp_mensajes SET resultado = ? WHERE wamid = ?",
                         (resultado, wamid))
        finally:
            conn.close()

    # -- cola de salida (Fase B) -------------------------------------------

    def ventana_abierta(self, conn: sqlite3.Connection, ahora: Optional[datetime] = None) -> bool:
        """¿Franco escribió hace menos de `VENTANA`? Sin ningún mensaje previo, no."""
        row = conn.execute(
            "SELECT valor FROM whatsapp_estado WHERE clave = 'ultimo_entrante'").fetchone()
        if row is None:
            return False
        ahora = ahora or ahora_ar()
        return ahora - datetime.fromisoformat(row["valor"]) < VENTANA

    def encolar_saliente(
        self, cfg: wa.ConfigWhatsApp, tipo: str, texto: str, id_origen: Optional[str]
    ) -> dict:
        """Guarda el mensaje y lo manda si la ventana está abierta.

        Devuelve `{"estado": "enviado" | "en_cola", "id": …}` y, si el mismo
        `id_origen` ya había llegado, `"repetido": True` sin mandar nada.
        """
        with self._lock_salida:
            conn = connect(self.db_path)
            try:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO whatsapp_salientes (tipo, texto, id_origen, creado_en) "
                    "VALUES (?, ?, ?, ?)",
                    (tipo, texto, id_origen, ahora_ar().isoformat()),
                )
                if cur.rowcount == 0:
                    row = conn.execute(
                        "SELECT id, enviado_en FROM whatsapp_salientes WHERE id_origen = ?",
                        (id_origen,)).fetchone()
                    log.info("Briefing repetido (%s): ya estaba, no se manda de nuevo", id_origen)
                    return {"estado": "enviado" if row["enviado_en"] else "en_cola",
                            "id": row["id"], "repetido": True}
                fila = cur.lastrowid
                if not self.ventana_abierta(conn):
                    log.info("Ventana de 24 h cerrada: %s #%s queda en cola", tipo, fila)
                    return {"estado": "en_cola", "id": fila}
                enviado = self._mandar_saliente(conn, cfg, fila, texto)
                return {"estado": "enviado" if enviado else "en_cola", "id": fila}
            finally:
                conn.close()

    def entregar_pendientes(self, cfg: wa.ConfigWhatsApp) -> int:
        """Manda en orden lo que quedó en cola. Devuelve cuántos salieron."""
        with self._lock_salida:
            conn = connect(self.db_path)
            try:
                filas = conn.execute(
                    "SELECT id, texto FROM whatsapp_salientes WHERE enviado_en IS NULL "
                    "ORDER BY id").fetchall()
                salieron = 0
                for i, f in enumerate(filas):
                    texto = f"{AVISO_PENDIENTES}\n\n{f['texto']}" if i == 0 else f["texto"]
                    if not self._mandar_saliente(conn, cfg, f["id"], texto):
                        break  # el resto espera al próximo mensaje, sin perder el orden
                    salieron += 1
                return salieron
            finally:
                conn.close()

    def _mandar_saliente(
        self, conn: sqlite3.Connection, cfg: wa.ConfigWhatsApp, fila: int, texto: str
    ) -> bool:
        try:
            self.enviar(cfg, cfg.numero_autorizado, texto)
        except wa.CanalNoDisponible as e:
            log.error("Saliente #%s no salió (código %s): %s — queda en cola", fila, e.codigo, e)
            conn.execute("UPDATE whatsapp_salientes SET error = ? WHERE id = ?",
                         (f"{e.codigo}: {e}", fila))
            return False
        conn.execute("UPDATE whatsapp_salientes SET enviado_en = ?, error = NULL WHERE id = ?",
                     (ahora_ar().isoformat(), fila))
        return True

    # -- recepción ---------------------------------------------------------

    def recibir(self, payload: dict, cfg: wa.ConfigWhatsApp, user_id: int) -> int:
        """Registra y encola los mensajes válidos. Devuelve cuántos encoló."""
        mensajes, fallidos = wa.extraer_eventos(payload)
        for s in fallidos:
            for err in s.get("errors") or [{}]:
                log.error("Meta informó un envío fallido (código %s): %s",
                          err.get("code"), err.get("title") or err.get("message"))

        autorizado = wa.canonico(cfg.numero_autorizado)
        encolados = 0
        conn = connect(self.db_path)
        try:
            for m in mensajes:
                if wa.canonico(m.remitente) != autorizado:
                    log.warning("Mensaje ignorado de un número no autorizado (%s)",
                                _enmascarar(m.remitente))
                    continue
                ahora = ahora_ar().isoformat()
                cur = conn.execute(
                    "INSERT OR IGNORE INTO whatsapp_mensajes "
                    "(wamid, recibido_en, remitente, texto) VALUES (?, ?, ?, ?)",
                    (m.wamid, ahora, m.remitente, m.texto),
                )
                if cur.rowcount == 0:
                    log.info("Mensaje repetido %s: Meta reintentó, se ignora", m.wamid)
                    continue
                # El formato real del `from` todavía no se vio (ADR-0008): queda en el log.
                log.info("Mensaje %s de %s (tipo %s)", m.wamid, m.remitente, m.tipo)
                conn.execute(
                    "INSERT INTO whatsapp_estado (clave, valor, actualizado_en) "
                    "VALUES ('ultimo_entrante', ?, ?) ON CONFLICT(clave) DO UPDATE SET "
                    "valor = excluded.valor, actualizado_en = excluded.actualizado_en",
                    (ahora, ahora),
                )
                self.cola.put(_Trabajo(m, cfg, user_id))
                encolados += 1
        finally:
            conn.close()
        return encolados

    def resolver_usuario(self, cfg: wa.ConfigWhatsApp) -> int:
        """id del usuario configurado. `LookupError` si no existe o el workspace no es suyo."""
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT id FROM usuarios WHERE username = ?",
                               (cfg.usuario,)).fetchone()
            if row is None:
                raise LookupError(f"SUPERAPP_DEFAULT_USER={cfg.usuario!r} no existe en usuarios")
            if cfg.workspace_id is not None:
                es_miembro = conn.execute(
                    "SELECT 1 FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                    (cfg.workspace_id, row["id"]),
                ).fetchone()
                if not es_miembro:
                    raise LookupError(
                        f"SUPERAPP_DEFAULT_WORKSPACE={cfg.workspace_id} no es de {cfg.usuario!r}")
            return int(row["id"])
        finally:
            conn.close()


class _Manejador(BaseHTTPRequestHandler):
    server: ServidorAPI
    server_version = "SuperAppAPI"
    sys_version = ""

    # -- utilidades --------------------------------------------------------

    def log_message(self, formato: str, *args) -> None:
        # Sin query string: ahí viaja el verify token de Meta.
        log.info("%s %s → %s", self.command, urlsplit(self.path).path,
                 args[1] if len(args) > 1 else "")

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo: int, obj: dict) -> None:
        self._responder(codigo, json.dumps(obj).encode("utf-8"), "application/json")

    def _config(self) -> Optional[wa.ConfigWhatsApp]:
        try:
            return self.server.cargar_config()
        except wa.ConfigIncompleta as e:
            log.error("Webhook deshabilitado: %s", e)
            self._json(503, {"ok": False, "error": "sin_configurar"})
            return None

    # -- rutas -------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 — nombre que impone http.server
        partes = urlsplit(self.path)
        if partes.path == "/api/health":
            self._json(200, {"ok": True})
        elif partes.path == "/api/privacidad":
            self._responder(200, PRIVACIDAD_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif partes.path == "/api/whatsapp":
            cfg = self._config()
            if cfg is None:
                return
            challenge = wa.verificar_suscripcion(dict(parse_qsl(partes.query)), cfg.verify_token)
            if challenge is None:
                self._json(403, {"ok": False, "error": "verificacion_fallida"})
            else:
                self._responder(200, challenge.encode("utf-8"), "text/plain")
        else:
            self._json(404, {"ok": False, "error": "no_existe"})

    def do_POST(self) -> None:  # noqa: N802
        ruta = urlsplit(self.path).path
        if ruta == "/api/briefing":
            self._post_briefing()
            return
        if ruta != "/api/whatsapp":
            self._json(404, {"ok": False, "error": "no_existe"})
            return
        # El cuerpo se lee **antes** de cualquier rechazo: si se responde sin
        # leerlo, el cliente todavía está mandando y la conexión se corta
        # (en Windows, ConnectionResetError) en vez de recibir el 503.
        largo = int(self.headers.get("Content-Length") or 0)
        if largo <= 0 or largo > MAX_CUERPO:
            self._json(400, {"ok": False, "error": "cuerpo_invalido"})
            return
        cuerpo = self.rfile.read(largo)

        cfg = self._config()
        if cfg is None:
            return
        if not wa.firma_valida(cuerpo, self.headers.get("X-Hub-Signature-256"), cfg.app_secret):
            log.warning("POST /api/whatsapp con firma inválida: descartado")
            self._json(401, {"ok": False, "error": "firma_invalida"})
            return
        try:
            payload = json.loads(cuerpo)
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "json_invalido"})
            return

        try:
            user_id = self.server.resolver_usuario(cfg)
        except LookupError as e:
            log.error("Webhook deshabilitado: %s", e)
            self._json(503, {"ok": False, "error": "usuario_invalido"})
            return

        self.server.recibir(payload, cfg, user_id)
        self._json(200, {"ok": True})


    def _post_briefing(self) -> None:
        """Briefing de Gemini (vía Apps Script) → se arma y sale por la cola."""
        largo = int(self.headers.get("Content-Length") or 0)
        if largo <= 0 or largo > MAX_CUERPO:
            self._json(400, {"ok": False, "error": "cuerpo_invalido"})
            return
        cuerpo = self.rfile.read(largo)  # antes de cualquier rechazo (ver do_POST)

        token = self.server.cargar_token_api()
        if token is None or self.server.componer is None:
            log.error("/api/briefing deshabilitado: falta SUPERAPP_API_TOKEN")
            self._json(503, {"ok": False, "error": "sin_configurar"})
            return
        recibido = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(recibido.encode("utf-8"), token.encode("utf-8")):
            log.warning("POST /api/briefing con token inválido: descartado")
            self._json(401, {"ok": False, "error": "no_autorizado"})
            return
        cfg = self._config()
        if cfg is None:
            return
        try:
            datos = json.loads(cuerpo)
            texto = datos["texto"]
            tipo = datos.get("tipo") or "briefing"
            id_origen = datos.get("id") or None
            if not isinstance(texto, str) or not isinstance(tipo, str):
                raise TypeError("texto y tipo tienen que ser texto")
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            self._json(400, {"ok": False, "error": "json_invalido", "detalle": str(e)})
            return
        try:
            user_id = self.server.resolver_usuario(cfg)
        except LookupError as e:
            log.error("/api/briefing deshabilitado: %s", e)
            self._json(503, {"ok": False, "error": "usuario_invalido"})
            return

        set_current_workspace_id(cfg.workspace_id)
        conn = connect(self.server.db_path)
        try:
            final = self.server.componer(conn, texto, tipo, user_id)
        except ValueError as e:
            self._json(400, {"ok": False, "error": "parametros_invalidos", "detalle": str(e)})
            return
        finally:
            conn.close()
            set_current_workspace_id(None)

        resultado = self.server.encolar_saliente(
            cfg, tipo, final, str(id_origen) if id_origen else None)
        self._json(200, {"ok": True, **resultado})


def crear_servidor(host: str, puerto: int, **dependencias) -> ServidorAPI:
    return ServidorAPI((host, puerto), **dependencias)
