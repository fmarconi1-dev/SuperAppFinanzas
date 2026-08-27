"""Contexto del workspace activo (D2) — **re-export de `core/context.py`**.

Mudado el 27/8/2026 junto con `current_user`. Ver `core/context.py` para el
motivo y para la trampa de los callbacks de Streamlit (premortem #5).

Fachada de compatibilidad: son los mismos objetos, no copias. Código nuevo:
importá de `core.context`.
"""

from __future__ import annotations

from core.context import (  # noqa: F401
    get_current_workspace_id,
    set_current_workspace_id,
)

__all__ = ["set_current_workspace_id", "get_current_workspace_id"]
