"""Benchmark money-weighted: la cartera contra el índice, con los mismos flujos.

El error que estos tests existen para impedir es el de comparar acumulados.
Franco aportó en 24 momentos distintos; el índice "aportó" todo el día uno. Un
test central acá (`test_money_weighted_no_es_lo_mismo_que_comparar_acumulados`)
construye a propósito el caso donde las dos formas de medir dan resultados
opuestos, para que nadie "simplifique" el módulo hacia la respuesta fácil.
"""

from __future__ import annotations

from datetime import date

import pytest

from core.market_data import indices
from places.inversiones.cartera import benchmark as bm

HOY = date(2026, 8, 27)


# Serie de juguete: el índice arranca en 100 y termina en 200 (+100%).
SERIE = {
    "2026-01-02": 100.0,
    "2026-03-02": 100.0,
    "2026-06-01": 200.0,
    "2026-08-27": 200.0,
}


# ---------------------------------------------------------------------------
# indices.valor_en — el día que no cotiza
# ---------------------------------------------------------------------------

def test_valor_en_toma_el_cierre_del_dia():
    assert indices.valor_en(SERIE, date(2026, 1, 2)) == 100.0


def test_un_domingo_toma_el_cierre_anterior():
    """Un depósito puede caer sábado. El mercado no abrió: vale el viernes."""
    assert indices.valor_en(SERIE, date(2026, 1, 4)) == 100.0


def test_un_hueco_grande_no_se_estira():
    """Más allá del tope no hay 'último cierre': hay un agujero, y se dice."""
    assert indices.valor_en(SERIE, date(2026, 5, 30), dias_atras=10) is None


def test_una_fecha_anterior_a_la_serie_no_tiene_precio():
    assert indices.valor_en(SERIE, date(2025, 1, 1)) is None


def test_serie_vacia_no_revienta():
    assert indices.valor_en({}, date(2026, 1, 2)) is None


# ---------------------------------------------------------------------------
# simular — la aritmética del contrafáctico
# ---------------------------------------------------------------------------

def test_un_solo_aporte_replica_el_rendimiento_del_indice():
    """US$100 el día que el índice vale 100 → 1 unidad → US$200 hoy."""
    sim = bm.simular([(date(2026, 1, 2), -100.0)], SERIE, HOY)
    assert sim.unidades == pytest.approx(1.0)
    assert sim.valor_final == pytest.approx(200.0)
    assert sim.aportado == pytest.approx(100.0)
    assert sim.rendimiento == pytest.approx(1.0)


def test_money_weighted_no_es_lo_mismo_que_comparar_acumulados():
    """**El test que justifica el módulo.**

    El índice hizo +100% en el período. Pero si casi toda la plata entró
    *después* de la suba, el contrafáctico NO rinde 100%: rinde mucho menos,
    porque esa plata no estuvo puesta durante la suba. Comparar el +100% del
    índice contra el rendimiento de la cartera sería comparar dos preguntas
    distintas.
    """
    flujos = [
        (date(2026, 1, 2), -100.0),      # entra barato: compra 1 unidad
        (date(2026, 6, 1), -900.0),      # entra caro: compra 4,5 unidades
    ]
    sim = bm.simular(flujos, SERIE, HOY)

    assert sim.aportado == pytest.approx(1000.0)
    assert sim.unidades == pytest.approx(5.5)
    assert sim.valor_final == pytest.approx(1100.0)
    # +10%, no +100%. Esa es toda la diferencia.
    assert sim.rendimiento == pytest.approx(0.10)
    assert sim.rendimiento < 1.0


def test_un_retiro_vende_unidades():
    flujos = [(date(2026, 1, 2), -200.0), (date(2026, 6, 1), 100.0)]
    sim = bm.simular(flujos, SERIE, HOY)
    assert sim.unidades == pytest.approx(1.5)     # 2 compradas − 0,5 vendidas
    assert sim.aportado == pytest.approx(100.0)
    assert sim.valor_final == pytest.approx(300.0)


def test_nadie_vende_lo_que_no_tiene():
    """Un retiro mayor que lo acumulado clampea en cero y queda marcado."""
    flujos = [(date(2026, 1, 2), -100.0), (date(2026, 6, 1), 5000.0)]
    sim = bm.simular(flujos, SERIE, HOY)
    assert sim.unidades == pytest.approx(0.0)
    assert sim.sobregiro is True


def test_un_flujo_sin_precio_se_informa_no_se_estima():
    """Un aporte anterior al inicio de la serie no se inventa."""
    flujos = [(date(2020, 1, 1), -500.0), (date(2026, 1, 2), -100.0)]
    sim = bm.simular(flujos, SERIE, HOY)
    assert sim.sin_precio == [date(2020, 1, 1)]
    assert sim.completa is False
    assert sim.n_flujos == 1
    assert sim.aportado == pytest.approx(100.0)   # el no usable no suma


def test_todos_los_flujos_usables_dan_completa():
    sim = bm.simular([(date(2026, 1, 2), -100.0)], SERIE, HOY)
    assert sim.completa is True
    assert sim.sin_precio == []


