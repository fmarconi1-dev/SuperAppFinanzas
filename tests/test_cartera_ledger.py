"""Tests del motor cronológico de la cartera (Fase 3b, paso 1).

Lo que protegen: que el costo de una venta sea el **vigente al momento de la
venta** y no el promedio de toda la historia, y que el motor no invente costo
ni explote con los datos incompletos que ya nos costaron caro en la Fase 3a
(pagarés sin cantidad, ventas por encima de lo registrado).
"""

from datetime import date

import pytest

from places.inversiones.cartera.ledger import (
    Evento, eventos_desde_movimientos, recorrer,
)


def ev(dia, categoria, ticker="ACME", cantidad=0.0, monto=0.0,
       moneda="ARS", tc=None):
    return Evento(
        fecha=date(2025, 1, dia), categoria=categoria, ticker=ticker,
        cantidad=cantidad, monto=monto, moneda=moneda, tc_mep=tc,
    )


# ---------------------------------------------------------------------------
# El motivo de existir del módulo
# ---------------------------------------------------------------------------

def test_el_ppc_es_el_vigente_al_vender_no_el_de_toda_la_historia():
    """Comprar, vender, y recomprar más caro NO puede cambiar el resultado
    de la venta ya hecha.

    Con PPC global (el método de `posiciones.py`) el costo de la venta sería
    (1.000 + 3.000) / 20 = 200 por unidad → daría una pérdida de 500 sobre una
    operación que en realidad ganó 500.
    """
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),   # PPC 100
        ev(2, "VENTA", cantidad=-10, monto=1500),    # vende a 150
        ev(3, "COMPRA", cantidad=10, monto=-3000),   # recompra a 300
    ])
    (r,) = led.realizaciones
    assert r.costo_ars == pytest.approx(1000)
    assert r.resultado_ars == pytest.approx(500)
    assert r.rendimiento_pct == pytest.approx(50)
    # y la tenencia que queda es la recompra, a su propio precio
    est = led.estados["ACME"]
    assert est.cantidad == pytest.approx(10)
    assert est.ppc_ars == pytest.approx(300)


def test_el_orden_de_entrada_no_altera_el_resultado():
    """Los movimientos llegan de la DB sin ORDER BY: el motor los ordena."""
    eventos = [
        ev(3, "COMPRA", cantidad=10, monto=-3000),
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "VENTA", cantidad=-10, monto=1500),
    ]
    a = recorrer(eventos)
    b = recorrer(list(reversed(eventos)))
    assert a.realizado_ars == b.realizado_ars == pytest.approx(500)


def test_compra_y_venta_el_mismo_dia_la_compra_va_primero():
    """El export no trae hora; si la venta se procesara primero quedaría
    descubierta y sin costo."""
    led = recorrer([
        ev(5, "VENTA", cantidad=-10, monto=1500),
        ev(5, "COMPRA", cantidad=10, monto=-1000),
    ])
    (r,) = led.realizaciones
    assert not r.descubierta
    assert r.resultado_ars == pytest.approx(500)


# ---------------------------------------------------------------------------
# Costo promedio ponderado móvil
# ---------------------------------------------------------------------------

def test_venta_parcial_libera_la_parte_proporcional_del_costo():
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),   # 100 c/u
        ev(2, "COMPRA", cantidad=10, monto=-2000),   # 200 c/u → PPC 150
        ev(3, "VENTA", cantidad=-5, monto=900),      # vende 5 a 180
    ])
    (r,) = led.realizaciones
    assert r.ppc_ars == pytest.approx(150)
    assert r.costo_ars == pytest.approx(750)
    assert r.resultado_ars == pytest.approx(150)
    est = led.estados["ACME"]
    assert est.cantidad == pytest.approx(15)
    assert est.costo_ars == pytest.approx(2250)      # 3.000 − 750
    assert est.ppc_ars == pytest.approx(150)         # vender no mueve el PPC


def test_cerrar_toda_la_posicion_no_deja_costo_colgado():
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "VENTA", cantidad=-10, monto=1200),
    ])
    est = led.estados["ACME"]
    assert est.cantidad == 0
    assert est.costo_ars == 0
    assert est.ppc_ars is None
    assert est.realizado_ars == pytest.approx(200)


# ---------------------------------------------------------------------------
# Las dos monedas, cada una al TC de su fecha (ADR-0003 / ADR-0004)
# ---------------------------------------------------------------------------

def test_operacion_en_pesos_se_mide_en_usd_al_mep_de_su_fecha():
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000, tc=1000),   # US$1
        ev(2, "VENTA", cantidad=-10, monto=1500, tc=1500),    # US$1
    ])
    (r,) = led.realizaciones
    assert r.costo_usd == pytest.approx(1.0)
    assert r.ingreso_usd == pytest.approx(1.0)
    # Ganó 50% en pesos y nada en dólares: exactamente la devaluación.
    assert r.resultado_ars == pytest.approx(500)
    assert r.resultado_usd == pytest.approx(0.0)


