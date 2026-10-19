"""Canal WhatsApp vía Meta Cloud API. **El único módulo que habla con Meta.**

Si el canal cambia (plan B: Telegram), se reemplaza este archivo y nada más:
`places/finanzas/core/comandos.py` no sabe de dónde viene el texto.

**Costo cero (ADR-0008), candado 2:** acá solo se arman mensajes de texto
libre. No hay ninguna función que mande plantillas, que son lo único que Meta
cobra, y `tests/test_api_whatsapp.py` falla si aparece la palabra en este
archivo. Un texto fuera de la ventana de 24 h no se cobra: Meta lo rechaza
(131047) y acá se levanta `CanalNoDisponible`.

**Números argentinos (comprobado en producción el 15/10/2026):** hay dos
formatos y cada uno va en un lugar distinto:

* **En la lista del panel de Meta**, el celular va **con el 9** (``549…``).
  Con el número cargado sin el 9, Meta *aceptaba* los envíos y no los
  entregaba nunca: aceptar no es entregar.
* **Los mensajes entrantes** traen el ``from`` **con el 9** (``549…``).
* **Para mandar**, Meta lo quiere **sin el 9** (``54…``): mandar a ``549…``
  devuelve 131030 ("no está en la lista") aunque la lista esté bien.

Por eso se manda primero en forma canónica (sin el 9) y, solo si Meta
responde 131030, se reintenta con el 9; queda en el log. El remitente se
compara con el autorizado también en forma canónica.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("superapp.api.whatsapp")

#: Versión de la Graph API. v23.0 es la que se probó el 15/10/2026.
GRAPH_VERSION_DEFAULT = "v23.0"
#: Tope de Meta para el cuerpo de un mensaje de texto.
LIMITE_TEXTO = 4096
#: "Recipient phone number not in allowed list".
NO_AUTORIZADO = 131030
#: Base de la Graph API (los tests la apuntan a un servidor local).
GRAPH_BASE = "https://graph.facebook.com"
#: Tope de un archivo recibido. Un extracto o un resumen pesan unos cientos
#: de KB; una foto del celular, 2–5 MB.
MAX_ARCHIVO = 10 * 1024 * 1024
#: Tipos de mensaje que traen un archivo.
TIPOS_CON_ARCHIVO = ("document", "image")


class CanalNoDisponible(Exception):
    """Meta no aceptó el envío. Se nombra con su código, no se traga."""

    def __init__(self, mensaje: str, codigo: Optional[int] = None):
        super().__init__(mensaje)
        self.codigo = codigo


class ArchivoNoDisponible(Exception):
    """No se pudo bajar un archivo de Meta (vencido, caído, demasiado grande)."""


class ConfigIncompleta(Exception):
    """Faltan variables de entorno obligatorias: el webhook responde 503."""

    def __init__(self, faltantes: list[str]):
        super().__init__("Faltan variables de entorno: " + ", ".join(faltantes))
        self.faltantes = faltantes


@dataclass(frozen=True)
class ConfigWhatsApp:
    token: str
    phone_number_id: str
    app_secret: str
    verify_token: str
    numero_autorizado: str
    usuario: str
    workspace_id: Optional[int] = None
    graph_version: str = GRAPH_VERSION_DEFAULT

    @classmethod
    def desde_entorno(cls) -> "ConfigWhatsApp":
        """Lee la configuración. Sin defaults para nada que sea secreto."""
        nombres = {
            "token": "WHATSAPP_TOKEN",
            "phone_number_id": "WHATSAPP_PHONE_NUMBER_ID",
            "app_secret": "WHATSAPP_APP_SECRET",
            "verify_token": "WHATSAPP_VERIFY_TOKEN",
            "numero_autorizado": "WHATSAPP_NUMERO_AUTORIZADO",
            "usuario": "SUPERAPP_DEFAULT_USER",
        }
        valores = {campo: os.environ.get(var, "").strip() for campo, var in nombres.items()}
        faltantes = [nombres[c] for c, v in valores.items() if not v]
        ws = os.environ.get("SUPERAPP_DEFAULT_WORKSPACE", "").strip()
        if ws and not ws.isdigit():
            faltantes.append("SUPERAPP_DEFAULT_WORKSPACE (tiene que ser un número)")
        if faltantes:
            raise ConfigIncompleta(faltantes)
        return cls(
            **valores,
            workspace_id=int(ws) if ws else None,
            graph_version=os.environ.get("WHATSAPP_GRAPH_VERSION", "").strip()
            or GRAPH_VERSION_DEFAULT,
        )


@dataclass(frozen=True)
class ArchivoEntrante:
    """Lo que Meta dice de un archivo. El contenido se baja aparte, con el id."""

    media_id: str
    mime: Optional[str] = None
    nombre: Optional[str] = None
    pie: Optional[str] = None


@dataclass(frozen=True)
class MensajeEntrante:
    wamid: str
    remitente: str
    tipo: str
    texto: Optional[str]
    archivo: Optional[ArchivoEntrante] = None


# ---------------------------------------------------------------------------
# Números
# ---------------------------------------------------------------------------

def digitos(numero: str) -> str:
    return "".join(c for c in str(numero) if c.isdigit())


def canonico(numero: str) -> str:
    """Forma canónica: celulares de AR sin el 9.

    Sirve para comparar remitentes y es el **primer formato al mandar**: Meta
    rechaza (131030) los envíos a ``549…`` y acepta y entrega ``54…``.
    """
    d = digitos(numero)
    if d.startswith("549") and len(d) == 13:
        return "54" + d[3:]
    return d


# ---------------------------------------------------------------------------
# Webhook entrante
# ---------------------------------------------------------------------------

def verificar_suscripcion(params: dict[str, str], verify_token: str) -> Optional[str]:
    """GET de Meta al configurar el webhook: devuelve el challenge si el token coincide."""
    if params.get("hub.mode") != "subscribe":
        return None
    if not hmac.compare_digest(params.get("hub.verify_token", ""), verify_token):
        return None
    return params.get("hub.challenge")


def firma_valida(cuerpo: bytes, cabecera: Optional[str], app_secret: str) -> bool:
    """`X-Hub-Signature-256: sha256=<hex>` = HMAC-SHA256 del cuerpo **crudo**."""
    if not cabecera or not cabecera.startswith("sha256="):
        return False
    esperada = hmac.new(app_secret.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(cabecera.removeprefix("sha256="), esperada)


def extraer_eventos(payload: dict) -> tuple[list[MensajeEntrante], list[dict]]:
    """(mensajes entrantes, estados `failed`). Los entregados/leídos se descartan.

    Los `failed` importan: ahí aparece tarde un 131042 (pago) o un 131047
    (ventana cerrada) de un mensaje que Meta había aceptado.
    """
    mensajes: list[MensajeEntrante] = []
    fallidos: list[dict] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for m in value.get("messages") or []:
                tipo = m.get("type", "")
                texto = (m.get("text") or {}).get("body") if tipo == "text" else None
                archivo = None
                if tipo in TIPOS_CON_ARCHIVO and (datos := m.get(tipo) or {}).get("id"):
                    archivo = ArchivoEntrante(datos["id"], datos.get("mime_type"),
                                              datos.get("filename"), datos.get("caption"))
                if m.get("id") and m.get("from"):
                    mensajes.append(MensajeEntrante(m["id"], m["from"], tipo, texto, archivo))
            for s in value.get("statuses") or []:
                if s.get("status") == "failed":
                    fallidos.append(s)
    return mensajes, fallidos


# ---------------------------------------------------------------------------
# Archivos recibidos
# ---------------------------------------------------------------------------

def _get(url: str, token: str, que: str) -> bytes:
    pedido = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(pedido, timeout=30) as r:
            datos = r.read(MAX_ARCHIVO + 1)
    except urllib.error.HTTPError as e:
        raise ArchivoNoDisponible(f"Meta no me dio {que} (HTTP {e.code})") from None
    except urllib.error.URLError as e:
        raise ArchivoNoDisponible(f"no pude conectar con Meta para bajar {que}: {e.reason}") from None
    if len(datos) > MAX_ARCHIVO:
        raise ArchivoNoDisponible(f"el archivo pasa de {MAX_ARCHIVO // (1024 * 1024)} MB")
    return datos


def descargar_archivo(cfg: ConfigWhatsApp, media_id: str) -> bytes:
    """Baja un archivo recibido. **A memoria**: nunca se escribe en disco.

    Son dos pasos: con el id se pide a la Graph API la URL del archivo, y
    esa URL se baja con el mismo token. La URL **vence a los pocos minutos**:
    por eso el hilo trabajador baja el archivo antes que cualquier otra cosa.
    Bajar un archivo recibido es gratis (Meta cobra solo las plantillas).
    """
    info = _get(f"{GRAPH_BASE}/{cfg.graph_version}/{media_id}", cfg.token, "los datos del archivo")
    try:
        meta = json.loads(info)
    except json.JSONDecodeError:
        raise ArchivoNoDisponible("Meta contestó algo que no entiendo sobre el archivo") from None
    if not meta.get("url"):
        raise ArchivoNoDisponible("Meta no me dio la dirección del archivo")
    if int(meta.get("file_size") or 0) > MAX_ARCHIVO:
        raise ArchivoNoDisponible(f"el archivo pasa de {MAX_ARCHIVO // (1024 * 1024)} MB")
    return _get(meta["url"], cfg.token, "el archivo")


# ---------------------------------------------------------------------------
# Envío
# ---------------------------------------------------------------------------

def partir_texto(texto: str, limite: int = LIMITE_TEXTO) -> list[str]:
    """Parte un texto largo por párrafos; si un párrafo no entra, por líneas."""
    if len(texto) <= limite:
        return [texto]
    piezas: list[str] = []
    for parrafo in texto.split("\n\n"):
        if len(parrafo) <= limite:
            piezas.append(parrafo)
            continue
        for linea in parrafo.split("\n"):
            while len(linea) > limite:
                piezas.append(linea[:limite])
                linea = linea[limite:]
            piezas.append(linea)
    partes: list[str] = []
    actual = ""
    for p in piezas:
        sep = "\n\n" if actual else ""
        if len(actual) + len(sep) + len(p) <= limite:
            actual += sep + p
        else:
            partes.append(actual)
            actual = p
    if actual:
        partes.append(actual)
    return partes


def _post_mensaje(cfg: ConfigWhatsApp, numero: str, cuerpo: str) -> dict:
    datos = json.dumps({
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": cuerpo},
    }).encode("utf-8")
    pedido = urllib.request.Request(
        f"{GRAPH_BASE}/{cfg.graph_version}/{cfg.phone_number_id}/messages",
        data=datos,
        headers={"Authorization": f"Bearer {cfg.token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(pedido, timeout=15) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            error = json.loads(e.read() or b"{}").get("error", {})
        except json.JSONDecodeError:
            error = {}
        raise CanalNoDisponible(
            f"Meta rechazó el envío (HTTP {e.code}): {error.get('message', '')}",
            error.get("code"),
        ) from None
    except urllib.error.URLError as e:
        raise CanalNoDisponible(f"No se pudo conectar con Meta: {e.reason}") from None


def formatos_envio(numero: str) -> list[str]:
    """Formatos a probar al mandar: el canónico (sin el 9) primero, después
    el original. Si son iguales, uno solo."""
    d = digitos(numero)
    c = canonico(d)
    return [c] if c == d else [c, d]


def enviar_texto(cfg: ConfigWhatsApp, numero: str, texto: str) -> list[str]:
    """Manda un texto (partido si hace falta). Devuelve los ids de Meta."""
    formatos = formatos_envio(numero)
    ids: list[str] = []
    for parte in partir_texto(texto):
        for i, destino in enumerate(formatos):
            try:
                r = _post_mensaje(cfg, destino, parte)
            except CanalNoDisponible as e:
                if e.codigo != NO_AUTORIZADO:
                    raise
                if i + 1 < len(formatos):
                    log.warning("Meta no reconoció %s (131030); pruebo %s",
                                destino, formatos[i + 1])
                    continue
                raise CanalNoDisponible(
                    f"{e} — probé {', '.join(formatos)}. Revisá que el número esté en la "
                    "lista de destinatarios del panel de Meta (un celular argentino va CON "
                    "el 9: +54 9 …).",
                    e.codigo,
                ) from None
            ids.extend(m.get("id", "") for m in r.get("messages") or [])
            break
    return ids
