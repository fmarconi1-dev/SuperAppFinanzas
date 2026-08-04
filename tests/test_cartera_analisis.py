"""Tests de la composición de la cartera (Fase 3b, punto 4).

Lo que protegen: que los porcentajes se midan contra el **patrimonio** (con el
efectivo adentro), que lo no cubierto diga "Sin dato" en vez de esconderse en
otra categoría, y que no se agregue el resultado total por grupo — solo el no
realizado, que es el único que se puede sumar sin que la devaluación lo infle.
"""

import pytest

from places.inversiones.cartera.analisis import (
    EFECTIVO, SIN_DATO, por_sector, por_tipo_de_renta, sectores_desde_snapshot,
    tipo_de_renta,
)


class _Pos:
    """Lo mínimo que el módulo necesita de una PosicionValuada."""

    def __init__(self, ticker, categoria="Cedears", valor=None, costo=0.0,
                 cerrada=False):
        self.ticker = ticker
        self.categoria_activo = categoria
        self.valor_ars = valor
        self.costo_ars = costo
        self.cerrada = cerrada


# ---------------------------------------------------------------------------
# Tipo de renta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("categoria,esperado", [
    ("Acciones", "Renta variable"),
    ("Cedears", "Renta variable"),
    ("Bonos", "Renta fija"),
    ("Letras", "Renta fija"),
    ("ONs", "Renta fija"),
    ("Pagarés", "Renta fija"),      # con tilde, como lo escribe la app
    ("Pagares", "Renta fija"),      # sin tilde, como puede venir del Excel
    ("CRIPTO", "Cripto"),
    ("", SIN_DATO),
    ("Loquesea", SIN_DATO),
    (None, SIN_DATO),
])
def test_traduccion_de_categoria_a_tipo_de_renta(categoria, esperado):
    assert tipo_de_renta(categoria) == esperado


def test_agrupa_por_tipo_de_renta_y_suma_valores():
    gs = por_tipo_de_renta([
        _Pos("GGAL", "Acciones", 700_000, 500_000),
        _Pos("NVDA", "Cedears", 300_000, 200_000),
        _Pos("AE38", "Bonos", 500_000, 400_000),
        _Pos("BITCOIN", "Cripto", 500_000, 300_000),
    ])
    por_nombre = {g.nombre: g for g in gs}
    assert por_nombre["Renta variable"].n == 2
    assert por_nombre["Renta variable"].valor_ars == pytest.approx(1_000_000)
    assert por_nombre["Renta fija"].valor_ars == pytest.approx(500_000)
    assert por_nombre["Cripto"].valor_ars == pytest.approx(500_000)


# ---------------------------------------------------------------------------
# El porcentaje se mide contra el patrimonio
# ---------------------------------------------------------------------------

def test_los_porcentajes_incluyen_el_efectivo_y_suman_cien():
    """Sin el efectivo, un 20% en caja desaparecería y todo lo demás se vería
    más grande de lo que es."""
    gs = por_tipo_de_renta(
        [_Pos("GGAL", "Acciones", 800_000, 800_000)], efectivo_ars=200_000,
    )
    por_nombre = {g.nombre: g for g in gs}
    assert por_nombre["Renta variable"].pct == pytest.approx(80.0)
    assert por_nombre[EFECTIVO].pct == pytest.approx(20.0)
    assert sum(g.pct for g in gs) == pytest.approx(100.0)


def test_el_efectivo_no_inventa_resultado():
    """La caja vale lo que costó: su resultado es cero, no una ganancia."""
    gs = por_tipo_de_renta([], efectivo_ars=500_000)
    (caja,) = gs
    assert caja.valor_ars == pytest.approx(500_000)
    assert caja.resultado_ars == 0
    assert caja.rendimiento_pct == 0


def test_sin_posiciones_ni_efectivo_no_rompe():
    assert por_tipo_de_renta([]) == []
    assert por_sector([], {}) == []


# ---------------------------------------------------------------------------
# Qué entra y qué no
# ---------------------------------------------------------------------------

def test_las_posiciones_cerradas_no_ocupan_lugar_en_la_cartera():
    """Vendidas o vencidas: su rendimiento cuenta en el total, pero no son
    parte de cómo está repartida la plata hoy."""
    gs = por_tipo_de_renta([
        _Pos("GGAL", "Acciones", 100_000, 100_000),
        _Pos("S15G5", "Letras", None, 0, cerrada=True),
    ])
    assert [g.nombre for g in gs] == ["Renta variable"]


