"""Armado de los briefings de Gemini para WhatsApp (Fase B, ADR-0008).

**Puro y sin red.** Los dos briefings los genera Gemini y llegan como texto
(mail reenviado por el Apps Script). Acá solo se decide qué se les suma:

* ``briefing`` (el de la mañana): al final, el bloque de finanzas del mes, con
  los **mismos números que `resumen`** (`comandos.totales_mes`).
* ``cierre`` (el de mercado): tal cual. La SuperApp no agrega ni valida datos
  de mercado: los números son de Gemini.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from places.finanzas.core.comandos import pesos, totales_mes

TIPOS = ("briefing", "cierre")


def bloque_finanzas(conn: sqlite3.Connection, *, user_id: int, hoy: date) -> str:
    """El renglón de finanzas del mes que va al pie del briefing de la mañana."""
    titulo = f"*📊 MIS FINANZAS ({hoy:%m/%Y})*"
    t = totales_mes(conn, user_id=user_id, hoy=hoy)
    if t is None:
        return f"{titulo}\nTodavía no hay movimientos este mes."
    lineas = [
        titulo,
        f"Gastos {pesos(t.gastos)} · Ingresos {pesos(t.ingresos)} · {t.movimientos} mov.",
    ]
    if t.sin_categorizar:
        lineas.append(f"Sin categorizar: {pesos(t.sin_categorizar)}")
    return "\n".join(lineas)


def componer(
    conn: sqlite3.Connection, texto: str, tipo: str, *, user_id: int, hoy: date
) -> str:
    """Texto de Gemini + lo nuestro, listo para WhatsApp. `ValueError` si el tipo no existe."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo desconocido: {tipo!r} (tiene que ser {' o '.join(TIPOS)})")
    texto = (texto or "").replace("\r\n", "\n").strip()
    if not texto:
        raise ValueError("el briefing llegó vacío")
    if tipo == "cierre":
        return texto
    return f"{texto}\n\n{bloque_finanzas(conn, user_id=user_id, hoy=hoy)}"
