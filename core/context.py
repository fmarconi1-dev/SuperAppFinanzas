"""Quién está usando la app, ahora mismo: usuario y workspace activos.

**Por qué este módulo existe y por qué no importa nada.**

Los contextvars nacieron dentro de `core/auth/` porque el usuario activo es un
concepto de autenticación. Pero terminaron siendo consultados por todo el
dominio —`core/db.py`, `core/workspaces.py`, y los seis módulos de lógica de
Finanzas— y eso dejó dos problemas:

1. **Un ciclo de imports.** `core/db.py` importaba `core.auth.current_user`,
   y `core/auth/login.py` importa `core.db`. Python lo tolera por el orden en
   que se resuelven, pero es la clase de dependencia circular que revienta el
   día que alguien mueve un import de lugar.

2. **Peso de más, donde menos corresponde.** Importar `core.auth.current_user`
   dispara el `__init__.py` del paquete (`from core.auth.auth import *`), que
   trae **bcrypt**. Así, `places/finanzas/core/metrics.py` —lógica de negocio
   pura, sin Streamlit por diseño— cargaba una librería de criptografía nada
   más que para leer un entero de un contextvar.

La solución es que el dato viva en un módulo **neutral**: saber quién es el
usuario activo no es autenticación (eso ya pasó), es contexto de ejecución.

> **Regla de este archivo: no importa nada del proyecto.** Solo stdlib. En el
> momento en que `core/context.py` importe otra cosa de `core/`, vuelve a
> existir el ciclo que vino a cortar.

`core/auth/current_user.py` y `core/auth/current_workspace.py` siguen
existiendo como **re-exports** de estos mismos objetos, así que el código que
ya los importaba sigue andando sin cambios. Es el mismo contextvar, no una
copia: si fueran dos, `set()` en uno y `get()` en el otro devolverían cosas
distintas y el bug sería invisible hasta que alguien mezclara los imports.

---

**Trampa heredada, sigue vigente (premortem #5).** Los callbacks de Streamlit
corren en un contexto distinto del rerun que los registró: **no confíes en
estos contextvars adentro de un callback**. Pasá `user_id`/`workspace_id`
explícitos desde `session_state`.
"""

from __future__ import annotations

import contextvars
from typing import Optional

__all__ = [
    "set_current_user_id", "get_current_user_id", "require_current_user_id",
    "set_current_workspace_id", "get_current_workspace_id",
]

_current_user_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "current_user_id", default=None
)

_current_workspace_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "current_workspace_id", default=None
)


# ---------------------------------------------------------------------------
# Usuario activo
# ---------------------------------------------------------------------------

def set_current_user_id(user_id: Optional[int]) -> None:
    """Lo baja `app.py` en cada rerun, después del login."""
    _current_user_id.set(user_id)


def get_current_user_id() -> Optional[int]:
    return _current_user_id.get()


def require_current_user_id() -> int:
    """El usuario activo, o `RuntimeError` si no hay.

    Lo usan las queries que **no pueden** correr sin dueño: devolver `None`
    silenciosamente las dejaría leyendo o escribiendo filas de nadie.
    """
    uid = _current_user_id.get()
    if uid is None:
        raise RuntimeError(
            "No hay usuario activo en el contexto. ¿Olvidaste llamar a "
            "set_current_user_id() después del login?"
        )
    return uid


# ---------------------------------------------------------------------------
# Workspace activo (grupo familiar, D2)
# ---------------------------------------------------------------------------

def set_current_workspace_id(workspace_id: Optional[int]) -> None:
    _current_workspace_id.set(workspace_id)


def get_current_workspace_id() -> Optional[int]:
    """El workspace activo, o ``None``.

    ``None`` es un estado **válido**, no un error: las queries resuelven
    entonces el espacio personal del usuario activo, que es el comportamiento
    idéntico al de antes de D2 gracias al invariante del backfill D1.
    """
    return _current_workspace_id.get()
