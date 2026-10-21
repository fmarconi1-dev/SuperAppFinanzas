"""Fuentes de los balances (ADR-0011) contra un Nasdaq y una Wikipedia de mentira locales.

Las respuestas imitan las reales del 20/10/2026 (`docs/PLAN-BALANCES.md`).
Nunca se sale a internet.
"""

from __future__ import annotations

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from core.api import balances_fuentes as bf
from core.api.balances_fuentes import (
    CalendarioNoDisponible,
    FilaCalendario,
    ListaNoDisponible,
    calendario,
    calendario_del_dia,
    lista_sp500,
    ticker_canonico,
)


def fila_nasdaq(symbol, time="time-after-hours", cap="$1,000,000,000", name=None):
    return {"lastYearRptDt": "10/29/2025", "lastYearEPS": "$7.25", "time": time,
            "symbol": symbol, "name": name or f"{symbol} Inc.", "marketCap": cap,
            "fiscalQuarterEnding": "Sep/2026", "epsForecast": "$6.54", "noOfEsts": "11"}


def html_wikipedia(tickers):
    filas = "".join(
        f'<tr>\n<td><a rel="nofollow" class="external text" '
        f'href="https://www.nyse.com/quote/XNYS:{t}">{t}</a>\n</td>\n'
        f'<td><a href="/wiki/X">Empresa {t}</a>\n</td>\n<td>Industrials\n</td>\n</tr>\n'
        for t in tickers)
    return ('<div><table class="wikitable sortable" id="constituents"><tbody>'
            '<tr><th>Symbol</th><th>Security</th><th>GICS Sector</th></tr>\n'
            f'{filas}</tbody></table>'
            '<table id="changes"><tr><td>NO_ES</td></tr></table></div>')


@pytest.fixture()
def fuentes(monkeypatch):
    estado = {"dias": {}, "codigo": None, "crudo": None, "wiki": None, "pedidos": [],
              "agentes": []}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _mandar(self, cuerpo: bytes):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):  # noqa: N802
            partes = urlsplit(self.path)
            estado["pedidos"].append(self.path)
            estado["agentes"].append(self.headers.get("User-Agent"))
            if estado["codigo"]:
                self.send_response(estado["codigo"])
                self.end_headers()
                return
            if estado["crudo"] is not None:
                self._mandar(estado["crudo"])
                return
            if partes.path == "/nasdaq/calendar/earnings":
                dia = parse_qs(partes.query)["date"][0]
                filas = estado["dias"].get(dia)
                cuerpo = {"data": {"asOf": dia, "headers": {}, "rows": filas},
                          "message": None, "status": {"rCode": 200}}
                self._mandar(json.dumps(cuerpo).encode())
            elif partes.path == "/w/api.php":
                cuerpo = {"parse": {"title": "List of S&P 500 companies", "pageid": 2676045,
                                    "text": estado["wiki"]}}
                self._mandar(json.dumps(cuerpo).encode())
            else:
                self.send_response(404)
                self.end_headers()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setattr(bf, "NASDAQ_BASE", f"{base}/nasdaq")
    monkeypatch.setattr(bf, "WIKIPEDIA_API", f"{base}/w/api.php")
    yield estado
    srv.shutdown()
    srv.server_close()


# ------------------------------------------------------------------ Nasdaq

def test_el_calendario_de_un_dia(fuentes):
    fuentes["dias"]["2026-10-21"] = [
        fila_nasdaq("META", "time-after-hours", "$1,797,112,860,000", "Meta Platforms, Inc."),
        fila_nasdaq("NEE", "time-pre-market", "$163,060,924,000"),
        fila_nasdaq("SPCX", "time-not-supplied", "$2,008,234,720,000",
                    "Space Exploration Technologies Corp."),
    ]
    filas = calendario_del_dia(date(2026, 10, 21))
    assert filas == [
        FilaCalendario("META", "Meta Platforms, Inc.", date(2026, 10, 21), "post", 1797112860000.0),
        FilaCalendario("NEE", "NEE Inc.", date(2026, 10, 21), "pre", 163060924000.0),
        FilaCalendario("SPCX", "Space Exploration Technologies Corp.", date(2026, 10, 21), None,
                       2008234720000.0),
    ]
    assert fuentes["pedidos"] == ["/nasdaq/calendar/earnings?date=2026-10-21"]
    assert "Mozilla" in fuentes["agentes"][0]        # sin esto Nasdaq no contesta


