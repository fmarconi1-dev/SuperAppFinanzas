"""Mapping Motivo → (Grupo macro, Subcategoria).

Estructura jerárquica de dos niveles:

  Grupo (macro)        Subcategoria
  ──────────────────   ──────────────────────
  Ingreso              Sueldo                ← Haberes Fundación, SBT, UCEMA
                       Otros                 ← Otros ingresos
                       Desahorro             ← Venta divisa (siempre);
                                               Inversiones cuando viene del
                                               lado del ingreso (caso dual).
  Gasto Fijo           Movilidad             ← Auto
                       Hogar                 ← Servicios, Expensas
                       Impuestos             ← Impuestos
                       Financiero            ← Pago tarjeta
  Gasto Variable       Consumo               ← Compras
                       Ocio                  ← Salidas, Viajes
                       Movilidad             ← Transportes
  Inversion            Activos financieros   ← Inversiones (lado pasivo)
                       Ahorro y Resguardo    ← Compra Divisa
  Saldo Inicial        —                     ← Caja (fila apertura)

Caso dual ("Inversiones"): si aparece en `ingresos` (cobranza, venta) cuenta
como Ingreso/Desahorro; si aparece en `pasivos` (inversión nueva) cuenta como
Inversion/Activos financieros. La lógica vive en `efective_grupo()`.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple


# Mapping default {motivo: (grupo, subcategoria)} para uso "directo".
# `efective_grupo()` puede sobrescribirlo cuando aplican reglas duales.
DEFAULT_CATEGORIAS: Dict[str, Tuple[str, Optional[str]]] = {
    # Ingresos
    "Haberes Fundación": ("Ingreso", "Sueldo"),
    "Haberes SBT":       ("Ingreso", "Sueldo"),
    "Haberes UCEMA":     ("Ingreso", "Sueldo"),
    "Otros ingresos":    ("Ingreso", "Otros"),
    "Venta divisa":      ("Ingreso", "Desahorro"),

    # Gastos fijos
    "Auto":              ("Gasto Fijo", "Movilidad"),
    "Servicios":         ("Gasto Fijo", "Hogar"),
    "Expensas":          ("Gasto Fijo", "Hogar"),
    "Impuestos":         ("Gasto Fijo", "Impuestos"),
    "Pago tarjeta":      ("Gasto Fijo", "Financiero"),

    # Gastos variables (Compra Divisa NO está acá — se mueve a Inversion).
    "Compras":           ("Gasto Variable", "Consumo"),
    "Salidas":           ("Gasto Variable", "Ocio"),
    "Viajes":            ("Gasto Variable", "Ocio"),
    "Transportes":       ("Gasto Variable", "Movilidad"),

    # Inversiones / ahorro (la macro "Inversion" es disjunta de "Gasto Variable").
    "Inversiones":       ("Inversion", "Activos financieros"),
    "Compra Divisa":     ("Inversion", "Ahorro y Resguardo"),

    # Especial: la fila del 1/1 que es saldo de apertura.
    "Caja":              ("Saldo Inicial", None),
}


# Compat hacia atrás: {motivo: grupo}. Se mantiene para código que todavía
# espera la estructura plana.
DEFAULT_GRUPOS: Dict[str, str] = {
    motivo: grupo for motivo, (grupo, _) in DEFAULT_CATEGORIAS.items()
}


# Defaults para usuarios nuevos (signup → onboarding). Sin motivos específicos
# de Franco como "Haberes Fundación / SBT / UCEMA". El nuevo usuario edita y
# crea sus propios motivos desde Configuración cuando los necesite.
DEFAULT_CATEGORIAS_NEW_USER: Dict[str, Tuple[str, Optional[str]]] = {
    # Ingresos
    "Sueldo":           ("Ingreso", "Sueldo"),
    "Otros ingresos":   ("Ingreso", "Otros"),
    "Venta divisa":     ("Ingreso", "Desahorro"),

    # Gastos fijos
    "Auto":             ("Gasto Fijo", "Movilidad"),
    "Servicios":        ("Gasto Fijo", "Hogar"),
    "Expensas":         ("Gasto Fijo", "Hogar"),
    "Impuestos":        ("Gasto Fijo", "Impuestos"),
    "Pago tarjeta":     ("Gasto Fijo", "Financiero"),

    # Gastos variables
    "Compras":          ("Gasto Variable", "Consumo"),
    "Salidas":          ("Gasto Variable", "Ocio"),
    "Viajes":           ("Gasto Variable", "Ocio"),
    "Transportes":      ("Gasto Variable", "Movilidad"),

    # Inversion
    "Inversiones":      ("Inversion", "Activos financieros"),
    "Compra Divisa":    ("Inversion", "Ahorro y Resguardo"),
}


# Motivos cuyo grupo depende de la dirección del flujo (ingreso vs pasivo).
# Si vienen como ingreso, se reclasifican a Ingreso/Desahorro.
MOTIVOS_DUAL_DESAHORRO = {"Inversiones"}


def categoria_de(
    motivo: str,
    custom_map: Optional[Dict[str, Tuple[str, Optional[str]]]] = None,
) -> Tuple[str, Optional[str]]:
    """Devuelve (grupo, subcategoria). Si el motivo no existe, ('Sin categorizar', None)."""
    if custom_map is None:
        custom_map = DEFAULT_CATEGORIAS
    return custom_map.get(motivo, ("Sin categorizar", None))


def efective_grupo(
    motivo: str,
    pasivos: float,
    ingresos: float,
    custom_map: Optional[Dict[str, Tuple[str, Optional[str]]]] = None,
) -> Tuple[str, Optional[str]]:
    """Aplica reglas duales: si "Inversiones" llega como ingreso, → Ingreso/Desahorro.

    Para motivos no-duales, devuelve el mapping default.
    """
    if motivo in MOTIVOS_DUAL_DESAHORRO and ingresos > 0 and pasivos == 0:
        return ("Ingreso", "Desahorro")
    return categoria_de(motivo, custom_map)


def grupos_efectivos(
    motivos: Iterable,
    pasivos: Iterable,
    ingresos: Iterable,
    custom_map: Optional[Dict[str, Tuple[str, Optional[str]]]] = None,
) -> Tuple[list, list]:
    """`efective_grupo` de cada fila, para columnas enteras: (grupos, subcategorías).

    Es la misma función fila a fila, sin `DataFrame.iterrows`. `iterrows` arma
    una Series por fila y costaba ~33 µs cada una: con 5.300 movimientos,
    ~175 ms en cada KPI, tabla del mes o libro diario (frente 4 de rendimiento,
    21/10/2026). Recorrer las columnas crudas da exactamente lo mismo.
    """
    # `float` como hacía cada llamador con `float(row[...])`: mismo resultado.
    pares = [efective_grupo(m, float(p), float(i), custom_map)
             for m, p, i in zip(motivos, pasivos, ingresos)]
    if not pares:
        return [], []
    grupos, subs = zip(*pares)
    return list(grupos), list(subs)


def motivos_sin_categorizar(
    motivos: list[str], custom_map: Optional[Dict[str, Tuple[str, Optional[str]]]] = None
) -> list[str]:
    if custom_map is None:
        custom_map = DEFAULT_CATEGORIAS
    return sorted({m for m in motivos if m and m not in custom_map})