def test_sin_serie_devuelve_none():
    assert bm.simular([(date(2026, 1, 2), -100.0)], {}, HOY) is None


def test_sin_flujos_devuelve_none():
    assert bm.simular([], SERIE, HOY) is None


def test_ningun_flujo_utilizable_devuelve_none():
    """Prefiere no mostrar nada antes que una comparación vacía con forma de 0."""
    assert bm.simular([(date(2020, 1, 1), -100.0)], SERIE, HOY) is None


def test_la_tir_usa_el_mismo_motor_que_la_cartera():
    """Duplicar la plata en ~8 meses da una TIR anualizada bastante mayor a 100%."""
    sim = bm.simular([(date(2026, 1, 2), -100.0)], SERIE, HOY)
    assert sim.tir is not None
    assert sim.tir > 1.0


# ---------------------------------------------------------------------------
# flujos_en — no cruzar monedas (trampa nº 1 del proyecto)
# ---------------------------------------------------------------------------

def test_flujos_en_usd_toma_la_columna_de_dolares():
    flujos = [(date(2026, 1, 2), -100000.0, -100.0)]
    assert bm.flujos_en(flujos, "USD") == [(date(2026, 1, 2), -100.0)]


def test_flujos_en_ars_toma_la_columna_de_pesos():
    flujos = [(date(2026, 1, 2), -100000.0, -100.0)]
    assert bm.flujos_en(flujos, "ARS") == [(date(2026, 1, 2), -100000.0)]


def test_un_contravalor_en_cero_no_es_un_flujo():
    """Sin TC congelado el contravalor queda en 0. Eso es un dato faltante, no
    un día sin aportes: sumarlo mentiría sobre el capital puesto."""
    flujos = [(date(2026, 1, 2), -100000.0, 0.0),
              (date(2026, 3, 2), -50000.0, -50.0)]
    assert bm.flujos_en(flujos, "USD") == [(date(2026, 3, 2), -50.0)]
    assert len(bm.flujos_en(flujos, "ARS")) == 2


# ---------------------------------------------------------------------------
# comparar
# ---------------------------------------------------------------------------

def test_comparar_dice_cuanto_le_ganaste_al_indice():
    sim = bm.simular([(date(2026, 1, 2), -100.0)], SERIE, HOY)   # → US$200
    c = bm.comparar(sim, valor_real=250.0)
    assert c["valor_indice"] == pytest.approx(200.0)
    assert c["diferencia"] == pytest.approx(50.0)
    assert c["ganaste"] is True


def test_comparar_tambien_dice_cuando_perdiste():
    sim = bm.simular([(date(2026, 1, 2), -100.0)], SERIE, HOY)
    c = bm.comparar(sim, valor_real=150.0)
    assert c["diferencia"] == pytest.approx(-50.0)
    assert c["ganaste"] is False


def test_comparar_sin_simulacion_o_sin_patrimonio_no_inventa():
    assert bm.comparar(None, 100.0) is None
    sim = bm.simular([(date(2026, 1, 2), -100.0)], SERIE, HOY)
    assert bm.comparar(sim, None) is None


def test_comparar_usa_el_aportado_real_si_se_lo_dan():
    """El aportado de la cartera puede diferir del que entró al contrafáctico
    (flujos sin precio). Se pasa explícito para no comparar contra otro capital."""
    sim = bm.simular([(date(2026, 1, 2), -100.0)], SERIE, HOY)
    c = bm.comparar(sim, valor_real=250.0, aportado_real=120.0)
    assert c["aportado"] == pytest.approx(120.0)
    assert c["resultado_real"] == pytest.approx(130.0)


# ---------------------------------------------------------------------------
# indices.serie_historica — sin red
# ---------------------------------------------------------------------------

def test_serie_historica_parsea_adjclose():
    crudo = {
        "chart": {"result": [{
            "timestamp": [1767312000, 1767398400],
            "indicators": {
                "quote": [{"close": [10.0, 11.0]}],
                "adjclose": [{"adjclose": [9.5, 10.5]}],
            },
        }]}
    }
    s = indices.serie_historica("SPY", fetch=lambda url: crudo)
    assert list(s.values()) == [9.5, 10.5]     # ajustado, no el close crudo


def test_serie_historica_cae_a_close_sin_adjclose():
    crudo = {"chart": {"result": [{
        "timestamp": [1767312000],
        "indicators": {"quote": [{"close": [10.0]}]},
    }]}}
    assert list(indices.serie_historica("MERVAL",
                                        fetch=lambda url: crudo).values()) == [10.0]


def test_los_nulls_de_yahoo_se_descartan():
    crudo = {"chart": {"result": [{
        "timestamp": [1767312000, 1767398400],
        "indicators": {"quote": [{"close": [None, 11.0]}]},
    }]}}
    assert len(indices.serie_historica("SPY", fetch=lambda url: crudo)) == 1


def test_una_fuente_caida_no_puede_tumbar_la_pantalla():
    def revienta(url):
        raise RuntimeError("Yahoo caído")
    assert indices.serie_historica("SPY", fetch=revienta) == {}
