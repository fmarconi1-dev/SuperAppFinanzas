"""Tests de los rendimientos de la caja (Fase 3b, punto 3).

Lo que protegen: que la tasa de las cauciones se pondere por capital y tiempo
(promediar las TNA sueltas engaña), que el apareo no invente contrapartes, y
que el dividendo que se muestra sea el **neto** de retención.
"""

from datetime import date

import pytest

from places.inversiones.cartera.rendimientos import (
    cauciones, dividendos_por_ticker, resumir_cauciones, total_remuneracion,
)


def col(dia, monto, liq=None, mes=1, tc=None):
    return ("CAUCION_COL", date(2025, mes, dia), date(2025, mes, liq or dia),
            -monto, "ARS", tc)


def vto(dia, monto, liq, mes=1, tc=None):
    return ("CAUCION_VTO", date(2025, mes, dia), date(2025, mes, liq),
            monto, "ARS", tc)


# ---------------------------------------------------------------------------
# Apareo
# ---------------------------------------------------------------------------

def test_aparea_por_fecha_de_concertacion_y_el_plazo_sale_de_la_liquidacion():
    """Las dos patas comparten la concertación; el plazo es la diferencia
    entre las fechas de liquidación (verificado en los 101 pares reales)."""
    (c,) = cauciones([col(6, 520_744.00), vto(6, 520_973.09, liq=7)])
    assert c.fecha == date(2025, 1, 6)
    assert c.capital == pytest.approx(520_744.00)
    assert c.interes == pytest.approx(229.09)
    assert c.dias == 1
    assert c.tna == pytest.approx(0.16058, rel=1e-3)   # ~16,1% anual
    assert not c.abierta


def test_un_fin_de_semana_son_tres_dias_no_uno():
    (c,) = cauciones([col(3, 186_511.00), vto(3, 186_766.31, liq=6)])
    assert c.dias == 3
    assert c.tna == pytest.approx(0.16652, rel=1e-3)


def test_colocacion_sin_vencimiento_queda_abierta_y_sin_tasa():
    """O la caución sigue viva, o el export se cortó. No se inventa el cobro."""
    (c,) = cauciones([col(10, 100_000)])
    assert c.abierta
    assert c.interes == 0
    assert c.tna is None


def test_vencimiento_sin_colocacion_se_descarta():
    """Caución colocada antes del inicio del registro: sin capital no hay tasa."""
    assert cauciones([vto(10, 100_500, liq=11)]) == []


def test_varias_cauciones_el_mismo_dia_se_aparean_por_monto():
    cs = cauciones([
        col(10, 100_000), col(10, 20_000),
        vto(10, 100_500, liq=11), vto(10, 20_050, liq=11),
    ])
    assert len(cs) == 2
    grande = next(c for c in cs if c.capital == 100_000)
    chica = next(c for c in cs if c.capital == 20_000)
    assert grande.interes == pytest.approx(500)
    assert chica.interes == pytest.approx(50)


def test_sin_fecha_de_liquidacion_no_hay_plazo_ni_tasa_pero_no_rompe():
    filas = [("CAUCION_COL", date(2025, 1, 10), None, -100_000, "ARS", None),
             ("CAUCION_VTO", date(2025, 1, 10), None, 100_500, "ARS", None)]
    (c,) = cauciones(filas)
    assert c.interes == pytest.approx(500)
    assert c.dias is None and c.tna is None


def test_las_cauciones_se_devuelven_ordenadas_por_fecha():
    cs = cauciones([col(20, 1), vto(20, 1, liq=21),
                    col(5, 1), vto(5, 1, liq=6)])
    assert [c.fecha.day for c in cs] == [5, 20]


# ---------------------------------------------------------------------------
# La tasa: ponderada por capital y tiempo
# ---------------------------------------------------------------------------

def test_la_tna_ponderada_no_es_el_promedio_de_las_tna():
    """El caso que motivó la métrica: una caución chica de un día con una tasa
    altísima no puede pesar lo mismo que una grande de cinco días.

    Chica: 20.000 a 1 día ganando 50 → 91,25% anual.
    Grande: 1.000.000 a 5 días ganando 685 → 5,0% anual.
    El promedio simple daría ~48%; lo que de verdad rindió el capital es 5,3%.
    """
    cs = cauciones([
        col(10, 20_000), vto(10, 20_050, liq=11),
        col(20, 1_000_000), vto(20, 1_000_685, liq=25),
    ])
    r = resumir_cauciones(cs)
    promedio_simple = sum(c.tna for c in cs) / len(cs)
    assert promedio_simple == pytest.approx(0.4813, rel=1e-2)
    assert r.tna_ponderada == pytest.approx(0.05344, rel=1e-3)
    assert r.tna_ponderada < promedio_simple / 5


def test_el_resumen_suma_interes_y_capital_rotado():
    cs = cauciones([
        col(10, 100_000), vto(10, 100_500, liq=11),
        col(20, 200_000), vto(20, 201_000, liq=21),
    ])
    r = resumir_cauciones(cs)
    assert r.n == 2 and r.abiertas == 0
    assert r.capital_rotado == pytest.approx(300_000)
    assert r.interes == pytest.approx(1_500)
    assert r.primera == date(2025, 1, 10) and r.ultima == date(2025, 1, 20)


