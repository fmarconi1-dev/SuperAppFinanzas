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


# ---------------------------------------------------------------------------
# Las URLs, contra la especificación (no contra los ejemplos de la doc)
# ---------------------------------------------------------------------------
#
# ⚠️ El 5/8/2026 la primera prueba real dio **HTTP 404** en el token. La causa
# no era la credencial: el ejemplo `curl` de la documentación escribe
# `/api/v1/auth/token/` **con barra final**, y la especificación OpenAPI —que
# es la autoridad— define `/api/v1/auth/token` **sin** barra.
#
# Un 404 en autenticación es especialmente engañoso porque parece un problema
# de credenciales. Estos tests fijan los paths para que nadie los "arregle"
# copiando otra vez del ejemplo.

def test_el_token_va_sin_barra_final():
    assert cr.URL_TOKEN.endswith("/api/v1/auth/token")
    assert not cr.URL_TOKEN.endswith("/")


def test_los_paths_son_los_de_la_especificacion():
    assert cr.BASE == "https://api.doctacapital.com.ar"
    assert "/api/v1/bonds/instruments/search?query=" in cr.URL_BUSQUEDA
    assert "/api/v1/bonds/analytics/" in cr.URL_CASHFLOW
    assert "/cashflow?nominal_units=" in cr.URL_CASHFLOW


def test_la_busqueda_lee_la_forma_documentada():
    """La respuesta real trae `data[].ticker`, con `asset_class` y
    `sub_asset_class` al lado. Se toma el `ticker` y nada más."""
    real = json.dumps({
        "data": [{"ticker": "AL30", "asset_class": "BONO AL30",
                  "sub_asset_class": "HARD_DOLLAR"}],
        "query": "AL30",
        "pagination": {"next_cursor": None, "has_next": False},
        "metadata": {"total_records": 1},
    })
    assert cr.buscar_simbolo(
        "AL30", fetch=_fetch({"instruments/search": real})) == "AL30"


# ---------------------------------------------------------------------------
# La caché (M15): el uso correcto de una fuente con 15 requests por día
# ---------------------------------------------------------------------------

from core.db import connect, init_db          # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    init_db(ruta)
    conn = connect(ruta)
    yield conn
    conn.close()


def _guardar_al30(db):
    cron = cr.traer_cronograma("AL30", fetch=_fetch({"cashflow": CASHFLOW_AL30}))
    n = cr.guardar_cronograma(db, cron)
    db.commit()
    return n


def test_lo_guardado_se_lee_igual(db):
    assert _guardar_al30(db) == 2
    cron = cr.leer_cronograma(db, "AL30")
    assert cron is not None
    assert cron.clase == "HARD_DOLLAR"
    assert [f.fecha for f in cron.flujos] == [date(2027, 7, 9), date(2028, 1, 9)]
    assert cron.flujos[1].capital == pytest.approx(8.0)


def test_se_escala_a_la_tenencia_sin_gastar_cuota(db):
    """Los importes se guardan **por 100 nominales**, como los sirve la API.
    Escalar es una multiplicación al leer: el mismo cronograma cacheado sigue
    sirviendo aunque cambie la cantidad, **sin otra consulta**."""
    _guardar_al30(db)
    cron = cr.leer_cronograma(db, "AL30", nominales=9500)
    assert cron.flujos[1].capital == pytest.approx(8.0 * 95)
    assert cron.flujos[1].total == pytest.approx(8.36 * 95)
    assert cron.flujos[1].residual == pytest.approx(88.0 * 95)


def test_refrescar_no_vuelve_a_pedir_lo_que_ya_tiene(db):
    """Con 15 consultas por día, reintentar en cada carga vaciaría la cuota."""
    llamadas = []

    def contar(url, datos=None, cabeceras=None):
        llamadas.append(url)
        return TOKEN_OK if "auth/token" in url else CASHFLOW_AL30

    cr.refrescar_cronogramas(db, ["AL30"], fetch=contar)
    db.commit()
    n_primera = sum(1 for u in llamadas if "cashflow" in u)

    cr.refrescar_cronogramas(db, ["AL30"], fetch=contar)
    assert n_primera == 1
    assert sum(1 for u in llamadas if "cashflow" in u) == 1


def test_forzar_si_vuelve_a_pedir(db):
    llamadas = []

    def contar(url, datos=None, cabeceras=None):
        llamadas.append(url)
        return TOKEN_OK if "auth/token" in url else CASHFLOW_AL30

    cr.refrescar_cronogramas(db, ["AL30"], fetch=contar)
    db.commit()
    cr.refrescar_cronogramas(db, ["AL30"], fetch=contar, forzar=True)
    assert sum(1 for u in llamadas if "cashflow" in u) == 2


def test_el_pagare_se_marca_sin_consultar(db):
    """⚠️ **Caché negativa.** Confirmado el 5/8/2026 contra la cuenta real: el
    pagaré del MAV no está en el catálogo. Sin marcarlo, se consultaría en cada
    carga de la pantalla y se comería la cuota diaria sin traer nada nunca."""
    def no_deberia_llamarse(*a, **k):
        raise AssertionError("consultó por el pagaré")

    n, faltan = cr.refrescar_cronogramas(db, ["#UMV060770008"],
                                         fetch=no_deberia_llamarse)
    db.commit()
    assert (n, faltan) == (0, ["#UMV060770008"])
    assert cr.ya_consultado(db, "#UMV060770008") is True

    # Y en la segunda vuelta tampoco consulta.
    cr.refrescar_cronogramas(db, ["#UMV060770008"], fetch=no_deberia_llamarse)


def test_lo_que_la_fuente_no_tiene_no_se_reintenta(db):
    """Igual que el pagaré, pero para un ticker que sí se consultó y vino
    vacío: la constancia de 'ya pregunté' vale tanto como el dato."""
    llamadas = []

    def vacio(url, datos=None, cabeceras=None):
        llamadas.append(url)
        return TOKEN_OK if "auth/token" in url else '{"data": []}'

    cr.refrescar_cronogramas(db, ["RARO"], fetch=vacio)
    db.commit()
    cr.refrescar_cronogramas(db, ["RARO"], fetch=vacio)
    assert sum(1 for u in llamadas if "cashflow" in u) == 1


def test_sin_la_migracion_no_se_rompe(db):
    """Los cronogramas son una mejora, no un requisito para ver la cartera."""
    db.execute("DROP TABLE cartera_cronogramas")
    db.execute("DROP TABLE cartera_cronogramas_meta")
    db.commit()
    assert cr.leer_cronograma(db, "AL30") is None
    assert cr.ya_consultado(db, "AL30") is False


def test_volver_a_guardar_reemplaza_en_vez_de_duplicar(db):
    """Un refresco no puede dejar los flujos viejos mezclados con los nuevos:
    el calendario mostraría pagos fantasma."""
    _guardar_al30(db)
    _guardar_al30(db)
    n = db.execute("SELECT COUNT(*) FROM cartera_cronogramas "
                   "WHERE ticker = 'AL30'").fetchone()[0]
    assert n == 2
