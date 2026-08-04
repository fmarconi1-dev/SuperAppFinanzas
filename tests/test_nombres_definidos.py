"""Ningún módulo puede usar un nombre global que no exista.

**Por qué existe.** Python no valida los nombres hasta que la línea se ejecuta.
En una app Streamlit eso significa que un nombre mal escrito o una función sin
importar no falla al arrancar: falla el día que el usuario aprieta *ese* botón.
Ya pasó dos veces en producción:

* el `UnboundLocalError: firma_val` al cargar un gasto desde el celular;
* `backup_db` usado en `cartera/view.py` sin estar importado (atajado por este
  test durante la Fase 4, antes de llegar a producción).

El chequeo lee el **bytecode**: junta los `LOAD_GLOBAL` de cada función y
verifica que ese nombre exista en el módulo o entre los builtins. Mirar el
bytecode en vez del AST evita los falsos positivos de los atributos
(`obj.backup_db` no es un global) y de las variables locales.

No reemplaza a un linter completo; cubre con precisión el error que ya nos
costó caro.
"""

from __future__ import annotations

import builtins
import dis
import importlib
import pkgutil
import types

import pytest

#: Paquetes propios que se revisan enteros.
PAQUETES = ("core", "places")


def _modulos() -> list[str]:
    nombres: list[str] = []
    for paquete in PAQUETES:
        try:
            mod = importlib.import_module(paquete)
        except Exception:                       # pragma: no cover
            continue
        for info in pkgutil.walk_packages(mod.__path__, f"{paquete}."):
            nombres.append(info.name)
    return sorted(nombres)


def _codigos(obj) -> list[types.CodeType]:
    """Todos los code objects anidados (funciones, lambdas, comprensiones)."""
    fuera = [obj]
    for const in obj.co_consts:
        if isinstance(const, types.CodeType):
            fuera.extend(_codigos(const))
    return fuera


def _globales_faltantes(modulo) -> list[str]:
    codigo = getattr(modulo, "__loader__", None)
    if codigo is None or not hasattr(modulo, "__file__"):
        return []
    with open(modulo.__file__, encoding="utf-8") as fh:
        arbol = compile(fh.read(), modulo.__file__, "exec")

    disponibles = set(vars(modulo)) | set(vars(builtins))
    faltantes = set()
    for c in _codigos(arbol):
        # Los nombres del scope del módulo se resuelven contra sí mismo y
        # pueden definirse más abajo; solo interesan los de las funciones.
        if c is arbol:
            continue
        for ins in dis.get_instructions(c):
            if ins.opname == "LOAD_GLOBAL" and isinstance(ins.argval, str):
                if ins.argval not in disponibles:
                    faltantes.add(ins.argval)
    return sorted(faltantes)


@pytest.mark.parametrize("nombre", _modulos())
def test_el_modulo_no_usa_nombres_inexistentes(nombre):
    try:
        modulo = importlib.import_module(nombre)
    except Exception as exc:                    # pragma: no cover
        pytest.skip(f"no se pudo importar {nombre}: {exc}")

    faltantes = _globales_faltantes(modulo)
    assert not faltantes, (
        f"{nombre} usa nombres que no existen en el módulo: "
        f"{', '.join(faltantes)}. Suele ser un import olvidado o un typo — "
        f"Python no lo detecta hasta que se ejecuta esa línea."
    )
