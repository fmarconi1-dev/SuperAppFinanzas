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
# Operaciones de un lote
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ref:
    """El id de una fila insertada antes en el mismo lote (por su `clave`)."""

    clave: str


@dataclass
class InsertarMovimiento:
    """Una fila nueva de `transacciones` (con su bruto, si tiene cuenta)."""

    mov: Movimiento
    clave: Optional[str] = None


@dataclass
class Insertar:
    """Una fila nueva en otra tabla del lote. Los valores pueden ser `Ref`."""

    tabla: str
    valores: dict
    clave: Optional[str] = None


@dataclass
class Actualizar:
    """Cambiar columnas de una fila que ya existe (se guarda cómo estaba)."""

    tabla: str
    fila_id: "int | Ref"
    cambios: dict


#: Las tablas que un lote puede tocar. Toda otra se rechaza: el nombre de la
#: tabla va en el SQL y no puede venir de afuera.
TABLAS = {"transacciones", "banco_filas", "emparejamientos", "reglas_comercio",
          "reglas_tipo", "saldos_declarados"}


@dataclass
class Deshecho:
    """Lo que revirtió `deshacer`."""

    #: Los gastos e ingresos que el lote había cargado, como estaban.
    borradas: list[dict]
    #: Cuántos gastos que ya existían volvieron a como estaban antes del lote.
    restauradas: int


# ---------------------------------------------------------------------------
# Aplicar (todo o nada)
# ---------------------------------------------------------------------------

def _foto(conn: sqlite3.Connection, txn_id: int) -> Optional[dict]:
    row = conn.execute(
        f"SELECT {', '.join(_COLUMNAS)} FROM transacciones WHERE id = ?", (txn_id,)
    ).fetchone()
    return dict(row) if row else None


def _tabla(tabla: str) -> str:
    if tabla not in TABLAS:
        raise ValueError(f"Un lote no puede tocar la tabla {tabla!r}")
    return tabla


def _fila(conn: sqlite3.Connection, tabla: str, fila_id: int) -> Optional[dict]:
    row = conn.execute(f"SELECT * FROM {_tabla(tabla)} WHERE id = ?", (fila_id,)).fetchone()
    return dict(row) if row else None


def aplicar(
    conn: sqlite3.Connection, lote_id: int, movimientos: list[Movimiento], *,
    user_id: int, ahora: datetime,
) -> list[int]:
    """Escribe los movimientos del lote: backup antes, todo o nada. Devuelve los ids."""
    if not movimientos:
        raise ValueError("Un lote sin movimientos no se aplica")
    claves = aplicar_operaciones(
        conn, lote_id, [InsertarMovimiento(m, clave=f"m{i}") for i, m in enumerate(movimientos)],
        user_id=user_id, ahora=ahora)
    return [claves[f"m{i}"] for i in range(len(movimientos))]


