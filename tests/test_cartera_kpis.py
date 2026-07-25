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
        (True, "COMPRA", "GGAL", 10, -1000, "ARS", None, False),
        (True, "COMPRA", "GGAL", 5, -550, "ARS", None, False),
        (True, "VENTA", "GGAL", -4, 460, "ARS", None, False),
    ]
    pos = _acumular(filas)["GGAL"]
    assert pos.cant_actual == 11
    assert pos.ppc_ars == pytest.approx(103.3333, rel=1e-4)
    assert pos.costo_ars_posicion == pytest.approx(1136.6667, rel=1e-4)


def test_costo_usd_usa_tc_de_cada_fecha():
    # misma plata nominal, dos TC muy distintos → el costo USD los respeta.
    filas = [
        (True, "COMPRA", "GGAL", 10, -1000, "ARS", 1000.0, False),   # US$1
        (True, "COMPRA", "GGAL", 10, -1000, "ARS", 500.0, False),    # US$2
    ]
    pos = _acumular(filas)["GGAL"]
    assert pos.costo_usd_hist == pytest.approx(3.0)
    assert pos.ppc_usd_hist == pytest.approx(0.15)


def test_compra_denominada_en_usd():
    filas = [(True, "COMPRA", "AE38", 100, -500, "USD", 1000.0, False)]
    pos = _acumular(filas)["AE38"]
    assert pos.costo_usd_hist == pytest.approx(500.0)
    assert pos.costo_ars_compras == pytest.approx(500_000.0)  # 500 × TC


def test_espejo_de_dividendo_no_suma_flujo():
    filas = [
        (True, "DIVIDENDO", "TSM", 0, 0.76, "USD", 1000.0, False),
        (True, "DIVIDENDO", "TSM", 0, -4.53, "ARS", 1000.0, True),  # espejo
    ]
    pos = _acumular(filas)["TSM"]
    assert pos.flujos_usd == pytest.approx(0.76)
    assert pos.flujos_ars == pytest.approx(760.0)  # solo la línea USD, a TC


def test_instrumento_vencido_cierra_la_posicion():
    from places.inversiones.cartera.posiciones import _InstrumentoMin
    filas = [
        (True, "COMPRA", "S15G5", 1000, -1000, "ARS", 1000.0, False),
        (True, "AMORTIZACION", "S15G5", 0, 1100, "ARS", 1000.0, False),
    ]
    pos = _acumular(filas, {"S15G5": _InstrumentoMin(activo=False)})["S15G5"]
    assert pos.cant_actual == 0          # venció: ya no hay tenencia
    assert pos.cant_remanente == 1000    # pero las unidades se compraron
    assert pos.cant_amortizada == 1000
    assert pos.costo_amortizado_ars == pytest.approx(1000.0)
    assert pos.flujos_ars == pytest.approx(1100.0)


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


def test_valuar_omite_cerradas_sin_resultado_pero_conserva_las_que_rindieron():
    pos = {
        # Vendida entera: sin tenencia, PERO dejó resultado realizado → se
        # conserva, porque su rendimiento forma parte del total de la cartera.
        "GGAL": Posicion("GGAL", cant_comprada=10, cant_vendida=-10,
                         costo_ars_compras=1000.0, ingreso_ars_ventas=1500.0),
        # Sin tenencia y sin resultado (ej. canje neutro): se omite.
        "RUIDO": Posicion("RUIDO", cant_comprada=5, cant_vendida=-5),
        "SPY": Posicion("SPY", cant_comprada=5, costo_ars_compras=500.0),
    }
    v = valuar(pos, _resolver_fijo({"SPY": 120.0}))
    tickers = {x.ticker for x in v}
    assert tickers == {"SPY", "GGAL"}
    ggal = next(x for x in v if x.ticker == "GGAL")
    assert ggal.cerrada is True
    assert ggal.resultado_ars == pytest.approx(500.0)   # 1500 − costo 1000
    assert ggal.rendimiento_pct == pytest.approx(50.0)


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


# ---------------------------------------------------------------------------
# Rendimiento completo: realizado + flujos + no realizado − capital amortizado
# ---------------------------------------------------------------------------