def test_un_dia_sin_rueda_viene_con_rows_null(fuentes):
    assert calendario_del_dia(date(2026, 10, 24)) == []


def test_capitalizacion_que_no_es_numero(fuentes):
    fuentes["dias"]["2026-10-21"] = [fila_nasdaq("XX", cap="N/A"), fila_nasdaq("YY", cap="")]
    assert [f.capitalizacion for f in calendario_del_dia(date(2026, 10, 21))] == [None, None]


def test_un_renglon_sin_ticker_se_saltea(fuentes):
    fuentes["dias"]["2026-10-21"] = [fila_nasdaq(""), fila_nasdaq("KO")]
    assert [f.ticker for f in calendario_del_dia(date(2026, 10, 21))] == ["KO"]


def test_la_semana_saltea_sabado_y_domingo(fuentes):
    fuentes["dias"]["2026-10-23"] = [fila_nasdaq("A")]
    fuentes["dias"]["2026-10-26"] = [fila_nasdaq("B")]
    filas = calendario(date(2026, 10, 23), date(2026, 10, 26))
    assert [(f.ticker, f.fecha) for f in filas] == [("A", date(2026, 10, 23)),
                                                    ("B", date(2026, 10, 26))]
    assert len(fuentes["pedidos"]) == 2                # ni el sábado ni el domingo


def test_nasdaq_caido_no_se_disimula(fuentes):
    fuentes["codigo"] = 503
    with pytest.raises(CalendarioNoDisponible, match="503"):
        calendario_del_dia(date(2026, 10, 21))


def test_nasdaq_contesta_cualquier_cosa(fuentes):
    fuentes["crudo"] = b"<html>Access Denied</html>"
    with pytest.raises(CalendarioNoDisponible, match="no es JSON"):
        calendario_del_dia(date(2026, 10, 21))
    fuentes["crudo"] = json.dumps({"data": None, "status": {"rCode": 400}}).encode()
    with pytest.raises(CalendarioNoDisponible, match="no trajo"):
        calendario_del_dia(date(2026, 10, 21))


def test_sin_red(monkeypatch):
    monkeypatch.setattr(bf, "NASDAQ_BASE", "http://127.0.0.1:9/nasdaq")
    with pytest.raises(CalendarioNoDisponible, match="no pude hablar con Nasdaq"):
        calendario_del_dia(date(2026, 10, 21))


# ------------------------------------------------------------------ Wikipedia

def test_la_lista_del_sp500(fuentes):
    tickers = [f"T{i}" for i in range(500)] + ["BRK.B", "BF.B"]
    fuentes["wiki"] = html_wikipedia(tickers)
    lista = lista_sp500()
    assert len(lista) == 502
    assert "BRK.B" in lista and "NO_ES" not in lista     # la otra tabla no se lee
    assert "SecretarioFranco" in fuentes["agentes"][0]


def test_una_tabla_que_trae_poco_no_se_cree(fuentes):
    fuentes["wiki"] = html_wikipedia(["MMM", "AOS"])
    with pytest.raises(ListaNoDisponible, match="2 tickers"):
        lista_sp500()


def test_una_pagina_sin_la_tabla(fuentes):
    fuentes["wiki"] = "<p>Esta página cambió</p>"
    with pytest.raises(ListaNoDisponible, match="constituents"):
        lista_sp500()


def test_wikipedia_caida(fuentes):
    fuentes["codigo"] = 500
    with pytest.raises(ListaNoDisponible, match="500"):
        lista_sp500()


def test_ticker_canonico():
    assert ticker_canonico("brk-b") == ticker_canonico("BRK/B") == ticker_canonico("BRK.B") == "BRK.B"
    assert ticker_canonico(" spcx ") == "SPCX"
