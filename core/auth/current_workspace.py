"""Contexto del workspace activo (grupo familiar D2).

Espejo del patrón de `current_user.py`: `st.session_state` decide qué
workspace está activo y `app.py` lo baja al contextvar en cada rerun.
Las queries del dominio filtran por workspace, no por usuario.

Si NO hay workspace en contexto, las queries resuelven el workspace
personal del usuario activo (comportamiento idéntico al pre-D2 gracias
al invariante del backfill D1).

Riesgo premortem #5 (callbacks sin contextvar): los callbacks de
Streamlit deben pasar `workspace_id` explícito desde session_state,
no confiar en este contextvar.
"""

from __future__ import annotations

import contextvars
from typing import Optional

_current_workspace_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "current_workspace_id", default=None
)


def set_current_workspace_id(workspace_id: Optional[int]) -> None:
    _current_workspace_id.set(workspace_id)


def get_current_workspace_id() -> Optional[int]:
    return _current_workspace_id.get()