def test_una_posicion_sin_precio_se_cuenta_pero_no_suma_valor_ni_costo():
    """Si su costo entrara sin su valor, el grupo mostraría una pérdida falsa."""
    gs = por_tipo_de_renta([
        _Pos("GGAL", "Acciones", 100_000, 60_000),
        _Pos("RARO", "Acciones", None, 40_000),
    ])
    (g,) = gs
    assert g.n == 2 and g.sin_precio == 1
    assert g.valor_ars == pytest.approx(100_000)
    assert g.costo_ars == pytest.approx(60_000)
    assert g.rendimiento_pct == pytest.approx(66.67, rel=1e-3)


def test_el_resultado_del_grupo_es_el_no_realizado():
    """Deliberadamente NO se agrega el resultado total: sumarlo por grupo
    repetiría la trampa de la Fase 3a (la devaluación infla los subtotales)."""
    gs = por_tipo_de_renta([_Pos("GGAL", "Acciones", 150_000, 100_000)])
    assert gs[0].resultado_ars == pytest.approx(50_000)
    assert gs[0].rendimiento_pct == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Sector: lo que no se sabe, se dice
# ---------------------------------------------------------------------------

def test_el_sector_solo_mira_la_renta_variable():
    """A un bono, al efectivo o a la cripto no les falta el sector: no tienen.
    Si entraran, empujarían todo a un "Sin dato" del 75% que no dice nada."""
    gs = por_sector(
        [_Pos("NVDA", valor=300_000, costo=200_000),
         _Pos("TSM", valor=100_000, costo=90_000),
         _Pos("AE38", "Bonos", 500_000, 400_000),
         _Pos("BITCOIN", "Cripto", 900_000, 900_000),
         _Pos("#UMV1", "Otros", 8_000_000, 8_000_000)],
        {"NVDA": "Technology", "TSM": "Technology"},
    )
    assert [g.nombre for g in gs] == ["Technology"]
    assert gs[0].n == 2
    assert gs[0].valor_ars == pytest.approx(400_000)
    assert gs[0].pct == pytest.approx(100.0)   # sobre la renta variable


def test_dentro_de_la_renta_variable_lo_no_cubierto_si_dice_sin_dato():
    """Los ETFs y las acciones fuera del universo del scoring."""
    gs = por_sector(
        [_Pos("NVDA", valor=300_000, costo=200_000),
         _Pos("GLD", valor=100_000, costo=90_000)],     # ETF: es una canasta
        {"NVDA": "Technology"},
    )
    por_nombre = {g.nombre: g for g in gs}
    assert por_nombre["Technology"].pct == pytest.approx(75.0)
    assert por_nombre[SIN_DATO].n == 1


def test_el_pagare_es_renta_fija_aunque_no_este_en_config():
    """Su ticker empieza con # y nunca estuvo en Config: llega como "Otros".
    Es el 34% de la cartera de Franco — no puede quedar en "Sin dato"."""
    assert tipo_de_renta("Otros", "#UMV060770008") == "Renta fija"
    gs = por_tipo_de_renta([_Pos("#UMV060770008", "Otros", 8_000_000, 7_600_000)])
    assert [g.nombre for g in gs] == ["Renta fija"]


def test_sin_dato_va_ultimo_aunque_sea_el_grupo_mas_grande():
    """Es una etiqueta de ignorancia, no una categoría que compita."""
    gs = por_sector(
        [_Pos("SPY", valor=9_000_000, costo=9_000_000),
         _Pos("NVDA", valor=100_000, costo=100_000)],
        {"NVDA": "Technology"},
    )
    assert [g.nombre for g in gs] == ["Technology", SIN_DATO]


def test_los_grupos_van_de_mayor_a_menor_peso():
    gs = por_sector(
        [_Pos("A", valor=100), _Pos("B", valor=900), _Pos("C", valor=500)],
        {"A": "Chico", "B": "Grande", "C": "Medio"},
    )
    assert [g.nombre for g in gs] == ["Grande", "Medio", "Chico"]


# ---------------------------------------------------------------------------
# Lectura del snapshot
# ---------------------------------------------------------------------------

def test_lee_los_sectores_del_snapshot():
    d = sectores_desde_snapshot({"empresas": [
        {"ticker": "nvda", "sector": " Technology "},
        {"ticker": "GGAL", "sector": "Financial Services"},
        {"ticker": "XXX"},                      # sin sector: se ignora
        {"sector": "Energy"},                   # sin ticker: se ignora
    ]})
    assert d == {"NVDA": "Technology", "GGAL": "Financial Services"}


@pytest.mark.parametrize("entrada", [None, {}, {"empresas": None}, "roto", []])
def test_un_snapshot_caido_o_vacio_deja_todo_en_sin_dato(entrada):
    """El scoring puede no responder: la cartera tiene que seguir mostrándose."""
    assert sectores_desde_snapshot(entrada) == {}
    gs = por_sector([_Pos("NVDA", valor=100)], sectores_desde_snapshot(entrada))
    assert [g.nombre for g in gs] == [SIN_DATO]
