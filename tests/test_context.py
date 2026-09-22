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
from pathlib import Path

from core import context

# ⚠️ Las fachadas se importan **dentro** de cada test, no acá arriba.
#
# `core/auth/current_user.py` dispara el `__init__.py` del paquete, que importa
# bcrypt. Con un import a nivel de módulo, un intérprete sin dependencias
# (correr la suite con el Python del sistema en vez del venv es un error fácil:
# está anotado como trampa en el prompt de inicio) tumba la **colección** del
# archivo entero — y con ella los tres tests de arriba, que miden el grafo de
# imports, no necesitan bcrypt, y son justamente la red que sostiene este
# refactor. Importándolas adentro, esos tres corren igual.


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
# Una sola fuente del contextvar
# ---------------------------------------------------------------------------
#
# Hasta el 22/9/2026 existían `core/auth/current_user.py` y
# `current_workspace.py` como fachadas que re-exportaban estos objetos. Ya
# nadie las importaba en producción y se borraron. Lo que importa es el
# invariante que protegían: si otro módulo definiera su propio ContextVar,
# `set()` por una puerta y `get()` por la otra devolverían cosas distintas —
# y el bug sería invisible hasta que alguien mezclara los imports.

def test_nadie_mas_define_un_contextvar_de_usuario_o_workspace():
    raiz = Path(__file__).resolve().parents[1]
    culpables = [
        str(p.relative_to(raiz))
        for carpeta in ("core", "places")
        for p in (raiz / carpeta).rglob("*.py")
        if p.name != "context.py" and "ContextVar(" in p.read_text(encoding="utf-8")
    ]
    assert culpables == [], f"ContextVar fuera de core/context.py: {culpables}"


def test_las_fachadas_viejas_no_vuelven():
    with pytest.raises(ModuleNotFoundError):
        __import__("core.auth.current_user")
    with pytest.raises(ModuleNotFoundError):
        __import__("core.auth.current_workspace")


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