def test_las_abiertas_no_ensucian_la_tasa():
    cs = cauciones([
        col(10, 100_000), vto(10, 100_500, liq=11),
        col(20, 5_000_000),                       # abierta: sin vencimiento
    ])
    r = resumir_cauciones(cs)
    assert r.n == 2 and r.abiertas == 1
    assert r.capital_rotado == pytest.approx(100_000)   # la abierta no cuenta
    assert r.tna_ponderada == pytest.approx(1.825, rel=1e-3)


def test_resumen_por_anio():
    cs = cauciones([col(10, 100_000), vto(10, 100_500, liq=11)])
    cs += cauciones([("CAUCION_COL", date(2024, 5, 3), date(2024, 5, 3),
                      -50_000, "ARS", None),
                     ("CAUCION_VTO", date(2024, 5, 3), date(2024, 5, 4),
                      50_100, "ARS", None)])
    r = resumir_cauciones(cs)
    assert set(r.por_anio) == {2024, 2025}
    assert r.por_anio[2025][0] == 1
    assert r.por_anio[2024][1] == pytest.approx(100)


def test_resumen_vacio_no_rompe():
    r = resumir_cauciones([])
    assert r.n == 0 and r.tna_ponderada is None and r.por_anio == {}


def test_el_interes_en_dolares_usa_el_mep_del_dia():
    (c,) = cauciones([col(10, 100_000, tc=1000), vto(10, 101_000, liq=11)])
    assert c.interes_usd == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Dividendos: lo que entra a la cuenta es el neto
# ---------------------------------------------------------------------------

def test_la_retencion_se_resta_del_dividendo_del_mismo_ticker():
    """Caso real de GGAL: $34.680 brutos con $3.777 retenidos."""
    d = dividendos_por_ticker([
        ("DIVIDENDO", "GGAL", 34_680.57, "ARS", None, False),
        ("RETENCION", "GGAL", -3_777.18, "ARS", None, False),
    ])["GGAL"]
    assert d.n == 1
    assert d.bruto == pytest.approx(34_680.57)
    assert d.neto == pytest.approx(30_903.39)
    assert d.retencion_pct == pytest.approx(10.89, rel=1e-3)


def test_el_espejo_en_pesos_del_dividendo_en_dolares_se_ignora():
    """Regla del LEEME: del dividendo en dólares se cuenta solo la línea USD."""
    divs = dividendos_por_ticker([
        ("DIVIDENDO", "SPY", 10.40, "USD", 1500.0, False),
        ("DIVIDENDO", "SPY", -15_600.0, "ARS", 1500.0, True),   # espejo
    ])
    assert divs["SPY"].n == 1
    assert divs["SPY"].bruto_usd == pytest.approx(10.40)
    assert divs["SPY"].bruto == pytest.approx(15_600.0)   # al MEP de su día


def test_dividendo_sin_retencion_tiene_neto_igual_al_bruto():
    d = dividendos_por_ticker([
        ("DIVIDENDO", "TSM", 2.11, "USD", 1400.0, False),
    ])["TSM"]
    assert d.neto == d.bruto
    assert d.retencion_pct == 0.0


def test_otras_categorias_no_entran_a_dividendos():
    assert dividendos_por_ticker([
        ("COMPRA", "GGAL", -1000.0, "ARS", None, False),
        ("RENTA", "AE38", 100.0, "USD", None, False),
    ]) == {}


# ---------------------------------------------------------------------------
# Cuenta remunerada
# ---------------------------------------------------------------------------

def test_la_remuneracion_suma_en_las_dos_monedas():
    ars, usd, n = total_remuneracion([
        ("REMUNERACION", 186.52, "ARS", 1400.0),
        ("REMUNERACION", 43.71, "ARS", 1400.0),
        ("COMPRA", -1000.0, "ARS", 1400.0),
    ])
    assert n == 2
    assert ars == pytest.approx(230.23)
    assert usd == pytest.approx(230.23 / 1400.0)


# ---------------------------------------------------------------------------
# Identidad contable independiente (la lección de la Fase 3a)
# ---------------------------------------------------------------------------

def test_el_interes_apareado_es_el_neto_de_todos_los_movimientos_de_caucion():
    """Contraste contra una identidad que **no depende del apareo**.

    Sin importar cómo se emparejen las patas, la plata que las cauciones le
    dejaron a la cuenta es la suma de todos sus movimientos: lo que salió al
    colocar (negativo) más lo que volvió al vencer (positivo). Si el interés
    que reporta el resumen no coincide con eso, el apareo está mal.
    """
    filas = [
        col(10, 100_000), vto(10, 100_500, liq=11),
        col(15, 250_000), vto(15, 251_200, liq=18),
        col(20, 20_000), col(20, 30_000),
        vto(20, 20_050, liq=21), vto(20, 30_090, liq=21),
    ]
    neto_movimientos = sum(f[3] for f in filas)
    r = resumir_cauciones(cauciones(filas))
    assert r.interes == pytest.approx(neto_movimientos)
    assert r.interes == pytest.approx(1_840)
