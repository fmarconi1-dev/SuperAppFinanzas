"""Contexto del usuario logueado — **re-export de `core/context.py`**.

El contextvar se mudó a `core/context.py` el 27/8/2026 para cortar el ciclo
`core ↔ core/auth` (y para que la lógica de negocio de Finanzas dejara de
arrastrar bcrypt solo por leer un entero). Ver el porqué completo allá.

Este módulo queda como fachada para no romper los imports que ya existían.
**Son los mismos objetos, no copias**: importar de acá o de `core.context` es
indistinto. Código nuevo: importá de `core.context`.
"""

from __future__ import annotations

from core.context import (  # noqa: F401
    get_current_user_id,
    require_current_user_id,
    set_current_user_id,
)

__all__ = ["set_current_user_id", "get_current_user_id",
           "require_current_user_id"]
