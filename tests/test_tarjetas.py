"""Desarmar el pago de la tarjeta con su resumen (Fase D, paso 5, ADR-0009 §3).

El PDF no se lee acá (eso es `test_resumen_tarjeta.py`): el lector se
reemplaza por un `Resumen` armado a mano. Nombres inventados. Corte 17/10.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

import places.finanzas.core.resumen_tarjeta as rt
from core.api.archivos import ArchivoRecibido
from core.api.cotizaciones import CotizacionNoDisponible
from places.finanzas.core.comandos import ZONA, procesar, procesar_archivo, totales_mes
from places.finanzas.core.resumen_tarjeta import Consumo, Linea, Resumen
from tests.test_conciliacion import (  # noqa: F401 — el fixture `db`
    COMPRA, _cargar, _extracto, _mandar, _q, db,
)

UID = 1
AHORA = datetime(2026, 11, 20, 12, tzinfo=ZONA)
PAGO = "PAGO TARJETA VISA\nOPERACION 1234567890"


def _resumen(**cambios) -> Resumen:
    """VISA, cierre 29/10, vence 11/11. Gastos reales $62.900; la percepción, $10.000."""
    datos = dict(
        tarjeta="VISA", cierre_anterior=date(2026, 10, 1), vencimiento_anterior=date(2026, 10, 9),
        cierre=date(2026, 10, 29), vencimiento=date(2026, 11, 11),
        cierre_proximo=date(2026, 11, 26), vencimiento_proximo=date(2026, 12, 5),
        saldo_anterior=(5000000, 0), total=(0, 0),
        pagos=[Linea(date(2026, 10, 9), "SU PAGO EN PESOS", -5000000, 0)],
        consumos=[
            Consumo(date(2026, 4, 15), "TIENDA INVENTADA", 4000000, 0, "06/06", "3017"),
            Consumo(date(2026, 10, 20), "AIRBNB * HM5YBSHC9H USD 12,00", 0, 1200, None, "3017"),
            Consumo(date(2026, 10, 22), "CLUB INVENTADO", 2000000, 0, None, "5694"),
        ],
        cargos=[Linea(date(2026, 10, 29), "IIBB PERCEP-CABA 2,00%( 1000,00)", 40000, 0),
                Linea(date(2026, 10, 29), "IVA RG 4240 21%( 2000,00)", 250000, 0)],
        percepciones=[Linea(date(2026, 10, 29), "DB.RG 5617 30%", 1000000, 0)],
    )
    datos.update(cambios)
    return Resumen(**datos)


@pytest.fixture()
def pdf(monkeypatch):
    """El "PDF" que llega es el resumen que se le diga."""
    estado = {"resumen": _resumen()}
    monkeypatch.setattr(rt, "palabras_del_pdf", lambda datos: [])
    monkeypatch.setattr(rt, "leer_resumen", lambda palabras: estado["resumen"])
    return estado


def _dolar(valor=1540.0):
    return lambda fecha: (valor, fecha)


def _mandar_pdf(db, cotizador=_dolar(), cuando=AHORA):
    return procesar_archivo(db, ArchivoRecibido(tipo="pdf", datos=b"%PDF-", nombre="r.pdf"),
                            user_id=UID, ahora=cuando, cotizador=cotizador)


def _p(db, texto, cotizador=_dolar(), cuando=AHORA):
    return procesar(db, texto, user_id=UID, ahora=cuando, cotizador=cotizador)


def _extracto_con_pago(db, monto=-72900, extra=()):
    r = _mandar(db, _extracto([("30/10/2026", COMPRA.format("KIOSCO"), -500), *extra,
                               ("11/11/2026", PAGO, monto)]), cuando=AHORA)
    assert "Esperando el resumen" in r.texto
    return r


def _desarmados(db):
    return _q(db, "SELECT fecha, motivo, pasivos, ingresos FROM transacciones "
                  "WHERE comentario LIKE 'VISA ·%' ORDER BY id")


# ---------------------------------------------------------------- el orden: resumen y pago

def test_el_resumen_antes_que_el_pago_se_guarda(db, pdf):
    r = _mandar_pdf(db)
    assert "Guardé el resumen VISA, cierre 29/10, vence 11/11" in r.texto
    assert r.resultado == "archivo"
    assert _q(db, "SELECT tarjeta, estado FROM resumenes") == [("VISA", "esperando_pago")]
    assert "Ya tenía guardado" in _mandar_pdf(db).texto


def test_cuando_llega_el_pago_se_propone_el_desarmado(db, pdf):
    _mandar_pdf(db)
    _extracto_con_pago(db)
    r = _p(db, "1 compras, ok")                    # el KIOSCO del extracto
    assert r.resultado == "lote"
    assert "Y ahora el resumen que esperaba este pago" in r.texto
    assert "Lo pagaste el 11/11 en la caja: $72.900" in r.texto
    assert "FIMA" not in r.texto                     # los saldos, después del desarmado


def test_el_pago_ya_estaba_y_llega_el_resumen(db, pdf):
    _extracto_con_pago(db)
    _p(db, "1 compras, ok")
    r = _mandar_pdf(db)
    assert r.resultado == "pendiente" and "Se desarma en (todo con fecha 11/11)" in r.texto


# ---------------------------------------------------------------- el desarmado

def _hasta_el_desarmado(db):
    _extracto_con_pago(db)
    _p(db, "1 compras, ok")
    return _mandar_pdf(db)


def test_el_desarmado_de_punta_a_punta(db, pdf):
    r = _hasta_el_desarmado(db)
    assert "1. TIENDA INVENTADA (06/06) $40.000 → ¿categoría?" in r.texto
    assert "AIRBNB * HM5YBSHC9H USD 12,00 USD 12 = $18.480 → ¿categoría? (+ Venta divisa)" in r.texto
    assert "IIBB PERCEP-CABA 2,00%( 1000,00) $400 → Impuestos" in r.texto
    assert "Percepción 30% (se devuelve): +$10.000" in r.texto
    r = _p(db, "1 compras, 2 salidas, 3 salidas, ok")
    assert r.resultado == "lote" and "Desarmé el pago de VISA" in r.texto
    assert "FIMA" in r.texto                         # ahora sí, los saldos
    assert _desarmados(db) == [
        ("2026-11-11", "Compras", 40000.0, 0.0),
        ("2026-11-11", "Salidas", 18480.0, 0.0), ("2026-11-11", "Venta divisa", 0.0, 18480.0),
        ("2026-11-11", "Salidas", 20000.0, 0.0),
        ("2026-11-11", "Impuestos", 400.0, 0.0), ("2026-11-11", "Impuestos", 2500.0, 0.0),
        ("2026-11-11", "Percepción 30% (se devuelve)", 10000.0, 0.0),
    ]
    assert _q(db, "SELECT estado FROM banco_filas WHERE tipo = 'PAGO TARJETA VISA'") == [
        ("desarmada",)]
    assert _q(db, "SELECT estado, pagado FROM resumenes") == [("desarmado", 7290000)]


def test_lo_desarmado_suma_justo_lo_pagado(db, pdf):
    _hasta_el_desarmado(db)
    _p(db, "1 compras, 2 salidas, 3 salidas, ok")
    neto = sum(i - p for _, _, p, i in _desarmados(db))
    assert round(neto, 2) == -72900.0               # el saldo baja lo mismo que la caja


def test_la_percepcion_no_es_gasto(db, pdf):
    _hasta_el_desarmado(db)
    _p(db, "1 compras, 2 salidas, 3 salidas, ok")
    t = totales_mes(db, user_id=UID, hoy=date(2026, 11, 30))
    assert t.gastos == 40000 + 18480 + 20000 + 400 + 2500      # la percepción no suma


def test_aprende_la_categoria_del_comercio_de_la_tarjeta(db, pdf):
    _hasta_el_desarmado(db)
    _p(db, "1 compras, 2 salidas, 3 salidas, ok")
    assert ("TARJETA VISA", "CLUB INVENTADO", "Salidas") in _q(
        db, "SELECT tipo, comercio, motivo FROM reglas_comercio")


def test_deshacer_deja_el_pago_otra_vez_esperando(db, pdf):
    _hasta_el_desarmado(db)
    _p(db, "1 compras, 2 salidas, 3 salidas, ok")
    r = _p(db, "deshacer", cuando=AHORA + timedelta(minutes=5))
    assert r.resultado == "deshecho"
    assert _desarmados(db) == []
    assert _q(db, "SELECT estado FROM banco_filas WHERE tipo = 'PAGO TARJETA VISA'") == [
        ("esperando_resumen",)]
    assert _q(db, "SELECT estado, pagado FROM resumenes") == [("esperando_pago", None)]


def test_no_se_aplica_sin_categorias(db, pdf):
    _hasta_el_desarmado(db)
    r = _p(db, "ok")
    assert r.resultado == "pendiente" and "Me falta la categoría de: 1, 2, 3" in r.texto


# ---------------------------------------------------------------- el dólar

def test_el_dolar_de_la_caja_gana(db, pdf):
    _extracto_con_pago(db, extra=[("11/11/2026", "Compra venta de dolares\nF\n2\n"
                                   "Cotizacion: 1600.0000\nOPERACION 1", -160000)])
    _p(db, "1 compras, ok")
    r = _mandar_pdf(db, cotizador=_dolar(9999))
    assert "Dólar a $1.600: la compra de dólares del 11/11 en la caja" in r.texto


def test_sin_dolar_lo_pide(db, pdf):
    def caido(fecha):
        raise CotizacionNoDisponible("timeout")

    _extracto_con_pago(db)
    _p(db, "1 compras, ok")
    r = _mandar_pdf(db, cotizador=caido)
    assert "Me falta el dólar (no pude traer el dólar oficial (timeout))" in r.texto
    assert "contestá *dolar 1540*" in r.texto
    r = _p(db, "1 compras, 2 salidas, 3 salidas, ok", cotizador=caido)
    assert r.resultado == "pendiente" and "Me falta el dólar" in r.texto
    r = _p(db, "dólar 1.500", cotizador=caido)
    assert "USD 12 = $18.000" in r.texto
    assert _p(db, "ok", cotizador=caido).resultado == "lote"
    assert ("2026-11-11", "Venta divisa", 0.0, 18000.0) in _desarmados(db)


# ---------------------------------------------------------------- sin duplicar

def test_un_consumo_ya_cargado_no_se_carga_de_nuevo(db, pdf):
    """El Club del 22/10 lo había cargado a mano (y marcado tarjeta): no va dos veces."""
    club = _cargar(db, date(2026, 10, 22), "Salidas", pasivos=20000)
    _extracto_con_pago(db)
    _p(db, "1 compras, 2 tarjeta, ok")               # el Club sobra: es de la tarjeta
    r = _mandar_pdf(db)
    assert f"CLUB INVENTADO $20.000 = Salidas $20.000 (22/10)" in r.texto
    _p(db, "1 compras, 2 salidas, ok")
    assert ("2026-11-11", "Salidas", 20000.0, 0.0) not in _desarmados(db)
    assert _q(db, "SELECT rol FROM emparejamientos WHERE transaccion_id = ?", club) == [
        ("resumen",)]
    # Lo desarmado + lo que ya estaba = lo pagado.
    neto = sum(i - p for _, _, p, i in _desarmados(db))
    assert round(neto - 20000, 2) == -72900.0


def test_un_resumen_ya_desarmado(db, pdf):
    _hasta_el_desarmado(db)
    _p(db, "1 compras, 2 salidas, 3 salidas, ok")
    assert "ya lo desarmé" in _mandar_pdf(db).texto


def test_el_resumen_siguiente_confirma_el_pago(db, pdf):
    _hasta_el_desarmado(db)
    _p(db, "1 compras, 2 salidas, 3 salidas, ok")
    pdf["resumen"] = _resumen(
        cierre_anterior=date(2026, 10, 29), vencimiento_anterior=date(2026, 11, 11),
        cierre=date(2026, 11, 26), vencimiento=date(2026, 12, 5),
        pagos=[Linea(date(2026, 11, 11), "SU PAGO EN PESOS", -7000000, 0)])
    _mandar(db, _extracto([("30/10/2026", COMPRA.format("KIOSCO"), -500),
                           ("11/11/2026", PAGO, -72900), ("05/12/2026", PAGO, -72900)]),
            cuando=AHORA + timedelta(days=20))
    _p(db, "ok", cuando=AHORA + timedelta(days=20))
    r = _mandar_pdf(db, cuando=AHORA + timedelta(days=20))
    assert "Este resumen dice que pagaste $70.000 del anterior, y en la caja salieron $72.900" \
        in r.texto