def test_letra_vencida_rinde_el_interes_no_el_capital():
    """Una letra que amortiza devuelve capital + interés: el rendimiento es
    el interés, no el total cobrado (bug detectado con datos reales)."""
    from places.inversiones.cartera.posiciones import _InstrumentoMin
    filas = [
        (True, "COMPRA", "S15G5", 1000, -1000, "ARS", 1000.0, False),
        (True, "AMORTIZACION", "S15G5", 0, 1050, "ARS", 1000.0, False),
    ]
    pos = _acumular(filas, {"S15G5": _InstrumentoMin(activo=False)})
    v = valuar(pos, _resolver_fijo({}))[0]
    assert v.cerrada is True
    assert v.resultado_ars == pytest.approx(50.0)      # 1050 − 1000, no 1050
    assert v.rendimiento_pct == pytest.approx(5.0)


def test_rendimiento_usd_usa_el_mep_de_cada_fecha():
    """Compra con MEP 1000 y amortiza con MEP 1400: gana en pesos y pierde
    en dólares. Es el caso real de S15G5."""
    from places.inversiones.cartera.posiciones import _InstrumentoMin
    filas = [
        (True, "COMPRA", "LETRA", 1000, -1000, "ARS", 1000.0, False),   # US$1
        (True, "AMORTIZACION", "LETRA", 0, 1200, "ARS", 1400.0, False),  # US$0,857
    ]
    pos = _acumular(filas, {"LETRA": _InstrumentoMin(activo=False)})
    v = valuar(pos, _resolver_fijo({}))[0]
    assert v.resultado_ars == pytest.approx(200.0)          # +20% en pesos
    assert v.rendimiento_pct == pytest.approx(20.0)
    assert v.resultado_usd < 0                              # pero pierde en USD
    assert v.rendimiento_usd_pct == pytest.approx(-14.2857, rel=1e-3)


def test_dividendos_suman_al_rendimiento():
    pos = {
        "GGAL": Posicion("GGAL", cant_comprada=10, costo_ars_compras=1000.0,
                         flujos_ars=80.0),
    }
    v = valuar(pos, _resolver_fijo({"GGAL": 110.0}))[0]
    # no realizado (1100−1000) + dividendos (80)
    assert v.no_realizado_ars == pytest.approx(100.0)
    assert v.resultado_ars == pytest.approx(180.0)
    assert v.rendimiento_pct == pytest.approx(18.0)


def test_kpis_componentes_del_rendimiento():
    from places.inversiones.cartera.posiciones import _InstrumentoMin
    filas = [
        # viva: compra 10 @100, vale 110 → +100 no realizado
        (True, "COMPRA", "VIVA", 10, -1000, "ARS", 1000.0, False),
        # vencida: compra 1000, amortiza 1050 → +50
        (True, "COMPRA", "VENC", 1000, -1000, "ARS", 1000.0, False),
        (True, "AMORTIZACION", "VENC", 0, 1050, "ARS", 1000.0, False),
    ]
    pos = _acumular(filas, {"VENC": _InstrumentoMin(activo=False)})
    k = kpis_de(valuar(pos, _resolver_fijo({"VIVA": 110.0}), mep_actual=1000.0),
                mep=1000.0)
    assert k.invertido_ars == pytest.approx(2000.0)
    assert k.flujos_ars == pytest.approx(1050.0)
    assert k.costo_amortizado_ars == pytest.approx(1000.0)
    assert k.no_realizado_ars == pytest.approx(100.0)
    # La tenencia viva se mide aparte del rendimiento total.
    assert k.valor_total_ars == pytest.approx(1100.0)
    assert k.resultado_ars == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Rendimiento total: método del patrimonio (el único verificable)
# ---------------------------------------------------------------------------

class _Cap:
    """Stub de CapitalAportado."""
    def __init__(self, ars, usd):
        self.neto_ars, self.neto_usd = ars, usd


def test_rendimiento_total_por_patrimonio():
    """Aportó $1.000 (US$1 a TC 1000) y hoy tiene $1.200 con MEP 1200:
    ganó 20% en pesos y 0% en dólares."""
    from places.inversiones.cartera.kpis import completar_patrimonio
    pos = {"A": Posicion("A", cant_comprada=10, costo_ars_compras=1000.0)}
    k = kpis_de(valuar(pos, _resolver_fijo({"A": 120.0}), mep_actual=1200.0), mep=1200.0)
    completar_patrimonio(k, _Cap(1000.0, 1.0), cash_ars=0.0, cash_usd=0.0, mep=1200.0)
    assert k.patrimonio_ars == pytest.approx(1200.0)
    assert k.patrimonio_usd == pytest.approx(1.0)
    assert k.resultado_total_ars == pytest.approx(200.0)
    assert k.rendimiento_total_pct == pytest.approx(20.0)
    assert k.resultado_total_usd == pytest.approx(0.0)      # en dólares, empató
    assert k.rendimiento_total_usd_pct == pytest.approx(0.0)


