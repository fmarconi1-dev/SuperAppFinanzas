"""Tests de la resolución automática de sector e industria (Fase 3b, punto 4+).

Corren **sin red**: el `fetch` es inyectable. Lo que protegen: que no se
confunda un ticker con otro parecido, que los ETF queden con una etiqueta
legible en vez de "Sin dato", que el override manual gane siempre, y que un
ticker que no resuelve no dispare una búsqueda en cada carga.
"""

import json

import pytest

from core import db as core_db
from core.db import connect, init_db
from core.market_data.sectores import (
    FichaTicker, buscar_ficha, etiqueta_etf, guardar_ficha_en_cache,
    leer_sectores_cache, refrescar_sectores, resolver_ficha, sectores_para,
    set_override_sector,
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(ruta)
    conn = connect(ruta)
    yield conn
    conn.close()


def _respuesta(*quotes):
    return json.dumps({"quotes": list(quotes)})


NVDA = {"symbol": "NVDA", "quoteType": "EQUITY", "sector": "Technology",
        "industry": "Semiconductors", "longname": "NVIDIA Corporation"}
GLD = {"symbol": "GLD", "quoteType": "ETF", "sector": None, "industry": None,
       "shortname": "SPDR Gold Shares"}
TGNO4 = {"symbol": "TGNO4.BA", "quoteType": "EQUITY", "sector": "Energy",
         "industry": "Oil & Gas Midstream",
         "longname": "Transportadora de Gas del Norte S.A."}


def _fetch(mapa):
    """Fetch falso: devuelve la respuesta según lo que se busque."""
    def f(url):
        for clave, resp in mapa.items():
            if f"q={clave}" in url or f"q={clave.replace('.', '%2E')}" in url:
                return resp
        return _respuesta()
    return f


# ---------------------------------------------------------------------------
# Búsqueda
# ---------------------------------------------------------------------------

def test_trae_sector_e_industria_de_una_accion():
    f = buscar_ficha("NVDA", _fetch({"NVDA": _respuesta(NVDA)}))
    assert f.sector == "Technology"
    assert f.industria == "Semiconductors"
    assert f.tipo == "EQUITY" and not f.es_etf
    assert f.fuente == "yahoo"


def test_solo_acepta_la_coincidencia_exacta_de_simbolo():
    """Buscando URA, Yahoo devuelve también UROY (una minera). Quedarse con el
    primer resultado le pondría a un ETF de uranio el sector de una empresa."""
    uroy = {"symbol": "UROY", "quoteType": "EQUITY", "sector": "Energy",
            "industry": "Uranium", "longname": "Uranium Royalty Corp."}
    ura = {"symbol": "URA", "quoteType": "ETF", "sector": None,
           "shortname": "Global X Uranium ETF"}
    f = buscar_ficha("URA", _fetch({"URA": _respuesta(uroy, ura)}))
    assert f.ticker == "URA" and f.es_etf and f.sector is None


def test_una_respuesta_rota_o_caida_no_lanza():
    def explota(url):
        raise OSError("sin red")
    assert buscar_ficha("NVDA", explota) is None
    assert buscar_ficha("NVDA", lambda u: "no es json") is None
    assert resolver_ficha("NVDA", explota) is None


# ---------------------------------------------------------------------------
# ETFs: no tienen sector, y está bien
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre,esperado", [
    ("SPDR Gold Shares", "ETF · Oro"),
    ("Global X Uranium ETF", "ETF · Uranio"),
    ("Global X Copper Miners ETF", "ETF · Cobre"),
    ("State Street SPDR S&P 500 ETF Trust", "ETF · S&P 500"),
    ("iShares Core MSCI Europe ETF", "ETF · Europa"),
])
def test_la_etiqueta_del_etf_sale_del_nombre_del_fondo(nombre, esperado):
    assert etiqueta_etf(nombre) == esperado


def test_un_etf_no_reconocido_cae_al_nombre_del_fondo_sin_inventar():
    assert etiqueta_etf("Fondo Rarísimo XYZ") == "ETF · Fondo Rarísimo XYZ"
    assert etiqueta_etf(None) == "ETF"


def test_resolver_le_pone_etiqueta_al_etf_en_vez_de_dejarlo_sin_dato():
    f = resolver_ficha("GLD", _fetch({"GLD": _respuesta(GLD)}))
    assert f.sector == "ETF · Oro"
    assert f.es_etf


# ---------------------------------------------------------------------------
# Acciones argentinas: el sufijo .BA
# ---------------------------------------------------------------------------

def test_una_accion_argentina_resuelve_con_el_sufijo_ba():
    """TGNO4 no existe en Yahoo; TGNO4.BA sí."""
    f = resolver_ficha("TGNO4", _fetch({"TGNO4.BA": _respuesta(TGNO4)}))
    assert f.ticker == "TGNO4"          # se conserva el ticker de la cartera
    assert f.sector == "Energy"
    assert f.industria == "Oil & Gas Midstream"


