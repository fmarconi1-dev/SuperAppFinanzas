"""Cronogramas de renta fija: sin red y sin credenciales.

Los ejemplos de respuesta salen de la **documentación real** de Docta Capital
(`docs.docta.com.ar`), no de una invención: `payment_date`, `capital`,
`interest_amount`, `residual_value`, `cash_flow` y el `metadata` con
`subasset_class` y `nominal_units`.

Lo que más se cuida acá es que **el módulo nunca tire abajo la cartera**: si la
API falla, si no hay credenciales, si el JSON viene raro, la respuesta correcta
es `None` y la pantalla se muestra igual con lo que haya en caché.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from core.market_data import cronogramas as cr


@pytest.fixture(autouse=True)
def _sin_estado(monkeypatch):
    """Cada test arranca sin token cacheado y con credenciales de mentira."""
    cr.reset_token()
    monkeypatch.setenv("DOCTA_CLIENT_ID", "id-de-prueba")
    monkeypatch.setenv("DOCTA_CLIENT_SECRET", "secreto-de-prueba")
    yield
    cr.reset_token()


TOKEN_OK = json.dumps({"access_token": "tok-123", "expires_in": 3600})

#: Respuesta real de la doc, recortada. AL30: cupón sin capital y después una
#: cuota que amortiza 8 y deja 88 de residual.
CASHFLOW_AL30 = json.dumps({
    "ticker": "AL30",
    "data": [
        {"issue_date": "2020-09-04", "payment_date": "2027-07-09",
         "capital": 0.0, "interest_rate": 0.13,
         "interest_amount": 0.1101388888888889, "residual_value": 100.0,
         "cash_flow": 0.1101388888888889,
         "adj_interest_amount": 0.1101388888888889, "adj_capital": 0.0},
        {"issue_date": "2020-09-04", "payment_date": "2028-01-09",
         "capital": 8.0, "interest_rate": 0.75, "interest_amount": 0.375,
         "residual_value": 88.0, "cash_flow": 8.36,
         "adj_interest_amount": 0.36, "adj_capital": 8.0},
    ],
    "metadata": {"subasset_class": "HARD_DOLLAR", "nominal_units": 100.0,
                 "total_records": 2},
})

BUSQUEDA_AE38 = json.dumps({"data": [
    {"ticker": "AE38D", "name": "Bonar 2038 D"},
    {"ticker": "AE38", "name": "Bonar 2038"},
]})


def _fetch(respuestas: dict):
    """`fetch` falso: mapea un fragmento de URL a su respuesta."""
    def _f(url, datos=None, cabeceras=None):
        if "auth/token" in url:
            return TOKEN_OK
        for fragmento, resp in respuestas.items():
            if fragmento in url:
                return resp
        raise AssertionError(f"URL no esperada: {url}")
    return _f


# ---------------------------------------------------------------------------
# Sin credenciales, el módulo simplemente no existe
# ---------------------------------------------------------------------------

def test_sin_credenciales_no_hay_token(monkeypatch):
    """Que falten no es un error: la app tiene que andar igual sin la fuente."""
    monkeypatch.delenv("DOCTA_CLIENT_ID", raising=False)
    monkeypatch.delenv("DOCTA_CLIENT_SECRET", raising=False)
    cr.reset_token()
    assert cr.hay_credenciales() is False
    assert cr.obtener_token() is None


def test_sin_credenciales_no_se_consulta_nada(monkeypatch):
    monkeypatch.delenv("DOCTA_CLIENT_SECRET", raising=False)
    cr.reset_token()

    def no_deberia_llamarse(*a, **k):
        raise AssertionError("consultó la red sin credenciales")

    assert cr.buscar_simbolo("AE38", fetch=no_deberia_llamarse) is None
    assert cr.traer_cronograma("AE38", fetch=no_deberia_llamarse) is None


# ---------------------------------------------------------------------------
# El token se cachea: pedirlo por request gastaría la cuota al doble
# ---------------------------------------------------------------------------

def test_el_token_se_pide_una_sola_vez():
    llamadas = []

    def contar(url, datos=None, cabeceras=None):
        llamadas.append(url)
        return TOKEN_OK if "auth/token" in url else CASHFLOW_AL30

    cr.traer_cronograma("AL30", fetch=contar)
    cr.traer_cronograma("AL30", fetch=contar)
    assert sum(1 for u in llamadas if "auth/token" in u) == 1


def test_un_token_vencido_se_renueva(monkeypatch):
    def vencido(url, datos=None, cabeceras=None):
        if "auth/token" in url:
            return json.dumps({"access_token": "tok", "expires_in": 0})
        return CASHFLOW_AL30

    llamadas = []

    def contar(url, datos=None, cabeceras=None):
        llamadas.append(url)
        return vencido(url, datos, cabeceras)

    cr.traer_cronograma("AL30", fetch=contar)
    cr.traer_cronograma("AL30", fetch=contar)
    assert sum(1 for u in llamadas if "auth/token" in u) == 2


# ---------------------------------------------------------------------------
# Búsqueda: coincidencia EXACTA
# ---------------------------------------------------------------------------

def test_encuentra_el_simbolo_exacto():
    assert cr.buscar_simbolo(
        "AE38", fetch=_fetch({"instruments/search": BUSQUEDA_AE38})) == "AE38"


def test_no_se_queda_con_un_parecido():
    """⚠️ El error más caro posible en este módulo: darle a un bono el
    cronograma de otro. Buscando `AE38` la API devuelve también `AE38D`."""
    solo_parecidos = json.dumps({"data": [{"ticker": "AE38D"}]})
    assert cr.buscar_simbolo(
        "AE38", fetch=_fetch({"instruments/search": solo_parecidos})) is None


def test_el_pagare_ni_se_consulta():
    """Es del MAV y el catálogo son soberanos, sub-soberanos y ONs. Preguntar
    sería gastar cuota a ciegas."""
    def no_deberia_llamarse(*a, **k):
        raise AssertionError("consultó por un pagaré")

    assert cr.buscar_simbolo("#UMV060770008", fetch=no_deberia_llamarse) is None
    assert cr.traer_cronograma("#UMV060770008",
                               fetch=no_deberia_llamarse) is None


# ---------------------------------------------------------------------------
# El cronograma
# ---------------------------------------------------------------------------

def test_lee_los_flujos_de_la_respuesta_real():
    cron = cr.traer_cronograma("AL30", fetch=_fetch({"cashflow": CASHFLOW_AL30}))
    assert cron is not None
    assert cron.ticker == "AL30"
    assert cron.clase == "HARD_DOLLAR"
    assert cron.nominales == 100.0
    assert len(cron.flujos) == 2


def test_distingue_el_cupon_de_la_amortizacion():
    """Un cupón no devuelve capital; una amortización sí. La diferencia es la
    que hace que una letra no dé 100% de rendimiento (trampa #3)."""
    cron = cr.traer_cronograma("AL30", fetch=_fetch({"cashflow": CASHFLOW_AL30}))
    cupon, cuota = cron.flujos
    assert not cupon.es_amortizacion
    assert cuota.es_amortizacion
    assert cuota.capital == 8.0
    assert cuota.residual == 88.0


def test_usa_los_importes_ajustados_cuando_estan():
    """Para un bono CER, el importe que importa es el **ajustado**: el nominal
    sin ajustar subestima el pago."""
    cron = cr.traer_cronograma("AL30", fetch=_fetch({"cashflow": CASHFLOW_AL30}))
    assert cron.flujos[1].interes == pytest.approx(0.36)   # adj, no 0.375


def test_los_flujos_quedan_ordenados_por_fecha():
    desordenado = json.dumps({"data": [
        {"payment_date": "2029-01-09", "capital": 8.0, "cash_flow": 8.0},
        {"payment_date": "2027-07-09", "capital": 0.0, "cash_flow": 0.1},
    ], "metadata": {}})
    cron = cr.traer_cronograma("X", fetch=_fetch({"cashflow": desordenado}))
    assert [f.fecha for f in cron.flujos] == [date(2027, 7, 9), date(2029, 1, 9)]


def test_el_proximo_pago_es_el_primero_que_viene():
    cron = cr.traer_cronograma("AL30", fetch=_fetch({"cashflow": CASHFLOW_AL30}))
    assert cron.proximo_pago(date(2026, 8, 5)).fecha == date(2027, 7, 9)
    assert cron.proximo_pago(date(2027, 8, 1)).fecha == date(2028, 1, 9)


def test_lo_ya_pagado_no_cuenta_como_futuro():
    cron = cr.traer_cronograma("AL30", fetch=_fetch({"cashflow": CASHFLOW_AL30}))
    assert cron.proximos(date(2029, 1, 1)) == []


# ---------------------------------------------------------------------------
# Nunca lanza: una fuente caída no puede tirar abajo la cartera
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("respuesta", [
    "no soy json", "{}", '{"data": []}', '{"data": null}',
    '{"data": [{"capital": 1}]}',            # fila sin fecha
    '[1, 2, 3]',                             # forma inesperada
])
def test_una_respuesta_rota_devuelve_none(respuesta):
    assert cr.traer_cronograma("AL30",
                               fetch=_fetch({"cashflow": respuesta})) is None


def test_si_la_red_falla_devuelve_none():
    def explota(*a, **k):
        raise OSError("sin red")

    cr.reset_token()
    assert cr.obtener_token(fetch=explota) is None
    assert cr.traer_cronograma("AL30", fetch=explota) is None
    assert cr.buscar_simbolo("AL30", fetch=explota) is None


def test_una_autenticacion_rechazada_no_lanza():
    def sin_token(url, datos=None, cabeceras=None):
        return json.dumps({"detail": "Invalid client credentials"})

    cr.reset_token()
    assert cr.obtener_token(fetch=sin_token) is None
    assert cr.traer_cronograma("AL30", fetch=sin_token) is None


def test_las_credenciales_no_viajan_en_la_url():
    """Un secreto en la URL termina en los logs del proveedor y en el historial
    del navegador. Va en el cuerpo del POST."""
    vistas = []

    def espiar(url, datos=None, cabeceras=None):
        vistas.append(url)
        return TOKEN_OK if "auth/token" in url else CASHFLOW_AL30

    cr.traer_cronograma("AL30", fetch=espiar)
    assert not any("secreto-de-prueba" in u or "id-de-prueba" in u
                   for u in vistas)