def test_patrimonio_suma_el_efectivo_de_las_dos_monedas():
    from places.inversiones.cartera.kpis import completar_patrimonio
    k = kpis_de([], mep=1000.0)
    completar_patrimonio(k, _Cap(0.0, 0.0), cash_ars=5000.0, cash_usd=10.0, mep=1000.0)
    assert k.patrimonio_ars == pytest.approx(15000.0)   # 5000 + 10×1000
    assert k.patrimonio_usd == pytest.approx(15.0)      # 10 + 5000/1000


def test_perdida_en_dolares_con_ganancia_en_pesos():
    """El caso real de Franco: sube en pesos, baja en dólares."""
    from places.inversiones.cartera.kpis import completar_patrimonio
    pos = {"A": Posicion("A", cant_comprada=10, costo_ars_compras=1000.0)}
    k = kpis_de(valuar(pos, _resolver_fijo({"A": 118.0}), mep_actual=1500.0), mep=1500.0)
    completar_patrimonio(k, _Cap(1000.0, 1.0), cash_ars=0.0, cash_usd=0.0, mep=1500.0)
    assert k.resultado_total_ars > 0        # +18% en pesos
    assert k.resultado_total_usd < 0        # pero perdió en dólares
    assert k.rendimiento_total_usd_pct == pytest.approx(-21.33, rel=1e-2)


# ---------------------------------------------------------------------------
# TIR: el rendimiento acumulado no dice nada sin el tiempo
# ---------------------------------------------------------------------------

def test_tir_casos_conocidos():
    from datetime import date
    from places.inversiones.cartera.posiciones import tir
    # 100 → 110 en un año = 10% anual
    assert tir([(date(2025, 1, 1), -100), (date(2026, 1, 1), 110)]) == \
        pytest.approx(0.10, abs=1e-3)
    # 100 → 121 en dos años = 10% anual (capitalizado, no 10,5%)
    assert tir([(date(2024, 1, 1), -100), (date(2026, 1, 1), 121)]) == \
        pytest.approx(0.10, abs=1e-3)
    # pérdida
    assert tir([(date(2025, 1, 1), -100), (date(2026, 1, 1), 90)]) == \
        pytest.approx(-0.10, abs=1e-3)


def test_tir_pondera_cuando_entro_cada_aporte():
    """Dos aportes iguales, uno al principio y otro casi al final: la TIR
    debe ser mayor que el rendimiento acumulado simple, porque la mitad del
    capital estuvo invertida poco tiempo."""
    from datetime import date
    from places.inversiones.cartera.posiciones import tir
    flujos = [
        (date(2025, 1, 1), -100),    # estuvo 1 año
        (date(2025, 12, 1), -100),   # estuvo 1 mes
        (date(2026, 1, 1), 220),     # patrimonio final
    ]
    r = tir(flujos)
    acumulado = 220 / 200 - 1        # +10% sobre el total aportado
    assert r > acumulado             # la TIR anualizada es mayor


def test_tir_devuelve_none_sin_solucion():
    from datetime import date
    from places.inversiones.cartera.posiciones import tir
    assert tir([]) is None
    assert tir([(date(2025, 1, 1), -100)]) is None          # un solo flujo
    assert tir([(date(2025, 1, 1), -100),
                (date(2026, 1, 1), -50)]) is None           # todos negativos


def test_kpis_calculan_periodo_y_tir():
    from datetime import date
    from places.inversiones.cartera.kpis import completar_patrimonio
    pos = {"A": Posicion("A", cant_comprada=10, costo_ars_compras=1000.0)}
    k = kpis_de(valuar(pos, _resolver_fijo({"A": 110.0}), mep_actual=1000.0), mep=1000.0)
    flujos = [(date(2025, 1, 1), -1000.0, -1.0)]
    completar_patrimonio(k, _Cap(1000.0, 1.0), 0.0, 0.0, 1000.0,
                         flujos, date(2026, 1, 1))
    assert k.dias == 365
    assert k.anios == pytest.approx(1.0)
    assert k.tir_ars == pytest.approx(0.10, abs=1e-3)   # 1000 → 1100 en un año
