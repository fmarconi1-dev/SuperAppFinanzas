"""Datos del Inicio: finanzas del mes y últimos movimientos (Fase C).

**Puro, sin Streamlit.** Los números salen de `comandos.totales_mes`, la misma
función que contesta `resumen` por WhatsApp: el Inicio y el bot no pueden
mostrar cifras distintas.

La variación se calcula contra **el mismo período del mes anterior** (del 1 al
día de hoy), no contra el mes entero: el 17/10, octubre lleva 17 días y
septiembre tuvo 30, así que comparar contra septiembre completo haría parecer
que siempre se gasta menos.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from places.finanzas.core.comandos import TotalesMes, totales_mes
from places.finanzas.core.transactions import list_recent

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass
class ResumenMes:
    hoy: date
    actual: TotalesMes
    #: El mismo período del mes anterior; None si ese mes no tuvo movimientos.
    previo: Optional[TotalesMes]

    @property
    def balance(self) -> float:
        return self.actual.ingresos - self.actual.gastos

    @property
    def mes(self) -> str:
        return MESES[self.hoy.month - 1]

    @property
    def mes_previo(self) -> str:
        return MESES[mes_anterior(self.hoy).month - 1]

    def periodo_previo(self) -> str:
        """"1 al 17 de septiembre" (o "septiembre" si hoy es el último día de un mes largo)."""
        fin = min(self.hoy.day, _ultimo_dia(mes_anterior(self.hoy)))
        return f"1 al {fin} de {self.mes_previo}"


def mes_anterior(hoy: date) -> date:
    """El primer día del mes anterior."""
    return (hoy.replace(day=1) - timedelta(days=1)).replace(day=1)


def _ultimo_dia(primero: date) -> int:
    siguiente = (primero.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (siguiente - timedelta(days=1)).day


def variacion(actual: float, previo: Optional[float]) -> Optional[float]:
    """Variación % contra el período anterior. None si no hay con qué comparar (no "inf%")."""
    if previo is None or previo <= 0:
        return None
    return (actual - previo) / previo * 100


def formatear_variacion(v: Optional[float]) -> Optional[str]:
    """+4,2% · -3,0% · None. Con signo explícito: el color nunca va solo.

    El menos es el ASCII "-" a propósito: `st.metric` decide la flecha y el
    color mirando si el delta empieza con "-"; con el "−" tipográfico pintaría
    una baja como suba.
    """
    if v is None:
        return None
    signo = "+" if v >= 0 else "-"
    return f"{signo}{abs(v):.1f}%".replace(".", ",")


def resumen_del_mes(conn: sqlite3.Connection, *, user_id: int, hoy: date) -> Optional[ResumenMes]:
    """Totales del mes en curso y del mismo período del anterior. None si no hay ningún movimiento."""
    actual = totales_mes(conn, user_id=user_id, hoy=hoy)
    if actual is None:
        return None
    previo = totales_mes(conn, user_id=user_id, hoy=mes_anterior(hoy), hasta_dia=hoy.day)
    if previo is not None and previo.movimientos == 0:
        previo = None
    return ResumenMes(hoy=hoy, actual=actual, previo=previo)


def ultimos_movimientos(conn: sqlite3.Connection, *, user_id: int, n: int = 5) -> list[dict]:
    """Los últimos `n` movimientos, con el monto ya con signo: gasto negativo, ingreso positivo."""
    filas = []
    for t in list_recent(conn, n, user_id=user_id):
        monto = float(t["ingresos"] or 0) - float(t["pasivos"] or 0)
        filas.append({"fecha": date.fromisoformat(t["fecha"]), "motivo": t["motivo"],
                      "comentario": t.get("comentario"), "monto": monto})
    return filas


def mensajes_en_cola(conn: sqlite3.Connection) -> int:
    """Briefings esperando a que Franco le escriba al bot (ventana de 24 h de Meta)."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM whatsapp_salientes WHERE enviado_en IS NULL").fetchone()
    return int(row["n"])


def saludo(hora: int) -> str:
    if 5 <= hora < 13:
        return "Buen día"
    if 13 <= hora < 20:
        return "Buenas tardes"
    return "Buenas noches"


def fecha_larga(d: date) -> str:
    """"viernes 17 de octubre de 2026"."""
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"
