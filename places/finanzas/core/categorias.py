"""CRUD de categorías + helpers para el editor de Configuración.

D2: operaciones aisladas por workspace (contextvar con fallback al
personal). `user_id` se conserva como autor. `core/categorizer.py` sigue
siendo lógica pura (DEFAULT_CATEGORIAS, efective_grupo).
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from core.auth.current_user import require_current_user_id
from core.db import backup_db
from core.workspaces import resolve_workspace_id


GRUPOS_EDITABLES = (
    "Ingreso",
    "Gasto Fijo",
    "Gasto Variable",
    "Inversion",
    "Sin categorizar",
)

MOTIVOS_PROTEGIDOS = frozenset({"Caja"})


def _uid(user_id: Optional[int]) -> int:
    return user_id if user_id is not None else require_current_user_id()


def update_categoria(
    conn: sqlite3.Connection,
    motivo: str,
    grupo: str,
    subcategoria: Optional[str],
    user_id: Optional[int] = None,
) -> None:
    """Actualiza grupo y subcategoría de un motivo del workspace activo."""
    wid = resolve_workspace_id(conn, _uid(user_id))
    if motivo in MOTIVOS_PROTEGIDOS:
        raise ValueError(f"El motivo '{motivo}' es protegido.")
    if grupo not in GRUPOS_EDITABLES:
        raise ValueError(
            f"Grupo '{grupo}' inválido. Permitidos: {', '.join(GRUPOS_EDITABLES)}"
        )

    cur = conn.execute(
        "UPDATE categorias SET grupo = ?, subcategoria = ? "
        "WHERE motivo = ? AND workspace_id = ?",
        (grupo, (subcategoria or None), motivo, wid),
    )
    if cur.rowcount == 0:
        raise LookupError(f"No existe categoría '{motivo}' en este espacio.")
    backup_db()


def delete_categoria(
    conn: sqlite3.Connection, motivo: str, user_id: Optional[int] = None
) -> None:
    """Borra categoría del workspace activo. Falla si hay transacciones usándola."""
    wid = resolve_workspace_id(conn, _uid(user_id))
    if motivo in MOTIVOS_PROTEGIDOS:
        raise ValueError(f"El motivo '{motivo}' es protegido y no se borra.")

    en_uso = conn.execute(
        "SELECT 1 FROM transacciones WHERE motivo = ? AND workspace_id = ? LIMIT 1",
        (motivo, wid),
    ).fetchone()
    if en_uso:
        raise ValueError(
            f"El motivo '{motivo}' está en uso. Borrá o reasigná las transacciones primero."
        )

    cur = conn.execute(
        "DELETE FROM categorias WHERE motivo = ? AND workspace_id = ?", (motivo, wid),
    )
    if cur.rowcount == 0:
        raise LookupError(f"No existe categoría '{motivo}' en este espacio.")
    backup_db()


def insert_categoria(
    conn: sqlite3.Connection,
    motivo: str,
    grupo: str = "Sin categorizar",
    subcategoria: Optional[str] = None,
    user_id: Optional[int] = None,
) -> None:
    """Crea categoría nueva en el workspace activo."""
    uid = _uid(user_id)
    wid = resolve_workspace_id(conn, uid)
    motivo = motivo.strip()
    if not motivo:
        raise ValueError("El motivo no puede estar vacío.")
    if grupo not in GRUPOS_EDITABLES:
        raise ValueError(
            f"Grupo '{grupo}' inválido. Permitidos: {', '.join(GRUPOS_EDITABLES)}"
        )

    ya_existe = conn.execute(
        "SELECT 1 FROM categorias WHERE motivo = ? AND workspace_id = ? LIMIT 1",
        (motivo, wid),
    ).fetchone()
    if ya_existe:
        raise ValueError(f"Ya existe una categoría con motivo '{motivo}' en este espacio.")

    conn.execute(
        "INSERT INTO categorias (motivo, grupo, subcategoria, user_id, workspace_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (motivo, grupo, (subcategoria or None), uid, wid),
    )
    backup_db()


def motivos_sin_uso(
    conn: sqlite3.Connection, user_id: Optional[int] = None
) -> list[str]:
    """Motivos del workspace activo sin transacciones asociadas (excluye protegidos)."""
    wid = resolve_workspace_id(conn, _uid(user_id))
    rows = conn.execute(
        """
        SELECT c.motivo
        FROM categorias c
        WHERE c.workspace_id = ?
          AND NOT EXISTS (
            SELECT 1 FROM transacciones t
            WHERE t.motivo = c.motivo AND t.workspace_id = c.workspace_id
          )
        ORDER BY c.motivo
        """,
        (wid,),
    ).fetchall()
    return [r["motivo"] for r in rows if r["motivo"] not in MOTIVOS_PROTEGIDOS]
