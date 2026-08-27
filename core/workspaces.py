"""Workspaces (grupo familiar D2): crear, unirse, salir, resolver el activo.

Modelo (definido en la migración M6 de core/db.py):
  - Cada usuario tiene un workspace `personal` (creado por backfill o acá).
  - Puede además crear/unirse a workspaces `familiar` compartidos, vía
    código de invitación (se guarda solo el hash SHA-256; el código en
    claro se muestra una única vez al crearlo).
  - Todos los miembros entran con role `admin` (multi-owner): cualquiera
    puede invitar o expulsar. `member_label` es una etiqueta cosmética
    de auditoría (quién cargó cada transacción), NO es autenticación.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from typing import Optional

from core.context import require_current_user_id
from core.context import get_current_workspace_id


# ---------------------------------------------------------------- helpers

def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def _uid(user_id: Optional[int]) -> int:
    return user_id if user_id is not None else require_current_user_id()


# ------------------------------------------------------------- resolución

def get_personal_workspace_id(
    conn: sqlite3.Connection, user_id: Optional[int] = None
) -> Optional[int]:
    """Id del workspace personal del usuario, o None si aún no existe."""
    uid = _uid(user_id)
    row = conn.execute(
        """
        SELECT w.id FROM workspaces w
        JOIN workspace_members wm ON wm.workspace_id = w.id
        WHERE wm.user_id = ? AND w.kind = 'personal'
        """,
        (uid,),
    ).fetchone()
    return row["id"] if row else None


def ensure_personal_workspace(
    conn: sqlite3.Connection, user_id: Optional[int] = None
) -> int:
    """Devuelve el workspace personal del usuario, creándolo si falta.

    Idempotente; replica la lógica del backfill M6 (incluye adoptar el
    saldo inicial y el fondo USD que hubiera en `configuracion`, y ligar
    las filas viejas sin workspace). Cubre DBs de test y usuarios nuevos.
    """
    uid = _uid(user_id)
    ws = get_personal_workspace_id(conn, uid)
    if ws is not None:
        return ws

    fila_u = conn.execute(
        "SELECT username, fullname FROM usuarios WHERE id = ?", (uid,)
    ).fetchone()
    nombre_visible = (fila_u["fullname"] or fila_u["username"]) if fila_u else f"usuario {uid}"

    def _cfg_float(clave: str) -> float:
        row = conn.execute(
            "SELECT valor FROM configuracion WHERE clave = ? AND user_id = ?",
            (clave, uid),
        ).fetchone()
        try:
            return float(row["valor"]) if row else 0.0
        except (ValueError, TypeError):
            return 0.0

    cur = conn.execute(
        "INSERT INTO workspaces (kind, nombre, saldo_inicial, fondo_usd) "
        "VALUES ('personal', ?, ?, ?)",
        (f"Personal de {nombre_visible}", _cfg_float("saldo_inicial_caja"),
         _cfg_float("fondo_emergencia_usd")),
    )
    ws_id = cur.lastrowid
    conn.execute(
        "INSERT INTO workspace_members (workspace_id, user_id, role, member_label) "
        "VALUES (?, ?, 'admin', ?)",
        (ws_id, uid, nombre_visible),
    )
    for tabla in ("transacciones", "categorias", "presupuesto", "configuracion"):
        conn.execute(
            f"UPDATE {tabla} SET workspace_id = ? "
            f"WHERE user_id = ? AND workspace_id IS NULL",
            (ws_id, uid),
        )
    return ws_id


def resolve_workspace_id(
    conn: sqlite3.Connection, user_id: Optional[int] = None
) -> int:
    """Workspace efectivo para las queries del dominio.

    1. Si hay workspace activo en contexto → ese.
    2. Si no → el personal del usuario (creándolo si falta).
    Con esto, sin switcher todo se comporta exactamente como pre-D2.
    """
    ws = get_current_workspace_id()
    if ws is not None:
        return ws
    return ensure_personal_workspace(conn, user_id)


# ------------------------------------------------------------ operaciones

def create_family_workspace(
    conn: sqlite3.Connection, nombre: str, user_id: Optional[int] = None
) -> tuple[int, str]:
    """Crea un workspace familiar. Devuelve (workspace_id, código en claro).

    El código solo se muestra esta vez; en DB queda el hash.
    """
    uid = _uid(user_id)
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El espacio compartido necesita un nombre")
    code = secrets.token_urlsafe(8)
    cur = conn.execute(
        "INSERT INTO workspaces (kind, nombre, invitation_code_hash) "
        "VALUES ('familiar', ?, ?)",
        (nombre, _hash_code(code)),
    )
    ws_id = cur.lastrowid
    conn.execute(
        "INSERT INTO workspace_members (workspace_id, user_id, role, member_label) "
        "VALUES (?, ?, 'admin', ?)",
        (ws_id, uid, _default_label(conn, uid)),
    )
    return ws_id, code


def join_family_workspace(
    conn: sqlite3.Connection,
    invitation_code: str,
    member_label: Optional[str] = None,
    user_id: Optional[int] = None,
) -> int:
    """Suma al usuario al workspace cuyo código coincida. Devuelve el id.

    Lanza LookupError si el código no matchea ningún workspace familiar,
    ValueError si ya es miembro o el label está tomado.
    """
    uid = _uid(user_id)
    row = conn.execute(
        "SELECT id FROM workspaces "
        "WHERE kind = 'familiar' AND invitation_code_hash = ?",
        (_hash_code(invitation_code or ""),),
    ).fetchone()
    if row is None:
        raise LookupError("Código de invitación inválido")
    ws_id = row["id"]

    ya = conn.execute(
        "SELECT 1 FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
        (ws_id, uid),
    ).fetchone()
    if ya:
        raise ValueError("Ya sos miembro de ese espacio")

    label = (member_label or "").strip() or _default_label(conn, uid)
    tomado = conn.execute(
        "SELECT 1 FROM workspace_members WHERE workspace_id = ? AND member_label = ?",
        (ws_id, label),
    ).fetchone()
    if tomado:
        raise ValueError(f"El nombre '{label}' ya está en uso en ese espacio")

    conn.execute(
        "INSERT INTO workspace_members (workspace_id, user_id, role, member_label) "
        "VALUES (?, ?, 'admin', ?)",
        (ws_id, uid, label),
    )
    return ws_id


def leave_family_workspace(
    conn: sqlite3.Connection, workspace_id: int, user_id: Optional[int] = None
) -> None:
    """Saca al usuario del workspace familiar. El workspace sobrevive si
    quedan miembros; si queda vacío, se elimina (CASCADE limpia members)."""
    uid = _uid(user_id)
    kind = conn.execute(
        "SELECT kind FROM workspaces WHERE id = ?", (workspace_id,)
    ).fetchone()
    if kind is None or kind["kind"] != "familiar":
        raise ValueError("Solo se puede salir de espacios familiares")
    cur = conn.execute(
        "DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
        (workspace_id, uid),
    )
    if cur.rowcount == 0:
        raise LookupError("No sos miembro de ese espacio")
    quedan = conn.execute(
        "SELECT COUNT(*) AS n FROM workspace_members WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchone()["n"]
    if quedan == 0:
        conn.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))


def list_user_workspaces(
    conn: sqlite3.Connection, user_id: Optional[int] = None
) -> list[dict]:
    """Workspaces del usuario (el personal primero), con su member_label."""
    uid = _uid(user_id)
    ensure_personal_workspace(conn, uid)
    rows = conn.execute(
        """
        SELECT w.id, w.kind, w.nombre, wm.member_label,
               (SELECT COUNT(*) FROM workspace_members x
                 WHERE x.workspace_id = w.id) AS miembros
        FROM workspaces w
        JOIN workspace_members wm ON wm.workspace_id = w.id
        WHERE wm.user_id = ?
        ORDER BY (w.kind != 'personal'), w.nombre
        """,
        (uid,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_members(conn: sqlite3.Connection, workspace_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT user_id, member_label, role, joined_en "
        "FROM workspace_members WHERE workspace_id = ? ORDER BY joined_en",
        (workspace_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def member_label_of(
    conn: sqlite3.Connection, workspace_id: int, user_id: Optional[int] = None
) -> Optional[str]:
    uid = _uid(user_id)
    row = conn.execute(
        "SELECT member_label FROM workspace_members "
        "WHERE workspace_id = ? AND user_id = ?",
        (workspace_id, uid),
    ).fetchone()
    return row["member_label"] if row else None


def _default_label(conn: sqlite3.Connection, uid: int) -> str:
    fila = conn.execute(
        "SELECT username, fullname FROM usuarios WHERE id = ?", (uid,)
    ).fetchone()
    return (fila["fullname"] or fila["username"]) if fila else f"usuario {uid}"
