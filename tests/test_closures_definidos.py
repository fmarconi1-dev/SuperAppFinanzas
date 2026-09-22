"""Una función anidada no puede usarse antes de que exista lo que lee.

**Por qué existe.** Es el primo de `test_nombres_definidos.py`, que mira los
nombres *globales*. Este mira las variables de la función que encierra
(*free variables*): Python las resuelve recién cuando la función anidada se
ejecuta, así que usarla antes de la asignación no falla al importar — falla
el día que se ejecuta esa rama.

Pasó en `cartera/view.py` (22/9/2026): `_resolver` leía `fecha_val`, se le
pasaba a `valuar()` en una línea y `fecha_val` se asignaba nueve líneas más
abajo. Con una tasa devengada cargada, la pantalla de Cartera entera moría con
``NameError: cannot access free variable 'fecha_val'``. Estuvo latente dos
meses porque ningún test cargaba una tasa.

El chequeo es por AST y no importa nada: para cada función anidada `f`, si la
función de afuera **menciona** a `f` (la llama o la pasa) antes de la primera
asignación de una variable que `f` lee, es el bug.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PAQUETES = ("core", "places", "app.py")


def _archivos() -> list[Path]:
    out: list[Path] = []
    for p in PAQUETES:
        ruta = RAIZ / p
        out.extend([ruta] if ruta.is_file() else sorted(ruta.rglob("*.py")))
    return [p for p in out if "__pycache__" not in p.parts]


def _asignados(nodo: ast.AST) -> dict[str, int]:
    """Nombre → primera línea donde se asigna, en el cuerpo propio de `nodo`
    (sin entrar en funciones anidadas)."""
    out: dict[str, int] = {}

    def visitar(n: ast.AST) -> None:
        for hijo in ast.iter_child_nodes(n):
            if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(hijo, ast.Name) and isinstance(hijo.ctx, ast.Store):
                out[hijo.id] = min(out.get(hijo.id, hijo.lineno), hijo.lineno)
            visitar(hijo)

    visitar(nodo)
    return out


def _leidos(fn: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _menciones(nodo: ast.AST, nombre: str, desde: int) -> list[int]:
    return sorted(n.lineno for n in ast.walk(nodo)
                  if isinstance(n, ast.Name) and n.id == nombre
                  and isinstance(n.ctx, ast.Load) and n.lineno > desde)


def problemas(fuente: str, archivo: str = "<fuente>") -> list[str]:
    arbol = ast.parse(fuente)
    out: list[str] = []
    for externa in ast.walk(arbol):
        if not isinstance(externa, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        asignados = _asignados(externa)
        for anidada in ast.walk(externa):
            if anidada is externa or not isinstance(
                    anidada, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            propios = set(_asignados(anidada)) | {
                a.arg for a in ast.walk(anidada.args) if isinstance(a, ast.arg)}
            libres = _leidos(anidada) - set(propios)
            for var in sorted(libres):
                linea_asig = asignados.get(var)
                if linea_asig is None or linea_asig < anidada.lineno:
                    continue
                usos = _menciones(externa, anidada.name, anidada.lineno)
                if usos and usos[0] < linea_asig:
                    out.append(
                        f"{archivo}:{usos[0]}: `{anidada.name}` se usa antes de "
                        f"que `{var}` se asigne (línea {linea_asig})")
    return out


def test_detecta_el_caso_de_fecha_val():
    """El test tiene que cazar el bug real, no solo pasar en verde."""
    fuente = (
        "def render():\n"
        "    def _resolver(t):\n"
        "        return fecha_val\n"
        "    valuadas = valuar(_resolver)\n"
        "    fecha_val = 1\n"
    )
    assert problemas(fuente)


def test_no_marca_el_orden_correcto():
    fuente = (
        "def render():\n"
        "    fecha_val = 1\n"
        "    def _resolver(t):\n"
        "        return fecha_val\n"
        "    valuadas = valuar(_resolver)\n"
    )
    assert problemas(fuente) == []


@pytest.mark.parametrize("archivo", _archivos(),
                         ids=lambda p: str(p.relative_to(RAIZ)))
def test_ninguna_funcion_anidada_lee_algo_que_todavia_no_existe(archivo):
    assert problemas(archivo.read_text(encoding="utf-8"),
                     str(archivo.relative_to(RAIZ))) == []
