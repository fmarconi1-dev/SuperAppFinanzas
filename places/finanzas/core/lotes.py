"""Lotes: propuesta → `ok` → todo o nada → `deshacer` (Fase D, ADR-0009 §6).

Un lote es lo que llega de una fuente y Franco confirma de una vez: hoy,
varios gastos en un mensaje; después, un extracto del banco o un resumen de
tarjeta. **Nada se escribe hasta el `ok`.** Al aplicar:

* **backup antes** y después **una sola transacción** (`BEGIN IMMEDIATE`):
  si algo falla a mitad, no queda nada escrito;
* cada fila tocada queda en `lote_operaciones` con cómo estaba **antes** y
  cómo quedó **después**.

`deshacer` revierte el lote entero, y solo si cada fila sigue igual que la
dejó el lote: si Franco editó o borró una desde la app, no toca nada y dice
cuál. Puro: sin red y sin Streamlit; `user_id` explícito (corre en el hilo
del servidor, donde los contextvars arrancan vacíos).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from core.db import backup_db
from places.finanzas.core.transactions import insertar_sin_backup

#: Una propuesta sin contestar deja de valer a las 48 h (Franco, 19/10/2026).
VIGENCIA_PROPUESTA = timedelta(hours=48)

#: Las columnas que se comparan para saber si una fila cambió desde el lote.
_COLUMNAS = ("fecha", "pasivos", "ingresos", "motivo", "comentario", "workspace_id")


class LoteNoDeshacible(Exception):
    """El lote no se puede revertir tal cual. El texto va a Franco."""


@dataclass
class Movimiento:
    """Una fila nueva de `transacciones`, ya decidida (categoría resuelta)."""

    fecha: date
    motivo: str
    pasivos: float = 0.0
    ingresos: float = 0.0
    comentario: Optional[str] = None
    #: La cuenta tal como la escribió Franco ("150000-25000*5") y su bruto.
    cuenta: Optional[str] = None
    bruto: Optional[float] = None


@dataclass
class Lote:
    id: int
    propuesta: dict
    creado_en: datetime


# ---------------------------------------------------------------------------
# Propuesta
# ---------------------------------------------------------------------------

def proponer(
    conn: sqlite3.Connection, *, workspace_id: int, user_id: int, origen: str,
    propuesta: dict, ahora: datetime,
) -> bool:
    """Guarda una propuesta nueva. True si había otra vigente (queda descartada).

    Hay una sola propuesta por espacio a la vez: la nueva reemplaza a la vieja.
    """
    habia = vigente(conn, workspace_id=workspace_id, ahora=ahora) is not None
    conn.execute(
        "UPDATE lotes SET estado = 'descartado' WHERE workspace_id = ? AND estado = 'propuesto'",
        (workspace_id,),
    )
    conn.execute(
        "INSERT INTO lotes (workspace_id, user_id, origen, estado, propuesta, creado_en) "
        "VALUES (?, ?, ?, 'propuesto', ?, ?)",
        (workspace_id, user_id, origen, json.dumps(propuesta), ahora.isoformat()),
    )
    return habia


def vigente(conn: sqlite3.Connection, *, workspace_id: int, ahora: datetime) -> Optional[Lote]:
    """La propuesta esperando respuesta, si no venció. Una vencida queda descartada."""
    row = conn.execute(
        "SELECT id, propuesta, creado_en FROM lotes "
        "WHERE workspace_id = ? AND estado = 'propuesto' ORDER BY id DESC LIMIT 1",
        (workspace_id,),
    ).fetchone()
    if row is None:
        return None
    creado = datetime.fromisoformat(row["creado_en"])
    if ahora - creado > VIGENCIA_PROPUESTA:
        descartar(conn, row["id"])
        return None
    return Lote(row["id"], json.loads(row["propuesta"]), creado)


def actualizar(conn: sqlite3.Connection, lote_id: int, propuesta: dict) -> None:
    conn.execute("UPDATE lotes SET propuesta = ? WHERE id = ? AND estado = 'propuesto'",
                 (json.dumps(propuesta), lote_id))


def descartar(conn: sqlite3.Connection, lote_id: int) -> None:
    conn.execute("UPDATE lotes SET estado = 'descartado' WHERE id = ? AND estado = 'propuesto'",
                 (lote_id,))


# ---------------------------------------------------------------------------
# Aplicar (todo o nada)
# ---------------------------------------------------------------------------

def _foto(conn: sqlite3.Connection, txn_id: int) -> Optional[dict]:
    row = conn.execute(
        f"SELECT {', '.join(_COLUMNAS)} FROM transacciones WHERE id = ?", (txn_id,)
    ).fetchone()
    return dict(row) if row else None


def aplicar(
    conn: sqlite3.Connection, lote_id: int, movimientos: list[Movimiento], *,
    user_id: int, ahora: datetime,
) -> list[int]:
    """Escribe los movimientos del lote: backup antes, todo o nada. Devuelve los ids."""
    if not movimientos:
        raise ValueError("Un lote sin movimientos no se aplica")
    backup_db()
    conn.execute("BEGIN IMMEDIATE")
    try:
        estado = conn.execute("SELECT estado FROM lotes WHERE id = ?", (lote_id,)).fetchone()
        if estado is None or estado["estado"] != "propuesto":
            raise ValueError(f"El lote {lote_id} no está esperando confirmación")
        ids = []
        for orden, m in enumerate(movimientos):
            txn_id = insertar_sin_backup(
                conn, m.fecha, m.motivo, pasivos=m.pasivos, ingresos=m.ingresos,
                comentario=m.comentario, user_id=user_id,
            )
            foto = _foto(conn, txn_id)
            if m.cuenta:
                conn.execute(
                    "INSERT INTO gasto_cuentas (transaccion_id, workspace_id, cuenta, bruto) "
                    "VALUES (?, ?, ?, ?)",
                    (txn_id, foto["workspace_id"], m.cuenta,
                     m.bruto if m.bruto is not None else m.pasivos or m.ingresos),
                )
            conn.execute(
                "INSERT INTO lote_operaciones (lote_id, orden, tabla, fila_id, accion, antes, "
                "despues) VALUES (?, ?, 'transacciones', ?, 'insert', NULL, ?)",
                (lote_id, orden, txn_id, json.dumps(foto)),
            )
            ids.append(txn_id)
        conn.execute(
            "UPDATE lotes SET estado = 'aplicado', aplicado_en = ? WHERE id = ?",
            (ahora.isoformat(), lote_id),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return ids


# ---------------------------------------------------------------------------
# Deshacer
# ---------------------------------------------------------------------------

def ultimo_aplicado(
    conn: sqlite3.Connection, *, workspace_id: int, desde: datetime
) -> Optional[tuple[int, datetime]]:
    """(id, aplicado_en) del último lote aplicado desde `desde`, o None."""
    rows = conn.execute(
        "SELECT id, aplicado_en FROM lotes WHERE workspace_id = ? AND estado = 'aplicado'",
        (workspace_id,),
    ).fetchall()
    # Se comparan fechas, no textos: un ISO con otra zona horaria ordenaría mal.
    candidatos = [(datetime.fromisoformat(r["aplicado_en"]), r["id"]) for r in rows]
    candidatos = [(c, i) for c, i in candidatos if c >= desde]
    if not candidatos:
        return None
    cuando, lote_id = max(candidatos)
    return lote_id, cuando


def deshacer(conn: sqlite3.Connection, lote_id: int, *, ahora: datetime) -> list[dict]:
    """Revierte el lote entero. Devuelve cómo eran las filas que borró.

    `LoteNoDeshacible` si alguna fila cambió o ya no está: en ese caso no se
    toca nada (deshacer a medias dejaría la base en un estado que nadie pidió).
    """
    ops = conn.execute(
        "SELECT tabla, fila_id, accion, antes, despues FROM lote_operaciones "
        "WHERE lote_id = ? ORDER BY orden DESC",
        (lote_id,),
    ).fetchall()
    for op in ops:
        actual = _foto(conn, op["fila_id"])
        if actual is None:
            raise LoteNoDeshacible(f"el #{op['fila_id']} ya no está (¿lo borraste desde la app?)")
        if actual != json.loads(op["despues"]):
            raise LoteNoDeshacible(f"el #{op['fila_id']} cambió desde que lo cargué")

    backup_db()
    conn.execute("BEGIN IMMEDIATE")
    try:
        borradas = []
        for op in ops:
            if op["accion"] == "insert":
                # `gasto_cuentas` se va solo (ON DELETE CASCADE).
                conn.execute("DELETE FROM transacciones WHERE id = ?", (op["fila_id"],))
                borradas.append({"id": op["fila_id"], **json.loads(op["despues"])})
            else:
                antes = json.loads(op["antes"])
                asignaciones = ", ".join(f"{c} = ?" for c in antes)
                conn.execute(f"UPDATE transacciones SET {asignaciones} WHERE id = ?",
                             (*antes.values(), op["fila_id"]))
        conn.execute(
            "UPDATE lotes SET estado = 'deshecho', deshecho_en = ? WHERE id = ?",
            (ahora.isoformat(), lote_id),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return list(reversed(borradas))