def test_los_pagares_no_se_buscan():
    """Un pagaré no es una empresa: no tiene sentido preguntarle a Yahoo."""
    def no_deberia_llamarse(url):
        raise AssertionError("no se debe consultar la red para un pagaré")
    assert resolver_ficha("#UMV060770008", no_deberia_llamarse) is None


# ---------------------------------------------------------------------------
# Caché y override
# ---------------------------------------------------------------------------

def test_resuelve_cachea_y_no_vuelve_a_pegarle_a_la_red(db):
    llamadas = []

    def contar(url):
        llamadas.append(url)
        return _respuesta(NVDA)

    n, faltan = refrescar_sectores(db, ["NVDA"], fetch=contar)
    db.commit()
    assert (n, faltan) == (1, [])
    assert len(llamadas) == 1

    n, faltan = refrescar_sectores(db, ["NVDA"], fetch=contar)
    assert (n, faltan) == (0, [])
    assert len(llamadas) == 1, "volvió a consultar algo que ya estaba cacheado"
    assert sectores_para(db) == {"NVDA": "Technology"}


def test_lo_que_no_resuelve_tambien_se_cachea(db):
    """Sin caché negativa, un ticker desconocido dispararía una búsqueda en
    cada carga de la pantalla, para siempre."""
    llamadas = []

    def contar(url):
        llamadas.append(url)
        return _respuesta()

    _, faltan = refrescar_sectores(db, ["RARO"], fetch=contar)
    db.commit()
    assert faltan == ["RARO"]
    previas = len(llamadas)

    _, faltan = refrescar_sectores(db, ["RARO"], fetch=contar)
    assert faltan == ["RARO"]
    assert len(llamadas) == previas, "reintentó un ticker ya buscado"
    assert sectores_para(db) == {}          # sin sector: no ensucia el cuadro


def test_forzar_reintenta_lo_que_no_habia_resuelto(db):
    refrescar_sectores(db, ["NVDA"], fetch=lambda u: _respuesta())
    db.commit()
    assert sectores_para(db) == {}
    n, _ = refrescar_sectores(db, ["NVDA"], fetch=lambda u: _respuesta(NVDA),
                              forzar=True)
    db.commit()
    assert n == 1 and sectores_para(db) == {"NVDA": "Technology"}


def test_el_override_gana_y_no_lo_pisa_ni_el_proveedor_ni_forzar(db):
    """Decisión con Franco: manda Yahoo por defecto, pero si él fija un
    sector a mano, ese gana siempre."""
    refrescar_sectores(db, ["TGNO4"], fetch=_fetch({"TGNO4.BA": _respuesta(TGNO4)}))
    db.commit()
    assert sectores_para(db)["TGNO4"] == "Energy"

    set_override_sector(db, "TGNO4", "Utilities", "Gas natural")
    db.commit()
    assert sectores_para(db)["TGNO4"] == "Utilities"

    guardar_ficha_en_cache(db, FichaTicker("TGNO4", sector="Energy",
                                           fuente="yahoo"))
    db.commit()
    assert sectores_para(db)["TGNO4"] == "Utilities", "el proveedor pisó el override"

    refrescar_sectores(db, ["TGNO4"], fetch=_fetch({"TGNO4.BA": _respuesta(TGNO4)}),
                       forzar=True)
    db.commit()
    assert sectores_para(db)["TGNO4"] == "Utilities"
    assert leer_sectores_cache(db)["TGNO4"].fuente == "override"


def test_la_cache_evita_la_segunda_llamada(db):
    """Reemplaza a `test_el_scoring_se_usa_antes_que_la_red`, que verificaba
    que el snapshot del scoring ahorrara la consulta. El scoring se retiró el
    5/8/2026 y ahora **la caché es lo único que evita pegarle a la red**, así
    que el invariante que hay que sostener es éste."""
    refrescar_sectores(db, ["NVDA"], fetch=_fetch({"NVDA": _respuesta(NVDA)}))
    db.commit()

    def no_deberia_llamarse(url):
        raise AssertionError("consultó la red teniendo el dato en caché")

    n, faltan = refrescar_sectores(db, ["NVDA"], fetch=no_deberia_llamarse)
    assert (n, faltan) == (0, [])
    assert leer_sectores_cache(db)["NVDA"].fuente == "yahoo"


def test_las_industrias_se_leen_aparte(db):
    refrescar_sectores(db, ["NVDA"], fetch=_fetch({"NVDA": _respuesta(NVDA)}))
    db.commit()
    assert sectores_para(db, "industria") == {"NVDA": "Semiconductors"}
