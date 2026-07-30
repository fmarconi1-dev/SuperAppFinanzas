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


# ---------------------------------------------------------------------------
# Enchufe con kpis.valuar() — ADR-0005
# ---------------------------------------------------------------------------

def test_realizado_por_ticker_agrupa_las_ventas():
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "VENTA", cantidad=-5, monto=750),      # +250
        ev(3, "VENTA", cantidad=-5, monto=600),      # +100
        ev(4, "COMPRA", ticker="OTRO", cantidad=1, monto=-50),
    ])
    d = led.realizado_por_ticker()
    assert d["ACME"][0] == pytest.approx(350)
    # un ticker sin ventas aparece en cero, para que quien consuma no se caiga
    # al PPC global por ausencia de clave
    assert d["OTRO"] == (0.0, 0.0)


def test_valuar_usa_el_realizado_del_ledger_cuando_se_lo_pasan():
    """El mismo caso que motivó el ADR-0005, extremo a extremo."""
    from places.inversiones.cartera.kpis import valuar
    from places.inversiones.cartera.posiciones import posiciones as pos_de

    movs = [
        _MovFalso(fecha_concertacion=date(2025, 1, 1), categoria="COMPRA",
                  cantidad=10.0, monto=-1000.0),
        _MovFalso(fecha_concertacion=date(2025, 1, 2), categoria="VENTA",
                  cantidad=-10.0, monto=1500.0),
        _MovFalso(fecha_concertacion=date(2025, 1, 3), categoria="COMPRA",
                  cantidad=10.0, monto=-3000.0),
    ]
    pos = pos_de(movs)
    led = recorrer(eventos_desde_movimientos(movs))

    (sin_ledger,) = valuar(pos, lambda t, i: (300.0, "test"))
    (con_ledger,) = valuar(pos, lambda t, i: (300.0, "test"),
                           cronologico=led.plano_por_ticker())

    assert sin_ledger.realizado_ars == pytest.approx(-500)   # PPC global: 200
    assert con_ledger.realizado_ars == pytest.approx(500)    # PPC del día: 100


# ---------------------------------------------------------------------------
# Lo que consume la vista (pura, testeable sin Streamlit)
# ---------------------------------------------------------------------------

def _led_dos_ventas():
    return recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "VENTA", cantidad=-5, monto=750),      # +250 (+50%)
        ev(3, "COMPRA", ticker="OTRO", cantidad=10, monto=-1000),
        ev(4, "VENTA", ticker="OTRO", cantidad=-10, monto=800),   # −200 (−20%)
    ])


def test_tabla_de_operaciones_va_de_la_mas_reciente_a_la_mas_vieja():
    filas = _led_dos_ventas().tabla_operaciones()
    assert [f["Ticker"] for f in filas] == ["OTRO", "ACME"]
    assert filas[1]["PPC del día"] == pytest.approx(100)
    assert filas[1]["Precio venta"] == pytest.approx(150)
    assert filas[1]["Resultado"] == pytest.approx(250)
    assert filas[1]["Aviso"] == ""


def test_resumen_de_operaciones_cuenta_aciertos_y_extremos():
    res = _led_dos_ventas().resumen_operaciones()
    assert res["n"] == 2
    assert res["ganadoras"] == 1
    assert res["total_ars"] == pytest.approx(50)     # +250 − 200
    assert res["mejor"].ticker == "ACME"
    assert res["peor"].ticker == "OTRO"


def test_resumen_sin_operaciones_no_rompe():
    res = recorrer([ev(1, "COMPRA", cantidad=1, monto=-10)]).resumen_operaciones()
    assert res["n"] == 0 and res["mejor"] is None and res["total_ars"] == 0


def test_la_venta_descubierta_se_marca_en_la_tabla():
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "VENTA", cantidad=-15, monto=2250),
    ])
    assert led.tabla_operaciones()[0]["Aviso"] == "revisar"


# ---------------------------------------------------------------------------
# Identidad contable: las dos mitades tienen que sumar el total comprado
# ---------------------------------------------------------------------------

def test_costo_liberado_mas_costo_remanente_es_el_total_comprado():
    """La lección de la Fase 3a: todo agregado se contrasta contra una
    identidad independiente antes de mostrarse.

    Si el realizado se midiera al PPC del día y el remanente al promedio de
    toda la historia, esta suma no daría — y el resultado por ticker estaría
    contando plata que no existe.
    """
    eventos = [
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "VENTA", cantidad=-4, monto=600),
        ev(3, "COMPRA", cantidad=10, monto=-3000),
        ev(4, "VENTA", cantidad=-6, monto=1800),
        ev(5, "COMPRA", cantidad=5, monto=-1500),
    ]
    led = recorrer(eventos)
    est = led.estados["ACME"]
    total_comprado = sum(-e.monto for e in eventos if e.categoria == "COMPRA")
    liberado = sum(r.costo_ars for r in led.realizaciones)
    assert liberado + est.costo_ars == pytest.approx(total_comprado)
    # y las unidades cierran igual
    assert est.cantidad == pytest.approx(15)


# ---------------------------------------------------------------------------
# Guarda contra datos malos: no mostrar un error como si fuera un acierto
# ---------------------------------------------------------------------------

def test_una_venta_con_rendimiento_absurdo_se_marca_para_revisar():
    """Caso real (ASML): el movimiento de compra dice 9 unidades a $60,10 y la
    venta fue a $13.840 → +22.754%. No es un trade, es un dato malo."""
    led = recorrer([
        ev(1, "COMPRA", cantidad=9, monto=-543.05),
        ev(2, "VENTA", cantidad=-9, monto=124_107.85),
    ])
    (r,) = led.realizaciones
    assert r.sospechosa
    assert led.tabla_operaciones()[0]["Aviso"] == "revisar"
    assert any("revisá ese movimiento" in a for a in led.advertencias)


def test_la_sospechosa_no_puede_ser_la_mejor_operacion():
    led = recorrer([
        ev(1, "COMPRA", cantidad=9, monto=-543.05),
        ev(2, "VENTA", cantidad=-9, monto=124_107.85),      # +22.754%
        ev(3, "COMPRA", ticker="OTRO", cantidad=10, monto=-1000),
        ev(4, "VENTA", ticker="OTRO", cantidad=-10, monto=1300),   # +30%
    ])
    res = led.resumen_operaciones()
    assert res["mejor"].ticker == "OTRO"
    assert res["a_revisar"] == 1


def test_un_trade_muy_bueno_pero_creible_no_se_marca():
    led = recorrer([
        ev(1, "COMPRA", cantidad=10, monto=-1000),
        ev(2, "VENTA", cantidad=-10, monto=9000),      # +800%: raro pero posible
    ])
    assert not led.realizaciones[0].sospechosa
