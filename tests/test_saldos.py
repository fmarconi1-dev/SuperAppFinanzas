"""FIMA, efectivo y el ajuste (Fase D, paso 4b). Base sintética."""

from __future__ import annotations

from datetime import date, datetime

from places.finanzas.core.comandos import ZONA, procesar
from tests.test_conciliacion import (  # noqa: F401 — el fixture `db`
    COMPRA, FIMA, _cargar, _extracto, _mandar, _q, db,
)

UID = 1


def _p(conn, texto, cuando=datetime(2026, 11, 18, 12, tzinfo=ZONA)):
    return procesar(conn, texto, user_id=UID, ahora=cuando)


def test_el_primer_saldo_es_el_punto_de_partida(db):
    r = _p(db, "18/10, fima 485.428,94 efectivo 154.400")
    assert r.resultado == "pendiente" and "punto de partida" in r.texto
    assert _p(db, "ok").resultado == "lote"
    assert _q(db, "SELECT parte, fecha, monto FROM saldos_declarados ORDER BY parte") == [
        ("efectivo", "2026-10-18", 15440000), ("fima", "2026-10-18", 48542894)]


def test_fima_y_efectivo_con_ajuste(db):
    _p(db, "18/10, fima 100.000 efectivo 50.000")
    _p(db, "ok")
    _cargar(db, date(2026, 10, 25), "Salidas", pasivos=8000)        # efectivo
    _mandar(db, _extracto([("20/10/2026", FIMA, -20000),
                           ("16/11/2026", "EXTRACCION CAJERO\n4517XXXX", -10000)]))
    _p(db, "ok")
    r = _p(db, "fima 121.500 efectivo 50.000")
    assert "esperaba $120.000" in r.texto and "+$1.500 de Rendimiento FIMA" in r.texto
    assert "esperaba $52.000" in r.texto and "faltan $2.000" in r.texto
    r = _p(db, "ok")
    assert r.resultado == "lote"
    filas = _q(db, "SELECT motivo, pasivos, ingresos FROM transacciones "
                   "WHERE comentario LIKE '%declarado contra%' ORDER BY motivo")
    assert filas == [("Ajuste Reconciliación", 2000.0, 0.0), ("Rendimiento FIMA", 0.0, 1500.0)]


def test_cancelar_no_guarda(db):
    _p(db, "fima 1.000")
    _p(db, "cancelar")
    assert _q(db, "SELECT COUNT(*) FROM saldos_declarados") == [(0,)]
