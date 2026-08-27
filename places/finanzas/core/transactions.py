"""CRUD de transacciones + hook de backup automático.

D2 (grupo familiar): todas las lecturas y modificaciones filtran por
`workspace_id` (resuelto desde el contextvar de workspace, con fallback
al workspace personal del usuario — comportamiento pre-D2 intacto).
`user_id` se conserva en cada fila como autor. En workspaces familiares
se registra además `creado_por_member_label` (etiqueta cosmética de
auditoría, no autenticación).
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from core.context import require_current_user_id
from core.db import backup_db
from core.workspaces import member_label_of, resolve_workspace_id


def _uid(user_id: Optional[int]) -> int:
    return user_id if user_id is not None else require_current_user_id()


def _es_familiar(conn: sqlite3.Connection, workspace_id: int) -> bool:
    row = conn.execute(
        "SELECT kind FROM workspaces WHERE id = ?", (workspace_id,)
    ).fetchone()
    return bool(row) and row["kind"] == "familiar"


def _asegurar_motivo(
    conn: sqlite3.Connection, motivo: str, uid: int, wid: int
) -> None:
    """Crea el motivo en `categorias` si no existe en el workspace."""
    conn.execute(
        "INSERT INTO categorias (motivo, grupo, user_id, workspace_id) "
        "SELECT ?, 'Sin categorizar', ?, ? "
        "WHERE NOT EXISTS (SELECT 1 FROM categorias WHERE motivo = ? AND workspace_id = ?)",
        (motivo, uid, wid, motivo, wid),
    )


def insert_transaction(
    conn: sqlite3.Connection,
    fecha: date,
    motivo: str,
    pasivos: float = 0.0,
    ingresos: float = 0.0,
    comentario: Optional[str] = None,
    user_id: Optional[int] = None,
    member_label: Optional[str] = None,
) -> int:
    """Inserta una transacción en el workspace activo. Devuelve el id.

    En workspaces familiares guarda `creado_por_member_label` ("firmar
    como"): el `member_label` recibido, o la etiqueta del usuario en ese
    workspace si no se pasó ninguna.
    """
    uid = _uid(user_id)
    wid = resolve_workspace_id(conn, uid)
    motivo = motivo.strip()
    if not motivo:
        raise ValueError("El motivo no puede estar vacío")
    if pasivos < 0 and ingresos < 0:
        raise ValueError("No tiene sentido negativo en pasivos e ingresos a la vez")

    _asegurar_motivo(conn, motivo, uid, wid)

    label = None
    if _es_familiar(conn, wid):
        label = (member_label or "").strip() or member_label_of(conn, wid, uid)

    cur = conn.execute(
        "INSERT INTO transacciones "
        "(fecha, pasivos, ingresos, motivo, comentario, user_id, workspace_id, "
        " creado_por_member_label) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (fecha.isoformat(), float(pasivos), float(ingresos), motivo, comentario,
         uid, wid, label),
    )
    new_id = cur.lastrowid
    backup_db()
    return new_id


def update_transaction(
    conn: sqlite3.Connection,
    txn_id: int,
    fecha: date,
    motivo: str,
    pasivos: float = 0.0,
    ingresos: float = 0.0,
    comentario: Optional[str] = None,
    user_id: Optional[int] = None,
) -> None:
    """Edita una transacción existente del workspace activo."""
    uid = _uid(user_id)
    wid = resolve_workspace_id(conn, uid)
    motivo = motivo.strip()
    if not motivo:
        raise ValueError("El motivo no puede estar vacío")

    _asegurar_motivo(conn, motivo, uid, wid)

    cur = conn.execute(
        "UPDATE transacciones SET fecha = ?, motivo = ?, pasivos = ?, ingresos = ?, "
        "comentario = ? WHERE id = ? AND workspace_id = ?",
        (fecha.isoformat(), motivo, float(pasivos), float(ingresos), comentario,
         txn_id, wid),
    )
    if cur.rowcount == 0:
        raise LookupError(f"No existe transacción con id={txn_id} en este espacio")
    backup_db()


def delete_transaction(
    conn: sqlite3.Connection, txn_id: int, user_id: Optional[int] = None
) -> None:
    wid = resolve_workspace_id(conn, _uid(user_id))
    cur = conn.execute(
        "DELETE FROM transacciones WHERE id = ? AND workspace_id = ?", (txn_id, wid),
    )
    if cur.rowcount == 0:
        raise LookupError(f"No existe transacción con id={txn_id} en este espacio")
    backup_db()


def get_transaction(
    conn: sqlite3.Connection, txn_id: int, user_id: Optional[int] = None
) -> Optional[dict]:
    wid = resolve_workspace_id(conn, _uid(user_id))
    row = conn.execute(
        "SELECT id, fecha, pasivos, ingresos, motivo, comentario, "
        "creado_por_member_label "
        "FROM transacciones WHERE id = ? AND workspace_id = ?",
        (txn_id, wid),
    ).fetchone()
    return dict(row) if row else None


def list_recent(
    conn: sqlite3.Connection, n: int = 20, user_id: Optional[int] = None
) -> list[dict]:
    """Últimas N transacciones del workspace activo."""
    wid = resolve_workspace_id(conn, _uid(user_id))
    rows = conn.execute(
        "SELECT id, fecha, pasivos, ingresos, motivo, comentario, "
        "creado_por_member_label "
        "FROM transacciones WHERE workspace_id = ? ORDER BY fecha DESC, id DESC LIMIT ?",
        (wid, n),
    ).fetchall()
    return [dict(r) for r in rows]


def all_motivos(conn: sqlite3.Connection, user_id: Optional[int] = None) -> list[str]:
    """Motivos del workspace en categorias + en transacciones (sin 'Caja')."""
    wid = resolve_workspace_id(conn, _uid(user_id))
    rows = conn.execute(
        "SELECT motivo FROM categorias WHERE workspace_id = ? "
        "UNION "
        "SELECT DISTINCT motivo FROM transacciones WHERE workspace_id = ? "
        "ORDER BY motivo",
        (wid, wid),
    ).fetchall()
    return [r["motivo"] for r in rows if r["motivo"] and r["motivo"] != "Caja"]


def motivos_recientes(
    conn: sqlite3.Connection,
    n: int = 6,
    dias: int = 60,
    user_id: Optional[int] = None,
) -> list[str]:
    """Motivos más usados en el workspace en los últimos `dias` días.

    Ordenados por frecuencia desc, con desempate por uso más reciente.
    Pensado para los chips de "atajos" en alta rápida.
    """
    wid = resolve_workspace_id(conn, _uid(user_id))
    rows = conn.execute(
        """
        SELECT motivo, COUNT(*) AS cnt, MAX(fecha) AS ultimo
        FROM transacciones
        WHERE workspace_id = ?
          AND date(fecha) >= date('now', ?)
          AND motivo != 'Caja'
        GROUP BY motivo
        ORDER BY cnt DESC, ultimo DESC
        LIMIT ?
        """,
        (wid, f"-{int(dias)} days", int(n)),
    ).fetchall()
    return [r["motivo"] for r in rows]


def montos_frecuentes_por_motivo(
    conn: sqlite3.Connection,
    motivo: Optional[str] = None,
    n: int = 4,
    dias: int = 90,
    user_id: Optional[int] = None,
) -> list[float]:
    """Montos más recurrentes en los últimos `dias` días.

    - Si `motivo` es None: agregado global (útil cuando todavía no se eligió motivo).
    - Si `motivo` es un motivo concreto: filtra por ese motivo.

    Cada transacción aporta `pasivos` (si > 0) o `ingresos` (si > 0). Se
    descartan los 0 y duplicados que sean idénticos al céntimo.
    """
    wid = resolve_workspace_id(conn, _uid(user_id))
    params: list = [wid, f"-{int(dias)} days"]
    where_motivo = ""
    if motivo:
        where_motivo = "AND motivo = ?"
        params.append(motivo)
    params.append(int(n))

    rows = conn.execute(
        f"""
        SELECT monto, COUNT(*) AS cnt
        FROM (
            SELECT CASE
                       WHEN pasivos  > 0 THEN ROUND(pasivos, 2)
                       WHEN ingresos > 0 THEN ROUND(ingresos, 2)
                       ELSE NULL
                   END AS monto
            FROM transacciones
            WHERE workspace_id = ?
              AND date(fecha) >= date('now', ?)
              {where_motivo}
        )
        WHERE monto IS NOT NULL AND monto > 0
        GROUP BY monto
        ORDER BY cnt DESC, monto DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [float(r["monto"]) for r in rows]