def test_operacion_denominada_en_dolares():
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-100, moneda="USD", tc=1000),
        ev(2, "VENTA", cantidad=-10, monto=150, moneda="USD", tc=1500),
    ])
    (r,) = led.realizaciones
    assert r.costo_usd == pytest.approx(100)
    assert r.costo_ars == pytest.approx(100_000)     # al MEP de su día
    assert r.resultado_usd == pytest.approx(50)


def test_sin_tc_los_importes_en_usd_quedan_en_cero_pero_no_rompe():
    """Los objetos del parser todavía no tienen el TC congelado."""
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "VENTA", cantidad=-10, monto=1500),
    ])
    (r,) = led.realizaciones
    assert r.resultado_ars == pytest.approx(500)
    assert r.resultado_usd == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Datos incompletos: las trampas ya conocidas de la Fase 3a
# ---------------------------------------------------------------------------

def test_vender_mas_de_lo_registrado_se_marca_y_no_inventa_costo():
    """Caso real: el ajuste de ratio de CEDEAR no genera movimiento, así que
    la línea de tiempo puede tener menos unidades que la realidad."""
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "VENTA", cantidad=-15, monto=2250),
    ])
    (r,) = led.realizaciones
    assert r.descubierta
    assert r.costo_ars == pytest.approx(1000)        # solo lo que había
    assert led.advertencias and "excedente" in led.advertencias[0]


def test_compra_sin_cantidad_acumula_costo_y_avisa():
    """El pagaré: el movimiento trae el monto pero no las unidades."""
    led = recorrer([ev(1, "COMPRA", ticker="#UMV1", cantidad=0, monto=-5032.12)])
    est = led.estados["#UMV1"]
    assert est.costo_ars == pytest.approx(5032.12)
    assert est.cantidad == 0
    assert est.ppc_ars is None                       # sin unidades no hay PPC
    assert led.advertencias and "sin cantidad" in led.advertencias[0]


def test_venta_sin_cantidad_no_genera_realizacion():
    led = recorrer([ev(1, "VENTA", cantidad=0, monto=100)])
    assert led.realizaciones == []


# ---------------------------------------------------------------------------
# Cobros: no tocan la tenencia (convención argentina de amortización)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("categoria", ["AMORTIZACION", "RENTA", "DIVIDENDO"])
def test_los_cobros_no_cambian_ni_cantidad_ni_costo(categoria):
    """En Argentina la amortización se refleja en el **precio**, no en los
    nominales: el broker deja la cantidad quieta."""
    led = recorrer([
        ev(1, "COMPRA", cantidad=100, monto=-6000),
        ev(2, categoria, monto=250),
    ])
    est = led.estados["ACME"]
    assert est.cantidad == pytest.approx(100)
    assert est.costo_ars == pytest.approx(6000)
    assert est.ppc_ars == pytest.approx(60)
    assert est.flujos_ars == pytest.approx(250)


def test_la_retencion_se_guarda_aparte_del_dividendo():
    """Para poder mostrar el dividendo bruto y el neto (punto 3 de la 3b)."""
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "DIVIDENDO", monto=100),
        ev(2, "RETENCION", monto=-9.7),
    ])
    est = led.estados["ACME"]
    assert est.flujos_ars == pytest.approx(100)
    assert est.retenciones_ars == pytest.approx(-9.7)


# ---------------------------------------------------------------------------
# Plazo de tenencia
# ---------------------------------------------------------------------------

def test_la_fecha_de_compra_promedio_pondera_por_costo():
    """Dos compras de igual costo → el promedio cae justo en el medio."""
    led = recorrer([
        Evento(date(2025, 1, 1), "COMPRA", "ACME", 10, -1000, "ARS", None),
        Evento(date(2025, 1, 11), "COMPRA", "ACME", 10, -1000, "ARS", None),
        Evento(date(2025, 1, 21), "VENTA", "ACME", -20, 3000, "ARS", None),
    ])
    (r,) = led.realizaciones
    assert r.fecha_compra_prom == date(2025, 1, 6)
    assert r.dias == 15


# ---------------------------------------------------------------------------
# Adaptador desde el parser
# ---------------------------------------------------------------------------

class _MovFalso:
    def __init__(self, **kw):
        self.__dict__.update(
            dict(fecha_concertacion=date(2025, 1, 1), categoria="COMPRA",
                 ticker_base="ACME", cantidad=1.0, monto=-10.0, moneda="ARS",
                 es_instrumento=True, es_espejo=False, tc_mep=None),
            **kw,
        )


def test_el_adaptador_filtra_espejos_y_no_instrumentos():
    movs = [
        _MovFalso(),
        _MovFalso(es_espejo=True),                        # espejo ARS de dividendo
        _MovFalso(es_instrumento=False, categoria="DEPOSITO"),
    ]
    assert len(eventos_desde_movimientos(movs)) == 1
