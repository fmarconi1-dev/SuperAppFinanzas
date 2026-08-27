"""`core/context.py`: el contexto de ejecución, sin ciclo y sin peso de más.

Estos tests no protegen un cálculo: protegen una **forma del grafo de
imports**. Es la clase de propiedad que se rompe sola cuando alguien agrega un
import "chiquito" y nadie se entera hasta que un día el orden de carga cambia y
revienta en producción.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from core import context
from core.auth import current_user as fachada_user
from core.auth import current_workspace as fachada_ws


def _en_proceso_limpio(codigo: str) -> str:
    """Corre `codigo` en un intérprete nuevo y devuelve su stdout.

    Hace falta un proceso aparte: `sys.modules` ya tiene medio proyecto
    cargado por los otros tests, así que medir "qué arrastra este import"
    dentro de la misma corrida daría siempre que no arrastra nada.
    """
    r = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(codigo)],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


# ---------------------------------------------------------------------------
# La forma del grafo
# ---------------------------------------------------------------------------

def test_context_no_importa_nada_del_proyecto():
    """**La regla del módulo.** Si `core/context.py` importa algo de `core/`,
    vuelve a existir el ciclo que vino a cortar."""
    salida = _en_proceso_limpio("""
        import sys
        antes = set(sys.modules)
        import core.context
        nuevos = set(sys.modules) - antes
        propios = [m for m in nuevos
                   if m.startswith(('core.', 'places.')) and m != 'core.context']
        print(','.join(sorted(propios)))
    """)
    assert salida == "", f"core/context.py arrastra módulos del proyecto: {salida}"


def test_core_db_ya_no_depende_de_auth():
    """El ciclo era `core.db → core.auth.current_user` contra
    `core.auth.login → core.db`. Este test es el que lo mantiene cortado."""
    salida = _en_proceso_limpio("""
        import sys
        antes = set(sys.modules)
        import core.db
        nuevos = set(sys.modules) - antes
        print(','.join(sorted(m for m in nuevos if m.startswith('core.auth'))))
    """)
    assert salida == "", f"core.db volvió a arrastrar auth: {salida}"


def test_la_logica_de_finanzas_no_arrastra_bcrypt():
    """`places/finanzas/core/` es lógica pura por diseño. Cargar una librería
    de criptografía para leer un entero de un contextvar era el síntoma."""
    salida = _en_proceso_limpio("""
        import sys
        antes = set(sys.modules)
        import places.finanzas.core.metrics
        print('bcrypt' if 'bcrypt' in set(sys.modules) - antes else '')
    """)
    assert salida == "", "places/finanzas/core/metrics.py volvió a arrastrar bcrypt"


# ---------------------------------------------------------------------------
# Las fachadas: el mismo objeto, no una copia
# ---------------------------------------------------------------------------
#
# Si cada módulo definiera su propio ContextVar, `set()` por una puerta y
# `get()` por la otra devolverían cosas distintas — y el bug sería invisible
# hasta que alguien mezclara los imports en el mismo flujo.

def test_la_fachada_de_usuario_es_el_mismo_contextvar():
    context.set_current_user_id(42)
    assert fachada_user.get_current_user_id() == 42
    assert fachada_user.require_current_user_id() == 42
    context.set_current_user_id(None)


def test_y_al_reves_tambien():
    fachada_user.set_current_user_id(7)
    assert context.get_current_user_id() == 7
    context.set_current_user_id(None)


def test_la_fachada_de_workspace_es_el_mismo_contextvar():
    context.set_current_workspace_id(3)
    assert fachada_ws.get_current_workspace_id() == 3
    fachada_ws.set_current_workspace_id(9)
    assert context.get_current_workspace_id() == 9
    context.set_current_workspace_id(None)


def test_las_funciones_son_literalmente_las_mismas():
    assert fachada_user.set_current_user_id is context.set_current_user_id
    assert fachada_user.get_current_user_id is context.get_current_user_id
    assert fachada_ws.get_current_workspace_id is context.get_current_workspace_id


# ---------------------------------------------------------------------------
# Comportamiento
# ---------------------------------------------------------------------------

def test_sin_usuario_require_explota_en_vez_de_devolver_none():
    """Devolver `None` en silencio dejaría queries leyendo filas de nadie."""
    context.set_current_user_id(None)
    with pytest.raises(RuntimeError, match="No hay usuario activo"):
        context.require_current_user_id()


def test_sin_workspace_get_devuelve_none_y_esta_bien():
    """``None`` es un estado válido: las queries caen al espacio personal."""
    context.set_current_workspace_id(None)
    assert context.get_current_workspace_id() is None
