"""El formulario de transacciones tiene dos modos y un solo guardado.

**Bug real en producción (4/8/2026).** Franco tocó "💸 Agregar gasto" desde el
celular y la app reventó::

    UnboundLocalError: cannot access local variable 'firma_val'
    where it is not associated with a value

`_form_alta_edicion` se bifurca en **modo rápido** (importe + motivo, y nada
más) y **modo detallado** (el formulario completo), pero después las dos ramas
caen al **mismo** código de guardado. `firma_val` se definía únicamente en la
rama detallada, así que en el modo rápido —el que se usa desde el teléfono—
la variable no existía cuando el guardado la leía.

Este test no revisa `firma_val`: revisa **la forma del problema**. Lee el
código con `ast` y verifica que ninguna variable que se lea después de la
bifurcación esté definida en una sola de las dos ramas. Así atrapa también a
la próxima variable que alguien agregue a un solo modo.

Se hace por AST y no ejecutando el formulario porque renderizar Streamlit en
un test exige un runtime entero; esto corre en milisegundos y apunta
exactamente a la clase de error que pasó.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

MODULO = (Path(__file__).resolve().parents[1]
          / "places" / "finanzas" / "views" / "transacciones.py")


def _funcion(nombre: str) -> ast.FunctionDef:
    arbol = ast.parse(MODULO.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
            return nodo
    raise AssertionError(f"No existe la función {nombre} en {MODULO.name}")


def _asignados(nodos) -> set[str]:
    """Nombres que quedan asignados al ejecutar `nodos`."""
    out: set[str] = set()
    for nodo in nodos:
        for sub in ast.walk(nodo):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                out.add(sub.id)
    return out


def _leidos(nodos) -> set[str]:
    out: set[str] = set()
    for nodo in nodos:
        for sub in ast.walk(nodo):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                out.add(sub.id)
    return out


def _bifurcacion_por_modo(func: ast.FunctionDef) -> ast.If:
    """El `if modo_rapido: ... else: ...` que parte el formulario en dos."""
    for nodo in ast.walk(func):
        if (isinstance(nodo, ast.If)
                and isinstance(nodo.test, ast.Name)
                and nodo.test.id == "modo_rapido"
                and nodo.orelse):
            return nodo
    raise AssertionError("No se encontró la bifurcación `if modo_rapido:`")


def test_las_dos_ramas_del_formulario_definen_las_mismas_variables():
    """Lo que se lee después de la bifurcación tiene que existir en AMBOS modos.

    Si este test falla, mirá qué variable aparece en el mensaje: está definida
    en un solo modo y el otro va a explotar en runtime. La solución es
    definirla **antes** del `if`, no duplicarla.
    """
    func = _funcion("_form_alta_edicion")
    bifurcacion = _bifurcacion_por_modo(func)
    cuerpo = func.body
    idx = next(i for i, n in enumerate(cuerpo) if _contiene(n, bifurcacion))
    despues = cuerpo[idx + 1:]

    rapido = _asignados(bifurcacion.body)
    detallado = _asignados(bifurcacion.orelse)
    solo_en_una = rapido.symmetric_difference(detallado)

    # Se descuentan las que ya existen antes de la bifurcación (la solución
    # correcta al bug) y las que el propio código de guardado crea —un
    # `with connect() as conn:`, por ejemplo—, porque esas no dependen de por
    # qué rama se pasó. Es una heurística, no análisis de flujo completo:
    # apunta a la clase de error que ya ocurrió, no a probar ausencia de todos.
    previas = _asignados([n for n in cuerpo if not _contiene(n, bifurcacion)])
    creadas_despues = _asignados(despues)

    peligrosas = sorted((solo_en_una & _leidos(despues))
                        - previas - creadas_despues)
    assert not peligrosas, (
        "Estas variables se definen en un solo modo del formulario y se leen "
        f"después de la bifurcación: {peligrosas}. En el modo que no las "
        "define, la app revienta con UnboundLocalError (pasó el 4/8/2026 con "
        "'firma_val' al tocar 'Agregar gasto' desde el celular). Definilas "
        "ANTES del `if modo_rapido:`."
    )


def _contiene(nodo: ast.AST, buscado: ast.AST) -> bool:
    return any(sub is buscado for sub in ast.walk(nodo))


@pytest.mark.parametrize("variable", [
    "firma_val",        # el del bug
    "importe_str", "motivo_sel", "motivo_nuevo",
    "fecha_val", "tipo_val", "comentario_val", "btn_label",
])
def test_las_variables_del_guardado_existen_en_los_dos_modos(variable):
    """Cada variable que el guardado necesita, disponible en ambos caminos.

    Explícito a propósito: si mañana alguien saca una de estas de un modo, el
    test dice **cuál** en vez de fallar con un genérico.
    """
    func = _funcion("_form_alta_edicion")
    bifurcacion = _bifurcacion_por_modo(func)
    previas = _asignados([n for n in func.body if not _contiene(n, bifurcacion)])
    rapido = _asignados(bifurcacion.body) | previas
    detallado = _asignados(bifurcacion.orelse) | previas

    assert variable in rapido, f"'{variable}' no existe en el modo RÁPIDO"
    assert variable in detallado, f"'{variable}' no existe en el modo DETALLADO"


def test_la_firma_se_define_antes_de_la_bifurcacion():
    """La corrección concreta: `firma_val` sale del `if` y vive antes.

    En modo rápido no se pregunta la firma —esa es la gracia del modo—, así
    que se asume el miembro activo del espacio familiar.
    """
    func = _funcion("_form_alta_edicion")
    bifurcacion = _bifurcacion_por_modo(func)
    previas = _asignados([n for n in func.body if not _contiene(n, bifurcacion)])
    assert "firma_val" in previas


# ---------------------------------------------------------------------------
# Editar una transacción no puede depender del signo con que se cargó
# ---------------------------------------------------------------------------
#
# Bug reportado por Franco el 5/8/2026: *"en la edición no me deja editar solo
# el tipo de transacción, si o si me exige que sea positivo o negativo, y a
# veces solamente me equivoqué de categoría"*.
#
# Causa: `tipo_default` se decidía con `pasivos > 0`. Una transacción con
# `pasivos` **negativo** caía en "Ingreso", el importe se tomaba de `ingresos`
# —que vale 0— y el campo precargaba **vacío**. Al guardar, la validación "el
# importe debe ser positivo" la rechazaba: esa fila no se podía editar de
# ninguna manera, ni siquiera para corregirle la categoría.
#
# Igual que el resto del archivo, esto se verifica **leyendo el código**, no
# importando el módulo: `transacciones.py` importa Streamlit y traerlo obliga
# a tener el runtime entero para correr la suite.


def _precarga(pasivos: float, ingresos: float) -> tuple[str, str]:
    """Réplica de la decisión que toma `_form_alta_edicion` al entrar en
    edición. Los tests de abajo la usan para documentar el comportamiento
    esperado; que el **código** siga esa regla lo garantiza
    `test_el_form_decide_el_tipo_con_distinto_de_cero`."""
    tipo = "Gasto" if pasivos != 0 else "Ingreso"
    importe = abs(pasivos if tipo == "Gasto" else ingresos)
    if importe == 0:
        return tipo, ""
    if importe == int(importe):
        return tipo, str(int(importe))
    return tipo, f"{importe:.2f}".replace(".", ",")


@pytest.mark.parametrize("pasivos,ingresos,tipo_esp,texto_esp", [
    (50_000.0, 0.0, "Gasto", "50000"),
    (0.0, 120_000.0, "Ingreso", "120000"),
    (1_234.56, 0.0, "Gasto", "1234,56"),
    (-5_000.0, 0.0, "Gasto", "5000"),     # el caso roto: gasto en negativo
    (-1_200.0, 0.0, "Gasto", "1200"),
])
def test_el_importe_precarga_siempre_con_algo(pasivos, ingresos,
                                              tipo_esp, texto_esp):
    tipo, texto = _precarga(pasivos, ingresos)
    assert tipo == tipo_esp
    assert texto == texto_esp
    assert texto != "", (
        "el campo precargó vacío: al guardar va a cortar con 'Importe "
        "inválido' y esa transacción queda imposible de editar"
    )


def test_un_pasivo_negativo_no_se_lee_como_ingreso():
    """Era la raíz del bug: el signo no cambia de qué columna sale el importe."""
    assert _precarga(-5_000.0, 0.0)[0] == "Gasto"


def test_el_form_decide_el_tipo_con_distinto_de_cero():
    """Fija la corrección en el código. Sin esto, los tests de arriba seguirían
    pasando aunque alguien volviera a poner `> 0`, porque replican la lógica en
    vez de importarla."""
    codigo = MODULO.read_text(encoding="utf-8")
    assert 'tipo_default = "Gasto" if pasivos_default != 0 else "Ingreso"' in codigo
    assert 'tipo_default = "Gasto" if pasivos_default > 0 else "Ingreso"' not in codigo


def test_el_importe_por_defecto_se_toma_en_valor_absoluto():
    codigo = MODULO.read_text(encoding="utf-8")
    assert "importe_default = abs(" in codigo