def aplicar_operaciones(
    conn: sqlite3.Connection, lote_id: int, operaciones: list, *, user_id: int, ahora: datetime,
) -> dict[str, int]:
    """Aplica las operaciones en orden: backup antes, todo o nada.

    Devuelve el id de cada fila insertada con `clave`. Cada operación queda en
    `lote_operaciones` con el antes y el después, para `deshacer`.
    """
    backup_db()
    conn.execute("BEGIN IMMEDIATE")
    try:
        estado = conn.execute("SELECT estado FROM lotes WHERE id = ?", (lote_id,)).fetchone()
        if estado is None or estado["estado"] != "propuesto":
            raise ValueError(f"El lote {lote_id} no está esperando confirmación")
        claves: dict[str, int] = {}

        def resolver(v):
            return claves[v.clave] if isinstance(v, Ref) else v

        for orden, op in enumerate(operaciones):
            if isinstance(op, InsertarMovimiento):
                m = op.mov
                fila_id = insertar_sin_backup(
                    conn, m.fecha, m.motivo, pasivos=m.pasivos, ingresos=m.ingresos,
                    comentario=m.comentario, user_id=user_id,
                )
                despues = _foto(conn, fila_id)
                if m.cuenta:
                    conn.execute(
                        "INSERT INTO gasto_cuentas (transaccion_id, workspace_id, cuenta, bruto) "
                        "VALUES (?, ?, ?, ?)",
                        (fila_id, despues["workspace_id"], m.cuenta,
                         m.bruto if m.bruto is not None else m.pasivos or m.ingresos),
                    )
                tabla, accion, antes = "transacciones", "insert", None
            elif isinstance(op, Insertar):
                tabla, accion, antes = _tabla(op.tabla), "insert", None
                valores = {k: resolver(v) for k, v in op.valores.items()}
                cur = conn.execute(
                    f"INSERT INTO {tabla} ({', '.join(valores)}) "
                    f"VALUES ({', '.join('?' for _ in valores)})",
                    tuple(valores.values()),
                )
                fila_id = cur.lastrowid
                despues = _fila(conn, tabla, fila_id)
            elif isinstance(op, Actualizar):
                tabla, accion = _tabla(op.tabla), "update"
                fila_id = resolver(op.fila_id)
                previa = _fila(conn, tabla, fila_id)
                if previa is None:
                    raise ValueError(f"No existe la fila {fila_id} de {tabla}")
                cambios = {k: resolver(v) for k, v in op.cambios.items()}
                antes = {k: previa[k] for k in cambios}
                conn.execute(
                    f"UPDATE {tabla} SET {', '.join(f'{c} = ?' for c in cambios)} WHERE id = ?",
                    (*cambios.values(), fila_id),
                )
                despues = (_foto(conn, fila_id) if tabla == "transacciones"
                           else _fila(conn, tabla, fila_id))
            else:
                raise TypeError(f"Operación desconocida: {op!r}")
            if getattr(op, "clave", None):
                claves[op.clave] = fila_id
            conn.execute(
                "INSERT INTO lote_operaciones (lote_id, orden, tabla, fila_id, accion, antes, "
                "despues) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (lote_id, orden, tabla, fila_id, accion,
                 json.dumps(antes) if antes is not None else None, json.dumps(despues)),
            )
        conn.execute(
            "UPDATE lotes SET estado = 'aplicado', aplicado_en = ? WHERE id = ?",
            (ahora.isoformat(), lote_id),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return claves


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


def deshacer(conn: sqlite3.Connection, lote_id: int, *, ahora: datetime) -> Deshecho:
    """Revierte el lote entero, de la última operación a la primera.

    Los gastos (`transacciones`) que tocó tienen que estar **igual** que como
    los dejó el lote: si Franco editó o borró uno desde la app, `LoteNoDeshacible`
    y no se toca nada (deshacer a medias dejaría la base en un estado que nadie
    pidió). Las demás tablas son del Secretario y se revierten sin chequeo.
    """
    ops = conn.execute(
        "SELECT tabla, fila_id, accion, antes, despues FROM lote_operaciones "
        "WHERE lote_id = ? ORDER BY orden DESC",
        (lote_id,),
    ).fetchall()
    for op in ops:
        if op["tabla"] != "transacciones":
            continue
        actual = _foto(conn, op["fila_id"])
        if actual is None:
            raise LoteNoDeshacible(f"el #{op['fila_id']} ya no está (¿lo borraste desde la app?)")
        if actual != json.loads(op["despues"]):
            raise LoteNoDeshacible(f"el #{op['fila_id']} cambió desde que lo cargué")

    backup_db()
    conn.execute("BEGIN IMMEDIATE")
    try:
        borradas, restauradas = [], 0
        for op in ops:
            tabla = _tabla(op["tabla"])
            if op["accion"] == "insert":
                # `gasto_cuentas` y los vínculos de un gasto se van solos (ON DELETE CASCADE).
                conn.execute(f"DELETE FROM {tabla} WHERE id = ?", (op["fila_id"],))
                if tabla == "transacciones":
                    borradas.append({"id": op["fila_id"], **json.loads(op["despues"])})
            else:
                antes = json.loads(op["antes"])
                conn.execute(f"UPDATE {tabla} SET {', '.join(f'{c} = ?' for c in antes)} "
                             "WHERE id = ?", (*antes.values(), op["fila_id"]))
                restauradas += tabla == "transacciones"
        conn.execute(
            "UPDATE lotes SET estado = 'deshecho', deshecho_en = ? WHERE id = ?",
            (ahora.isoformat(), lote_id),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return Deshecho(list(reversed(borradas)), restauradas)
