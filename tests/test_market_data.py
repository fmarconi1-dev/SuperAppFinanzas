"""Tests de `core/market_data` (Fase 3a, paso 3) — sin red.

El `fetch` se inyecta en todas las funciones (mismo patrón que
`tests/test_scoring_snapshot.py`), así los tests son deterministas y no
dependen de que las APIs estén arriba.

Cubre: parseo de la serie MEP, último hábil anterior, caché, fallback cuando
la fuente cae, override manual, precios ARG (incluida la normalización /100
de los bonos), yahoo, y el congelado idempotente del TC por operación.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from core import db as core_db
from core.db import connect, init_db
from core.market_data.mep import (
    TICKER_MEP,
    cargar_serie_desde_cache,
    guardar_serie_en_cache,
    mep_para_fecha,
    obtener_serie_mep,
    serie_mep_con_fallback,
    set_override_mep,
)
from core.market_data.precios import (
    leer_precio_cache,
    precio_yahoo,
    precios_arg,
    resolver_precio,
    set_override_precio,
)
from places.inversiones.cartera.ingest import congelar_tc_mep, importar_movimientos
from places.inversiones.cartera.parser import Instrumento, parse_filas


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(db_path)
    conn = connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) "
        "VALUES (1, 'franco', 'Franco')"
    )
    yield conn
    conn.close()


# Serie de ejemplo con el shape real de argentinadatos.
SERIE_JSON = json.dumps([
    {"casa": "bolsa", "compra": 1060.0, "venta": 1061.8, "fecha": "2024-12-05"},
    {"casa": "bolsa", "compra": 1430.0, "venta": 1432.3, "fecha": "2026-05-19"},
    {"casa": "bolsa", "compra": 1519.0, "venta": 1521.9, "fecha": "2026-07-23"},  # jueves
])


def _fetch_ok(url):
    return SERIE_JSON


def _fetch_roto(url):
    raise ConnectionError("API caída")


# ---------------------------------------------------------------------------
# Serie MEP
# ---------------------------------------------------------------------------

def test_obtener_serie_usa_venta():
    serie = obtener_serie_mep(_fetch_ok)
    assert serie["2024-12-05"] == 1061.8
    assert serie["2026-07-23"] == 1521.9
    assert len(serie) == 3


def test_mep_para_fecha_exacta():
    serie = obtener_serie_mep(_fetch_ok)
    assert mep_para_fecha(serie, date(2026, 5, 19)) == 1432.3
    assert mep_para_fecha(serie, "2026-05-19") == 1432.3


def test_mep_para_fecha_usa_ultimo_habil_anterior():
    serie = obtener_serie_mep(_fetch_ok)
    # sábado y domingo posteriores al jueves 23/7 → toma el jueves.
    assert mep_para_fecha(serie, date(2026, 7, 25)) == 1521.9
    assert mep_para_fecha(serie, date(2026, 7, 26)) == 1521.9


def test_mep_sin_dato_devuelve_none():
    serie = obtener_serie_mep(_fetch_ok)
    assert mep_para_fecha(serie, date(2020, 1, 1)) is None
    assert mep_para_fecha({}, date(2026, 7, 23)) is None


# ---------------------------------------------------------------------------
# Caché / fallback / override
# ---------------------------------------------------------------------------

def test_serie_se_cachea_y_se_relee(db):
    serie = obtener_serie_mep(_fetch_ok)
    n = guardar_serie_en_cache(db, serie)
    db.commit()
    assert n == 3
    assert cargar_serie_desde_cache(db) == serie


def test_fallback_a_cache_si_la_fuente_cae(db):
    guardar_serie_en_cache(db, obtener_serie_mep(_fetch_ok))
    db.commit()
    serie, origen = serie_mep_con_fallback(db, _fetch_roto)
    assert origen == "cache"
    assert serie["2026-07-23"] == 1521.9


def test_con_fuente_ok_marca_proveedor_y_refresca(db):
    serie, origen = serie_mep_con_fallback(db, _fetch_ok)
    assert origen == "proveedor"
    assert serie["2024-12-05"] == 1061.8
    assert cargar_serie_desde_cache(db)  # quedó cacheada


def test_override_manual_gana_sobre_proveedor(db):
    set_override_mep(db, "2026-07-23", 1600.0)
    db.commit()
    serie, _ = serie_mep_con_fallback(db, _fetch_ok)
    assert serie["2026-07-23"] == 1600.0  # el override pisa al proveedor
    row = db.execute(
        "SELECT es_override FROM cartera_precios_cache "
        "WHERE ticker = ? AND fecha = '2026-07-23'",
        (TICKER_MEP,),
    ).fetchone()
    assert row["es_override"] == 1


# ---------------------------------------------------------------------------
# Precios
# ---------------------------------------------------------------------------

PANEL_JSON = json.dumps([
    {"symbol": "GGAL", "c": 7890.0, "px_bid": 7890.0, "px_ask": 7920.0},
    {"symbol": "AE38", "c": 127360.0, "px_bid": 126900.0, "px_ask": 127360.0},
    {"symbol": "SINCIERRE", "c": 0, "px_bid": 100.0, "px_ask": 102.0},
])


def test_precios_arg_parsea_y_usa_mid_si_no_hay_cierre():
    p = precios_arg(lambda url: PANEL_JSON, paneles=("arg_stocks",))
    assert p["GGAL"] == 7890.0
    assert p["SINCIERRE"] == 101.0  # mid de las puntas


def test_precios_arg_tolera_panel_caido():
    def fetch(url):
        if "stocks" in url:
            raise ConnectionError("caído")
        return PANEL_JSON
    p = precios_arg(fetch, paneles=("arg_stocks", "arg_bonds"))
    assert "GGAL" in p  # el panel que sí respondió alimentó el dict


def test_resolver_precio_normaliza_bonos_por_100(db):
    prov = precios_arg(lambda url: PANEL_JSON, paneles=("arg_bonds",))
    precio, origen = resolver_precio(
        db, "AE38", fecha="2026-07-24", precios_proveedor=prov, divide_por_100=True
    )
    assert origen == "proveedor"
    assert precio == pytest.approx(1273.6)  # 127360 / 100


def test_resolver_precio_precedencia_override_cache_proveedor(db):
    prov = {"GGAL": 7890.0}
    # 1) proveedor (y cachea)
    precio, origen = resolver_precio(db, "GGAL", "2026-07-24", precios_proveedor=prov)
    assert (precio, origen) == (7890.0, "proveedor")
    # 2) sin proveedor → caché
    precio, origen = resolver_precio(db, "GGAL", "2026-07-24")
    assert (precio, origen) == (7890.0, "cache")
    # 3) override gana aunque el proveedor traiga otro precio
    set_override_precio(db, "GGAL", 8000.0, "2026-07-24")
    precio, origen = resolver_precio(db, "GGAL", "2026-07-24", precios_proveedor=prov)
    assert (precio, origen) == (8000.0, "override")


def test_resolver_precio_sin_dato(db):
    precio, origen = resolver_precio(db, "NOEXISTE", "2026-07-24")
    assert precio is None and origen == "sin_dato"


def test_cache_no_pisa_override(db):
    set_override_precio(db, "GGAL", 8000.0, "2026-07-24")
    resolver_precio(db, "GGAL", "2026-07-24", precios_proveedor={"GGAL": 1.0})
    assert leer_precio_cache(db, "GGAL", "2026-07-24") == (8000.0, True)


def test_precio_yahoo_parsea_y_tolera_error():
    payload = json.dumps({"chart": {"result": [{"meta": {"regularMarketPrice": 65877.0}}]}})
    assert precio_yahoo("BTC-USD", lambda url: payload) == 65877.0
    assert precio_yahoo("BTC-USD", _fetch_roto) is None
    assert precio_yahoo("XX", lambda url: json.dumps({"chart": {"result": []}})) is None


# ---------------------------------------------------------------------------
# Congelado del TC por operación
# ---------------------------------------------------------------------------

def _movs():
    insts = {"GGAL": Instrumento("GGAL", "GGALD", "Acciones", "ARS")}
    filas = [
        ["Compra", "2024-12-05", "2024-12-05", "GGAL | Grupo", -1000, 10, 100, "ARS"],
        ["Compra", "2026-05-19", "2026-05-20", "GGAL | Grupo", -2000, 5, 400, "ARS"],
        ["Compra", "2026-07-25", "2026-07-27", "GGAL | Grupo", -3000, 2, 1500, "ARS"],  # sábado
    ]
    return parse_filas(filas, insts)


def test_congelar_tc_mep_por_fecha(db):
    importar_movimientos(db, _movs(), user_id=1)
    serie = obtener_serie_mep(_fetch_ok)
    n, sin_dato = congelar_tc_mep(db, serie, user_id=1)
    assert n == 3 and sin_dato == []
    filas = {
        r["fecha_concertacion"]: r["tc_mep"]
        for r in db.execute(
            "SELECT fecha_concertacion, tc_mep FROM cartera_movimientos"
        )
    }
    assert filas["2024-12-05"] == 1061.8
    assert filas["2026-05-19"] == 1432.3
    assert filas["2026-07-25"] == 1521.9  # sábado → último hábil (jueves 23)


def test_congelar_es_idempotente_y_no_pisa(db):
    importar_movimientos(db, _movs(), user_id=1)
    serie = obtener_serie_mep(_fetch_ok)
    congelar_tc_mep(db, serie, user_id=1)
    # segunda corrida: ya no hay filas con tc_mep NULL.
    n2, _ = congelar_tc_mep(db, serie, user_id=1)
    assert n2 == 0
    # aunque cambie la serie, lo congelado no se toca.
    congelar_tc_mep(db, {"2024-12-05": 9999.0}, user_id=1)
    row = db.execute(
        "SELECT tc_mep FROM cartera_movimientos WHERE fecha_concertacion='2024-12-05'"
    ).fetchone()
    assert row["tc_mep"] == 1061.8


def test_congelar_reporta_fechas_sin_dato(db):
    importar_movimientos(db, _movs(), user_id=1)
    n, sin_dato = congelar_tc_mep(db, {"2026-05-19": 1432.3}, user_id=1)
    assert n == 1
    assert "2024-12-05" in sin_dato  # anterior al inicio de la serie
