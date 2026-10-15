"""Servidor HTTP de la API (stdlib): rutas, autenticación y la cola de trabajo.

Escucha en ``127.0.0.1:8000``; nginx le pasa todo lo que empieza con
``/api/``. Rutas:

    GET  /api/health      → 200 {"ok": true}
    GET  /api/whatsapp    → verificación de la suscripción de Meta (hub.challenge)
    POST /api/whatsapp    → mensajes entrantes, firmados por Meta
    GET  /api/privacidad  → política de privacidad (Meta la pide para el modo Live)

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

`core/` no importa `places/`: la lógica de los comandos llega inyectada
(`procesar`), y quien la conecta es `api.py`.
"""

from __future__ import annotations

import json
import logging
import queue
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
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
        db_path: Optional[Path] = None,
    ):
        super().__init__(direccion, _Manejador)
        self.procesar = procesar
        self.enviar = enviar
        self.cargar_config = cargar_config
        self.db_path = db_path
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
        # Se responde al `from` exacto: es el id de WhatsApp que da Meta. Un
        # formato deducido puede ser aceptado y nunca entregado (15/10/2026).
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
        if urlsplit(self.path).path != "/api/whatsapp":
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


def crear_servidor(host: str, puerto: int, **dependencias) -> ServidorAPI:
    return ServidorAPI((host, puerto), **dependencias)
