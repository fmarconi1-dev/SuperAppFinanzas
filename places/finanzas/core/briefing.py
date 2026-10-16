"""Armado de los briefings de Gemini para WhatsApp (Fase B, ADR-0008).

**Puro y sin red.** Los dos briefings los genera Gemini y llegan como texto
(mail reenviado por el Apps Script): ``briefing`` (el de la mañana) y
``cierre`` (el de mercado). **Se mandan tal cual**: la SuperApp no les suma
nada ni valida sus datos.

Decisión de Franco (16/10/2026): *"El briefing es una cosa, mis finanzas son
otra"*. Las finanzas del mes se consultan aparte, con el comando `resumen`.
"""

from __future__ import annotations

import sqlite3
from datetime import date

TIPOS = ("briefing", "cierre")


def componer(
    conn: sqlite3.Connection, texto: str, tipo: str, *, user_id: int, hoy: date
) -> str:
    """Texto de Gemini listo para WhatsApp. `ValueError` si el tipo no existe o llega vacío.

    `conn`, `user_id` y `hoy` no se usan hoy: quedan en la firma para que el
    servidor no cambie si algún día un tipo necesita la base.
    """
    if tipo not in TIPOS:
        raise ValueError(f"tipo desconocido: {tipo!r} (tiene que ser {' o '.join(TIPOS)})")
    texto = (texto or "").replace("\r\n", "\n").strip()
    if not texto:
        raise ValueError("el briefing llegó vacío")
    return texto
