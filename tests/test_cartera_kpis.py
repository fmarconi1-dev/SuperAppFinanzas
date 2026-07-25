"""Tests de valuación y KPIs de cartera (Fase 3a, paso 4).

Puros: el precio se inyecta con un `resolver` fake, así no hay red ni UI.
Cubren el costo promedio ponderado, el resultado, el manejo de posiciones sin
precio (no deben ensuciar los totales) y el costo en USD con TC histórico.
"""

from __future__ import annotations

import pytest

from places.inversiones.cartera.kpis import kpis_de, valuar
from places.inversiones.cartera.parser import Instrumento
from places.inversiones.cartera.posiciones import Posicion, _acumular


def _resolver_fijo(precios: dict):
    def _r(ticker, inst):
        p = precios.get(ticker)
        return (p, "proveedor") if p is not None else (None, "sin_dato")
    return _r


# ---------------------------------------------------------------------------
# Posición: PPC y costo de la tenencia
# ---------------------------------------------------------------------------

def test_ppc_y_costo_de_posicion():
    # 10 @ 100 y 5 @ 110 → PPC 103,33; vendo 4 → quedan 11.
    filas = [
        (True, "COMPRA", "GGAL", 10, -1000, "ARS", None),
        (True, "COMPRA", "GGAL", 5, -550, "ARS", None),
        (True, "VENTA", "GGAL", -4, 460, "ARS", None),
    ]
    pos = _acumular(filas)["GGAL"]
    assert pos.cant_actual == 11
    assert pos.ppc_ars == pytest.approx(103.3333, rel=1e-4)
    assert pos.costo_ars_posicion == pytest.approx(1136.6667, rel=1e-4)


def test_costo_usd_usa_tc_de_cada_fecha():
    # misma plata nominal, dos TC muy distintos → el costo USD los respeta.
    filas = [
        (True, "COMPRA", "GGAL", 10, -1000, "ARS", 1000.0),   # US$1
        (True, "COMPRA", "GGAL", 10, -1000, "ARS", 500.0),    # US$2
    ]
    pos = _acumular(filas)["GGAL"]
    assert pos.costo_usd_hist == pytest.approx(3.0)
    assert pos.ppc_usd_hist == pytest.approx(0.15)


def test_compra_denominada_en_usd():
    filas = [(True, "COMPRA", "AE38", 100, -500, "USD", 1000.0)]
    pos = _acumular(filas)["AE38"]
    assert pos.costo_usd_hist == pytest.approx(500.0)
    assert pos.costo_ars_compras == pytest.approx(500_000.0)  # 500 × TC


# ---------------------------------------------------------------------------
# Valuación
# ---------------------------------------------------------------------------

def test_valuar_calcula_valor_resultado_y_rendimiento():
    pos = {"GGAL": Posicion("GGAL", cant_comprada=10, costo_ars_compras=1000.0)}
    v = valuar(pos, _resolver_fijo({"GGAL": 150.0}))[0]
    assert v.cantidad == 10
    assert v.valor_ars == pytest.approx(1500.0)
    assert v.costo_ars == pytest.approx(1000.0)
    assert v.resultado_ars == pytest.approx(500.0)
    assert v.rendimiento_pct == pytest.approx(50.0)


def test_valuar_omite_posiciones_cerradas():
    pos = {
        "GGAL": Posicion("GGAL", cant_comprada=10, cant_vendida=-10,
                         costo_ars_compras=1000.0),
        "SPY": Posicion("SPY", cant_comprada=5, costo_ars_compras=500.0),
    }
    tickers = [v.ticker for v in valuar(pos, _resolver_fijo({"SPY": 120.0}))]
    assert tickers == ["SPY"]


def test_valuar_sin_precio_no_rompe():
    pos = {"XX": Posicion("XX", cant_comprada=3, costo_ars_compras=300.0)}
    v = valuar(pos, _resolver_fijo({}))[0]
    assert v.precio is None and v.valor_ars is None
    assert v.resultado_ars is None and v.rendimiento_pct is None
    assert v.origen_precio == "sin_dato"


def test_valuar_toma_categoria_del_instrumento():
    pos = {"AE38": Posicion("AE38", cant_comprada=100, costo_ars_compras=1000.0)}
    insts = {"AE38": Instrumento("AE38", "AE38D", "Bonos", "USD/100")}
    v = valuar(pos, _resolver_fijo({"AE38": 12.0}), insts)[0]
    assert v.categoria_activo == "Bonos"


def test_valuadas_ordenadas_por_valor_desc():
    pos = {
        "CHICA": Posicion("CHICA", cant_comprada=1, costo_ars_compras=10.0),
        "GRANDE": Posicion("GRANDE", cant_comprada=100, costo_ars_compras=100.0),
    }
    v = valuar(pos, _resolver_fijo({"CHICA": 10.0, "GRANDE": 50.0}))
    assert [x.ticker for x in v] == ["GRANDE", "CHICA"]


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

def test_kpis_totales_y_usd():
    pos = {
        "A": Posicion("A", cant_comprada=10, costo_ars_compras=1000.0),
        "B": Posicion("B", cant_comprada=10, costo_ars_compras=2000.0),
    }
    v = valuar(pos, _resolver_fijo({"A": 150.0, "B": 180.0}))
    k = kpis_de(v, mep=1500.0)
    assert k.valor_total_ars == pytest.approx(3300.0)
    assert k.costo_total_ars == pytest.approx(3000.0)
    assert k.resultado_ars == pytest.approx(300.0)
    assert k.rendimiento_pct == pytest.approx(10.0)
    assert k.valor_total_usd == pytest.approx(2.2)
    assert (k.posiciones_valuadas, k.posiciones_sin_precio) == (2, 0)


def test_kpis_excluyen_costo_de_lo_que_no_tiene_precio():
    # Si una posición no tiene precio, su costo tampoco suma: si no, el
    # rendimiento compararía valor parcial contra costo total.
    pos = {
        "A": Posicion("A", cant_comprada=10, costo_ars_compras=1000.0),
        "SINPRECIO": Posicion("SINPRECIO", cant_comprada=5, costo_ars_compras=9999.0),
    }
    k = kpis_de(valuar(pos, _resolver_fijo({"A": 150.0})), mep=1500.0)
    assert k.costo_total_ars == pytest.approx(1000.0)
    assert k.valor_total_ars == pytest.approx(1500.0)
    assert k.posiciones_sin_precio == 1


def test_kpis_sin_mep_no_calcula_usd():
    pos = {"A": Posicion("A", cant_comprada=1, costo_ars_compras=100.0)}
    k = kpis_de(valuar(pos, _resolver_fijo({"A": 100.0})), mep=None)
    assert k.valor_total_usd is None


def test_kpis_vacios_no_dividen_por_cero():
    k = kpis_de([], mep=1500.0)
    assert k.valor_total_ars == 0 and k.rendimiento_pct is None
