"""Corregir por chat lo que ya está cargado (Fase E, paso 3, ADR-0012).

Dos órdenes, escritas a mano o traducidas por Gemini (que las propone y
Franco confirma con *sí*):

* ``#505 fecha 02/11`` — cambia la fecha de un gasto o ingreso. Para lo que
  cuenta en otro mes que el que dice el banco (Franco, 6/11/2026: los haberes
  de UCEMA del 28/10 son de noviembre).
* ``partir #511 19400 + 1000 propina`` — parte un gasto en varios que suman lo
  mismo (un café de 19.400 con tarjeta y 1.000 de propina en efectivo): así la
  conciliación encuentra los 19.400 y los 1.000 quedan como efectivo.

Cada cambio es un lote propio (`lotes.aplicar_edicion`): backup, todo o nada,
`deshacer` lo revierte, y no descarta la propuesta abierta. Puro: sin red.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from places.finanzas.core import lotes
from places.finanzas.core.comandos import (
    EntradaInvalida,
    Respuesta,
    _fecha_corta,
    parsear_fecha,
    parsear_monto,
    pesos,
)

_RE_FECHA = re.compile(r"^\s*#(\d+)\s+fecha\s+(\S+)\s*$", re.IGNORECASE)
_RE_PARTIR = re.compile(r"^\s*partir\s+#(\d+)\s+(.+)$", re.IGNORECASE)
#: Una parte: el monto (o una cuenta) y, opcional, un comentario con letras.
_RE_PARTE = re.compile(r"^\s*(\$?\s*[\d.,]+k?)\s*(.*?)\s*$", re.IGNORECASE)
#: Lo que se puede errar al partir: una diferencia de $1 (los centavos de una cuenta).
TOLERANCIA = 1.0


@dataclass
class Edicion:
    txn_id: int
    #: "fecha" | "partir"
    tipo: str
    fecha: Optional[date] = None
    #: (monto, comentario) de cada parte, en el orden escrito.
    partes: list = field(default_factory=list)


def parsear(texto: str, hoy: date) -> Optional[Edicion]:
    """La orden de edición, o None si el mensaje no es una. `EntradaInvalida` si está mal."""
    if m := _RE_FECHA.match(texto):
        return Edicion(int(m.group(1)), "fecha", fecha=parsear_fecha(m.group(2), hoy))
    if m := _RE_PARTIR.match(texto):
        partes = []
        for crudo in re.split(r"\s*[+,;]\s*", m.group(2).strip()):
            if not crudo:
                continue
            p = _RE_PARTE.match(crudo)
            if not p:
                raise EntradaInvalida(f"«{crudo}» no es una parte: va el monto y, si querés, "
                                      "un comentario (*1000 propina*).")
            partes.append((parsear_monto(p.group(1)), p.group(2) or None))
        if len(partes) < 2:
            raise EntradaInvalida("Para partir hacen falta al menos dos montos: "
                                  "*partir #511 19400 + 1000 propina*.")
        if any(monto <= 0 for monto, _ in partes):
            raise EntradaInvalida("Cada parte tiene que ser un monto mayor que cero.")
        return Edicion(int(m.group(1)), "partir", partes=partes)
    return None


def _gasto(conn: sqlite3.Connection, txn_id: int, wid: int) -> dict:
    row = conn.execute(
        "SELECT t.id, t.fecha, t.motivo, t.pasivos, t.ingresos, t.comentario, gc.cuenta "
        "FROM transacciones t LEFT JOIN gasto_cuentas gc ON gc.transaccion_id = t.id "
        "WHERE t.id = ? AND t.workspace_id = ?", (txn_id, wid)).fetchone()
    if row is None:
        raise EntradaInvalida(f"No encuentro el #{txn_id}.")
    return dict(row)


def _describir(g: dict, hoy: date) -> str:
    monto = g["ingresos"] or g["pasivos"]
    signo = "+" if g["ingresos"] else ""
    return (f"#{g['id']} {g['motivo']} {signo}{pesos(monto)} "
            f"({_fecha_corta(date.fromisoformat(g['fecha']), hoy)})")


#: Los vínculos con una fila del banco: el gasto es esa fila (o su devolución).
_CONCILIADO = ("origen", "mismo", "arrastre", "devolucion")


def _conciliado(conn: sqlite3.Connection, txn_id: int) -> bool:
    return conn.execute(
        f"SELECT 1 FROM emparejamientos WHERE transaccion_id = ? AND banco_fila_id IS NOT NULL "
        f"AND rol IN ({', '.join('?' for _ in _CONCILIADO)}) LIMIT 1",
        (txn_id, *_CONCILIADO)).fetchone() is not None


def explicar(conn: sqlite3.Connection, e: Edicion, *, wid: int, hoy: date) -> str:
    """Lo que va a hacer la edición, con el gasto completo (para el *sí* de una traducción:
    «#505» solo no dice qué es). `EntradaInvalida` si no se puede hacer."""
    g = _gasto(conn, e.txn_id, wid)
    if e.tipo == "fecha":
        return f"cambiar {_describir(g, hoy)} al {_fecha_corta(e.fecha, hoy)}"
    if _conciliado(conn, e.txn_id):
        raise EntradaInvalida(f"{_describir(g, hoy)} ya está conciliado con el banco: "
                              "partirlo lo desarmaría.")
    partes = " + ".join(pesos(m) + (f" {c}" if c else "") for m, c in e.partes)
    return f"partir {_describir(g, hoy)} en {partes}"


def aplicar(conn: sqlite3.Connection, e: Edicion, *, user_id: int, wid: int, hoy: date,
            ahora: datetime) -> Respuesta:
    """Aplica la edición (ya confirmada o escrita a mano) y dice qué cambió."""
    try:
        g = _gasto(conn, e.txn_id, wid)
    except EntradaInvalida as err:
        return Respuesta(f"⚠️ {err}", "rechazado")
    antes = _describir(g, hoy)
    if e.tipo == "fecha":
        if e.fecha.isoformat() == g["fecha"]:
            return Respuesta(f"{antes} ya tiene esa fecha: no cambié nada.", "rechazado")
        lotes.aplicar_edicion(
            conn, workspace_id=wid, user_id=user_id, ahora=ahora,
            propuesta={"tipo": "edicion", "orden": f"#{e.txn_id} fecha {e.fecha.isoformat()}"},
            operaciones=[lotes.Actualizar("transacciones", e.txn_id,
                                          {"fecha": e.fecha.isoformat()})])
        return Respuesta(f"✅ {antes} → ahora es del {_fecha_corta(e.fecha, hoy)}.\n"
                         "*deshacer* lo vuelve atrás.", "lote")

    if _conciliado(conn, e.txn_id):
        # La fila del banco quedaría atada a un monto menor, y la parte nueva saldría
        # como un sobrante que se toma por efectivo.
        return Respuesta(f"⚠️ {antes} ya está conciliado con el banco: partirlo lo "
                         "desarmaría. No cambié nada.", "rechazado")
    columna = "ingresos" if g["ingresos"] else "pasivos"
    total = g[columna]
    suma = sum(monto for monto, _ in e.partes)
    if abs(suma - total) > TOLERANCIA:
        return Respuesta(f"⚠️ Las partes suman {pesos(suma)} y {antes} es de {pesos(total)}: "
                         "tienen que sumar lo mismo. No cambié nada.", "rechazado")
    (primero, comentario0), *resto = e.partes
    operaciones = [lotes.Actualizar("transacciones", e.txn_id, {
        columna: primero, "comentario": comentario0 or g["comentario"]})]
    if g["cuenta"]:
        # La cuenta guardada ("19400+1000") ya no es la de este gasto: queda la suya.
        operaciones.append(lotes.Actualizar("gasto_cuentas", e.txn_id,
                                            {"cuenta": f"{primero:g}", "bruto": primero}))
    fecha = date.fromisoformat(g["fecha"])
    for i, (monto, comentario) in enumerate(resto):
        operaciones.append(lotes.InsertarMovimiento(lotes.Movimiento(
            fecha=fecha, motivo=g["motivo"], comentario=comentario,
            **{columna: monto}), clave=f"p{i}"))
    lotes.aplicar_edicion(
        conn, workspace_id=wid, user_id=user_id, ahora=ahora, operaciones=operaciones,
        propuesta={"tipo": "edicion", "orden": f"partir #{e.txn_id}",
                   "partes": [m for m, _ in e.partes]})
    lineas = [f"✅ Partí {antes} en {len(e.partes)}:"]
    for monto, comentario in e.partes:
        lineas.append(f"  • {pesos(monto)}" + (f" · {comentario}" if comentario else ""))
    return Respuesta("\n".join(lineas) + "\nLa conciliación ya puede encontrar cada parte por "
                     "separado. *deshacer* lo vuelve atrás.", "lote")
