"""El dólar oficial de una fecha (Fase D, paso 5), contra un ArgentinaDatos de mentira.

Y que la percepción (Flujo Capital) no aparezca en el gráfico de categorías.
"""

from __future__ import annotations

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pandas as pd
import pytest

from core.api import cotizaciones
from core.api.cotizaciones import CotizacionNoDisponible, oficial_vendedor
from places.finanzas.core.metrics import gasto_por_categoria


@pytest.fixture()
def fuente(monkeypatch):
    estado = {"dias": {}, "codigo": None, "pedidos": []}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):  # noqa: N802
            estado["pedidos"].append(self.path)
            fecha = "-".join(self.path.strip("/").split("/")[-3:])
            if estado["codigo"]:
                self.send_response(estado["codigo"])
                self.end_headers()
                return
            if fecha not in estado["dias"]:
                self.send_response(404)
                self.end_headers()
                return
            cuerpo = json.dumps({"casa": "oficial", "compra": 1, "venta": estado["dias"][fecha],
                                 "fecha": fecha}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(cotizaciones, "BASE", f"http://127.0.0.1:{srv.server_address[1]}/oficial")
    yield estado
    srv.shutdown()
    srv.server_close()


def test_la_cotizacion_del_dia(fuente):
    fuente["dias"]["2026-10-09"] = 1540
    assert oficial_vendedor(date(2026, 10, 9)) == (1540.0, date(2026, 10, 9))
    assert fuente["pedidos"] == ["/oficial/2026/10/09"]


def test_un_fin_de_semana_usa_el_dia_habil_anterior(fuente):
    fuente["dias"]["2026-10-09"] = 1540                    # viernes
    assert oficial_vendedor(date(2026, 10, 11)) == (1540.0, date(2026, 10, 9))


def test_sin_cotizacion_cerca(fuente):
    with pytest.raises(CotizacionNoDisponible, match="no hay cotización"):
        oficial_vendedor(date(2026, 10, 11))


def test_la_fuente_caida_no_se_disimula(fuente):
    fuente["codigo"] = 503
    with pytest.raises(CotizacionNoDisponible, match="503"):
        oficial_vendedor(date(2026, 10, 9))


def test_sin_red(monkeypatch):
    monkeypatch.setattr(cotizaciones, "BASE", "http://127.0.0.1:9/oficial")
    with pytest.raises(CotizacionNoDisponible, match="no pude hablar"):
        oficial_vendedor(date(2026, 10, 9))


def test_la_percepcion_no_va_al_grafico_de_categorias():
    df = pd.DataFrame({"fecha": pd.to_datetime(["2026-11-11"] * 2),
                       "pasivos": [10000.0, 5000.0], "ingresos": [0.0, 0.0],
                       "motivo": ["Percepción 30% (se devuelve)", "Compras"]})
    cats = {"Percepción 30% (se devuelve)": ("Flujo Capital", None),
            "Compras": ("Gasto Variable", None)}
    assert list(gasto_por_categoria(df, cats)["motivo"]) == ["Compras"]
