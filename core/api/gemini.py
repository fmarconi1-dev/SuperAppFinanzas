"""Leer fotos con Gemini, plan gratuito (Fase D, paso 6, ADR-0009 §8).

**Gemini solo extrae filas** (fecha, descripción, monto, si es ingreso) en
JSON. El emparejamiento, la categoría y lo que se carga los decide el mismo
código determinístico de siempre (ADR-0006 §6: la IA nunca decide plata), y
todo pasa por una propuesta con `ok`.

* Solo para **fotos y capturas** (el Excel y el PDF se leen sin IA).
* **Plan gratuito:** Franco aceptó que Google puede usar el contenido. La
  clave se crea en Google AI Studio **en un proyecto sin facturación** (así no
  hay nada que cobrar) y va en `fly secrets` como `GEMINI_API_KEY`, **sin valor
  por defecto**: si falta, el Secretario dice que no puede leer fotos y pide
  el archivo.
* Modelo: `GEMINI_MODELO`, por defecto ``gemini-3.5-flash-lite`` (gratuito y
  con entrada de imagen, verificado en la página de precios el 20/10/2026).
* Un error de la API se nombra (`GeminiNoDisponible`) y le llega a Franco;
  nunca se convierte en "no había nada en la foto".
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"

INSTRUCCIONES = (
    "Sos un lector de comprobantes y capturas de pantalla de movimientos de plata en "
    "Argentina. Extraé SOLO los movimientos que se ven en la imagen, uno por fila: la "
    "fecha (AAAA-MM-DD; si no tiene año, dejá el año vacío como 0000), una descripción "
    "corta (el comercio o la persona, sin números de cuenta, CUIT, CBU ni tarjeta), el "
    "monto en pesos como número positivo (punto decimal, sin separador de miles) y si es "
    "un ingreso (plata que entra). No inventes nada: si un dato no se lee, no incluyas esa "
    "fila. Si no hay movimientos, devolvé una lista vacía."
)

ESQUEMA = {
    "type": "OBJECT",
    "properties": {"filas": {"type": "ARRAY", "items": {
        "type": "OBJECT",
        "properties": {"fecha": {"type": "STRING"}, "descripcion": {"type": "STRING"},
                       "monto": {"type": "NUMBER"}, "es_ingreso": {"type": "BOOLEAN"}},
        "required": ["fecha", "descripcion", "monto"]}}},
    "required": ["filas"],
}

_MIMES = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


class GeminiNoDisponible(Exception):
    """Gemini no contestó, rechazó el pedido o devolvió algo que no se entiende."""


@dataclass(frozen=True)
class ClienteGemini:
    clave: str
    modelo: str = MODELO_POR_DEFECTO

    @classmethod
    def desde_entorno(cls) -> Optional["ClienteGemini"]:
        """None si no está `GEMINI_API_KEY`: sin clave no se leen fotos (y se dice)."""
        clave = os.environ.get("GEMINI_API_KEY", "").strip()
        if not clave:
            return None
        return cls(clave, os.environ.get("GEMINI_MODELO", "").strip() or MODELO_POR_DEFECTO)

    def extraer_filas(self, datos: bytes, tipo: str) -> list[dict]:
        """La foto → filas crudas como las da Gemini (se validan en `places/`)."""
        cuerpo = json.dumps({
            "contents": [{"parts": [
                {"inline_data": {"mime_type": _MIMES.get(tipo, "image/jpeg"),
                                 "data": base64.b64encode(datos).decode("ascii")}},
                {"text": INSTRUCCIONES},
            ]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "responseSchema": ESQUEMA, "temperature": 0},
        }).encode("utf-8")
        pedido = urllib.request.Request(
            f"{BASE}/{self.modelo}:generateContent", data=cuerpo, method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self.clave})
        try:
            with urllib.request.urlopen(pedido, timeout=60) as r:
                respuesta = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise GeminiNoDisponible(f"Gemini respondió {e.code}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise GeminiNoDisponible(f"no pude hablar con Gemini ({e})") from None
        except json.JSONDecodeError:
            raise GeminiNoDisponible("Gemini contestó algo que no es JSON") from None
        try:
            texto = respuesta["candidates"][0]["content"]["parts"][0]["text"]
            filas = json.loads(texto)["filas"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            motivo = (respuesta.get("promptFeedback") or {}).get("blockReason") if isinstance(
                respuesta, dict) else None
            raise GeminiNoDisponible(
                f"Gemini no devolvió las filas{f' ({motivo})' if motivo else ''}") from None
        if not isinstance(filas, list):
            raise GeminiNoDisponible("Gemini no devolvió una lista de filas")
        return filas
