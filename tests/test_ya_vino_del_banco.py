"""El "¿es el mismo?" (Fase D, paso 4b, ADR-0009 §4): si Franco manda por
WhatsApp algo que ya entró por una conciliación, se pregunta antes de cargar."""

from __future__ import annotations

from datetime import datetime

from places.finanzas.core.comandos import ZONA, procesar
from tests.test_conciliacion import (  # noqa: F401 — el fixture `db`
    PROPIA, _extracto, _mandar, _q, db,
)

UID = 1
CUANDO = datetime(2026, 10, 30, 12, tzinfo=ZONA)


def _p(conn, texto):
    return procesar(conn, texto, user_id=UID, ahora=CUANDO)


def _con_auto_del_banco(db):
    """El extracto trae una transferencia de $50.000 el 27/10 y queda cargada como Auto."""
    _mandar(db, _extracto([("27/10/2026", PROPIA, -50000)]), cuando=CUANDO)
    assert _p(db, "1 auto, ok").resultado == "lote"


def _autos(db):
    return _q(db, "SELECT fecha, pasivos FROM transacciones WHERE motivo = 'Auto' ORDER BY id")


def test_si_es_el_mismo_no_se_carga(db):
    _con_auto_del_banco(db)
    r = _p(db, "25/10, 50.000, auto")
    assert r.resultado == "pendiente"
    assert "Ya tengo Auto $50.000 del 27/10 que vino del banco. ¿Es el mismo?" in r.texto
    r = _p(db, "sí")
    assert "no lo cargué" in r.texto
    assert _autos(db) == [("2026-10-27", 50000.0)]


def test_si_es_otro_se_carga(db):
    _con_auto_del_banco(db)
    _p(db, "25/10, 50.000, auto")
    r = _p(db, "no")
    assert r.resultado == "cargado"
    assert _autos(db) == [("2026-10-27", 50000.0), ("2026-10-25", 50000.0)]


def test_fuera_de_la_ventana_no_pregunta(db):
    _con_auto_del_banco(db)
    assert _p(db, "20/10, 50.000, auto").resultado == "cargado"     # 7 días antes


def test_un_monto_distinto_no_pregunta(db):
    _con_auto_del_banco(db)
    assert _p(db, "25/10, 51.000, auto").resultado == "cargado"


def test_lo_que_cargaste_vos_no_cuenta_como_del_banco(db):
    """Solo pregunta por lo que **vino del banco**, no por lo que ya cargaste a mano."""
    assert _p(db, "25/10, 50.000, auto").resultado == "cargado"
    assert _p(db, "25/10, 50.000, auto").resultado == "cargado"
