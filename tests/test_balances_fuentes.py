"""Fuentes de los balances (ADR-0011) contra un Nasdaq y una Wikipedia de mentira locales.

Las respuestas imitan las reales del 20/10/2026 (`docs/PLAN-BALANCES.md`).
Nunca se sale a internet.
"""

from __future__ import annotations

import json
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest

from core.api import balances_fuentes as bf
from core.api.balances_fuentes import (
    CalendarioNoDisponible,
    FilaCalendario,
    FechaAnunciada,
    ListaNoDisponible,
    PrecioNoDisponible,
    calendario,
    calendario_del_dia,
    cierres,
    fecha_anunciada,
    lista_sp500,
    ticker_canonico,
    ultimo_del_posmercado,
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
              "agentes": [], "fichas": {}, "yahoo": {}}

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
            elif partes.path.startswith("/nasdaq/analyst/"):
                ticker = partes.path.split("/")[3]
                texto = estado["fichas"].get(ticker)
                cuerpo = {"data": {"reportText": texto, "heading": f"{ticker} Earnings Date"}
                          if texto is not None else None,
                          "status": {"rCode": 200 if texto is not None else 400}}
                self._mandar(json.dumps(cuerpo).encode())
            elif partes.path.startswith("/yahoo/"):
                simbolo = partes.path.split("/")[2]
                consulta = parse_qs(partes.query)
                clave = "diario" if consulta.get("interval") == ["1d"] else "intradiario"
                cuerpo = estado["yahoo"].get((simbolo, clave))
                if cuerpo is None:
                    self.send_response(404)
                    self.end_headers()
                    return
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
    monkeypatch.setattr(bf, "YAHOO_BASE", f"{base}/yahoo")
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


# ------------------------------------------------------------------ la ficha de cada empresa

#: Los textos de Nasdaq del 21/10/2026, tal cual (con sus dos espacios).
FICHA_MCD = ("McDonald's Corporation Common Stock is expected* to report earnings on  11/04/2026 "
             "before market open.  The report will be for the fiscal Quarter ending Sep 2026.")
FICHA_TGS = ("Transportadora de Gas del Sur SA TGS Common Stock is estimated to report earnings on "
             " 11/02/2026. The upcoming earnings date is derived from an algorithm based on a "
             "company's historical reporting dates.")
FICHA_MSFT = ("Microsoft Corporation Common Stock is expected* to report earnings on  10/28/2026 "
              "after market close.  The report will be for the fiscal Quarter ending Sep 2026.")


def test_la_ficha_dice_si_la_fecha_es_estimada(fuentes):
    fuentes["fichas"].update({"MCD": FICHA_MCD, "TGS": FICHA_TGS, "MSFT": FICHA_MSFT})
    assert fecha_anunciada("MCD") == FechaAnunciada(date(2026, 11, 4), "pre", estimada=False)
    assert fecha_anunciada("tgs") == FechaAnunciada(date(2026, 11, 2), None, estimada=True)
    assert fecha_anunciada("MSFT") == FechaAnunciada(date(2026, 10, 28), "post", estimada=False)
    assert fuentes["pedidos"][0] == "/nasdaq/analyst/MCD/earnings-date"


def test_una_ficha_sin_anuncio_es_none(fuentes):
    assert fecha_anunciada("ZZZZQ") is None                      # Nasdaq: data null
    fuentes["fichas"]["BRK.B"] = "Berkshire Hathaway Inc. has no upcoming earnings date."
    assert fecha_anunciada("BRK.B") is None


def test_la_ficha_caida_no_se_disimula(fuentes):
    fuentes["codigo"] = 403
    with pytest.raises(CalendarioNoDisponible, match="403"):
        fecha_anunciada("MCD")


# ------------------------------------------------------------------ Yahoo

NY = ZoneInfo("America/New_York")


def _ts(dia, hora, minuto=0):
    return int(datetime(2026, 10, dia, hora, minuto, tzinfo=NY).timestamp())


def yahoo_diario(cierres_por_dia):
    return {"chart": {"result": [{
        "meta": {"symbol": "X"},
        "timestamp": [_ts(d, 9, 30) for d in cierres_por_dia],
        "indicators": {"quote": [{"close": list(cierres_por_dia.values())}]}}], "error": None}}


def yahoo_intradiario(barras, dias=(19, 20, 21)):
    """`barras`: [(día, hora, minuto, precio)]. Ventanas de verdad de cada día."""
    periodos = {k: [[{"start": _ts(d, a), "end": _ts(d, b), "timezone": "EDT"}] for d in dias]
                for k, (a, b) in {"pre": (4, 9), "regular": (9, 16), "post": (16, 20)}.items()}
    return {"chart": {"result": [{
        "meta": {"symbol": "X", "tradingPeriods": periodos},
        "timestamp": [_ts(d, h, m) for d, h, m, _ in barras],
        "indicators": {"quote": [{"close": [p for *_, p in barras]}]}}], "error": None}}


def test_los_cierres_por_dia_de_nueva_york(fuentes):
    fuentes["yahoo"][("NFLX", "diario")] = yahoo_diario({19: 69.85, 20: 68.69})
    assert cierres("NFLX") == {date(2026, 10, 19): 69.85, date(2026, 10, 20): 68.69}


def test_el_posmercado_es_el_de_ese_dia(fuentes):
    """A la mañana siguiente ya corre la pre-apertura: esa barra no cuenta."""
    fuentes["yahoo"][("NFLX", "intradiario")] = yahoo_intradiario([
        (20, 15, 55, 68.67), (20, 16, 5, 66.0), (20, 19, 55, 64.718), (20, 20, 0, None),
        (21, 4, 0, 63.0), (21, 9, 25, 64.3)])
    assert ultimo_del_posmercado("NFLX", date(2026, 10, 20)) == 64.718


def test_un_dia_sin_posmercado(fuentes):
    fuentes["yahoo"][("NFLX", "intradiario")] = yahoo_intradiario([(20, 15, 55, 68.67)])
    with pytest.raises(PrecioNoDisponible, match="no operó en el posmercado del 20/10"):
        ultimo_del_posmercado("NFLX", date(2026, 10, 20))
    with pytest.raises(PrecioNoDisponible, match="no tiene el posmercado de NFLX del 10/10"):
        ultimo_del_posmercado("NFLX", date(2026, 10, 10))


def test_yahoo_usa_guion_para_las_clases(fuentes):
    fuentes["yahoo"][("BRK-B", "diario")] = yahoo_diario({20: 480.0})
    assert cierres("BRK.B") == {date(2026, 10, 20): 480.0}
    assert fuentes["pedidos"][-1].startswith("/yahoo/BRK-B?range=1mo&interval=1d")


def test_yahoo_sin_el_ticker_o_caido(fuentes):
    with pytest.raises(PrecioNoDisponible, match="404"):
        cierres("ZZZZQ")
    fuentes["crudo"] = json.dumps({"chart": {"result": None, "error": {"code": "Not Found"}}}).encode()
    with pytest.raises(PrecioNoDisponible, match="no tiene ZZZZQ"):
        cierres("ZZZZQ")
