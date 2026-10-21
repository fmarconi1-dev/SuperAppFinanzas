"""Balances de la semana (ADR-0011, paso 2): la lista del domingo y la respuesta.

Base sintética y fuentes falsas (`FuentesFalsas`); el servidor real en un
puerto libre para `POST /api/balances`. Nada sale a internet ni a Meta.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

import pytest

import api
import core.db as core_db
from core.api.balances_fuentes import CalendarioNoDisponible, FilaCalendario, ListaNoDisponible
from core.api.servidor import crear_servidor
from core.context import set_current_workspace_id
from core.db import connect, init_db
from core.workspaces import resolve_workspace_id
from places.finanzas.core import balances, lotes
from places.finanzas.core.balances import Eleccion, leer_respuesta
from places.finanzas.core.comandos import ZONA, procesar
from places.finanzas.core.transactions import insert_transaction
from tests.test_api_whatsapp import CFG

UID = 1
LUNES = date(2026, 10, 26)
#: El domingo a la noche, cuando llega la lista.
DOMINGO = datetime(2026, 10, 25, 20, 10, tzinfo=ZONA)
TOKEN = "token-de-la-api"

B = 1_000_000_000   # mil millones de dólares


def _f(ticker, dia, momento="post", cap=100 * B, nombre=None):
    return FilaCalendario(ticker, nombre or f"{ticker} Inc.", LUNES + timedelta(days=dia),
                          momento, cap)


#: Una semana parecida a la del 26/10/2026 que trajo Nasdaq el 20/10.
SEMANA = [
    _f("KO", 1, "pre", 300 * B, "Coca-Cola Company (The)"),
    _f("GOOGL", 2, "post", 4161 * B, "Alphabet Inc."),
    _f("GOOG", 2, "post", 4161 * B, "Alphabet Inc."),     # la otra clase: no va
    _f("MSFT", 2, "post", 3800 * B, "Microsoft Corporation"),
    _f("VIST", 2, "post", 6 * B),
    _f("AMZN", 3, "post", 2500 * B),
    _f("SAP", 1, "post", 277 * B),                          # ni del S&P ni de la lista
    _f("V", 1, "post", 650 * B),
    _f("VZ", 0, "pre", 170 * B),
    _f("FOX", 0, "post", 20 * B, "Fox Corporation"),
    _f("FOXA", 0, "post", 20 * B, "Fox Corporation"),       # la otra clase: no va
    _f("XOM", 4, "pre", 480 * B),
    _f("LLY", 3, "pre", 800 * B),
    _f("MA", 3, "pre", 520 * B),
    _f("CAT", 3, None, 190 * B),
] + [_f(f"S{i:02d}", i % 5, "pre", (50 - i) * B) for i in range(20)]

SP500 = {"KO", "GOOGL", "GOOG", "MSFT", "AMZN", "V", "VZ", "FOX", "FOXA", "XOM", "LLY", "MA",
         "CAT"} | {f"S{i:02d}" for i in range(20)}


class FuentesFalsas:
    def __init__(self, filas=SEMANA, sp=SP500, falla_calendario=None, falla_sp=None):
        self.filas, self.sp = filas, sp
        self.falla_calendario, self.falla_sp = falla_calendario, falla_sp
        self.pedidos_calendario: list[tuple[date, date]] = []
        self.pedidos_sp = 0

    def calendario(self, desde, hasta):
        self.pedidos_calendario.append((desde, hasta))
        if self.falla_calendario:
            raise CalendarioNoDisponible(self.falla_calendario)
        return [f for f in self.filas if desde <= f.fecha <= hasta]

    def lista_sp500(self):
        self.pedidos_sp += 1
        if self.falla_sp:
            raise ListaNoDisponible(self.falla_sp)
        return sorted(self.sp)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(db_path)
    conn = connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) VALUES (1, 'franco', 'Franco')")
    set_current_workspace_id(None)
    for motivo in ("Supermercado", "Transportes"):
        insert_transaction(conn, fecha=date(2026, 9, 1), motivo=motivo, pasivos=1, user_id=UID)
        conn.execute("UPDATE categorias SET grupo = 'Gasto Variable' WHERE motivo = ?", (motivo,))
    conn.execute("DELETE FROM transacciones")
    yield conn
    set_current_workspace_id(None)
    conn.close()


def _wid(conn):
    return resolve_workspace_id(conn, UID)


def _armar(conn, fuentes=None, ahora=DOMINGO):
    return balances.armar(conn, workspace_id=_wid(conn), lunes=LUNES,
                          fuentes=fuentes or FuentesFalsas(), ahora=ahora)


def _p(conn, texto, ahora=DOMINGO, fuentes=None):
    return procesar(conn, texto, user_id=UID, ahora=ahora, fuentes_balances=fuentes)


def _prop(conn, ahora=DOMINGO):
    return balances.vigente(conn, workspace_id=_wid(conn), ahora=ahora)


# ------------------------------------------------------------------ armar la lista

def test_primero_mi_lista_despues_las_15_mas_grandes_y_el_resto():
    items, principales = balances.elegir(SEMANA, SP500)
    mias = [it["ticker"] for it in items if it["grupo"] == "mia"]
    grandes = [it["ticker"] for it in items if it["grupo"] == "grande"]
    resto = [it["ticker"] for it in items if it["grupo"] == "resto"]
    # La lista de Franco, por fecha (y antes de la apertura primero).
    assert mias == ["KO", "GOOGL", "MSFT", "VIST", "AMZN"]
    assert len(grandes) == balances.CANTIDAD_GRANDES and principales == 5 + 15
    # Las más grandes del S&P fuera de la lista: V (650) entra, la S19 (31) no.
    assert "V" in grandes and "LLY" in grandes and "S19" in resto
    # Ni la otra clase de Alphabet o de Fox, ni las que no son del S&P (SAP).
    todas = mias + grandes + resto
    assert "GOOG" not in todas and todas.count("FOX") + todas.count("FOXA") == 1
    assert "SAP" not in todas
    assert [it["n"] for it in items] == list(range(1, len(items) + 1))


def test_las_grandes_van_por_fecha_dentro_del_mensaje():
    items, principales = balances.elegir(SEMANA, SP500)
    fechas = [it["fecha"] for it in items[5:principales]]
    assert fechas == sorted(fechas)


def test_el_texto_de_la_lista(db):
    texto = _armar(db)
    assert texto.startswith("📊 *Balances de la semana* (26/10 al 30/10)")
    assert "*Tu lista*\n1. KO — mar 27/10, pre-apertura\n2. GOOGL — mié 28/10, post-cierre" in texto
    assert "*S&P 500, las más grandes*" in texto
    assert "CAT — jue 29/10, sin hora" in texto
    assert "*todas* (las de este mensaje)" in texto
    resto = len(SEMANA) - 1 - 1 - 1 - 20        # sin SAP, GOOG, FOXA ni los 20 del mensaje
    assert f"*balances todas* muestra las otras {resto} del S&P 500." in texto
    assert len(texto) < 4096                     # entra en un solo WhatsApp


def test_una_semana_sin_nadie(db):
    texto = _armar(db, FuentesFalsas(filas=[]))
    assert "Ninguna de tu lista ni de las grandes del S&P 500" in texto
    assert _prop(db) is None


def test_sin_nadie_de_mi_lista():
    items, principales = balances.elegir([_f("V", 1)], {"V"})
    texto = balances.texto_lista(items, principales, LUNES, None)
    assert "*Tu lista*\nNinguna presenta esta semana." in texto


def test_una_lista_nueva_reemplaza_a_la_anterior(db):
    _armar(db)
    primera = _prop(db)
    _armar(db, FuentesFalsas(filas=[_f("KO", 1)]))
    segunda = _prop(db)
    assert segunda.id != primera.id and [it["ticker"] for it in segunda.items] == ["KO"]


def test_la_lista_vence_al_terminar_el_viernes(db):
    _armar(db)
    assert _prop(db, datetime(2026, 10, 30, 23, 59, tzinfo=ZONA)) is not None
    assert _prop(db, datetime(2026, 10, 31, 0, 0, tzinfo=ZONA)) is None


def test_el_calendario_caido_no_deja_lista(db):
    with pytest.raises(CalendarioNoDisponible):
        _armar(db, FuentesFalsas(falla_calendario="Nasdaq respondió HTTP 503"))
    assert _prop(db) is None


def test_la_lista_pide_de_lunes_a_viernes(db):
    fuentes = FuentesFalsas()
    _armar(db, fuentes)
    assert fuentes.pedidos_calendario == [(LUNES, date(2026, 10, 30))]


# ------------------------------------------------------------------ el S&P 500, una vez por mes

def test_el_sp500_se_pide_una_vez_por_mes(db):
    fuentes = FuentesFalsas()
    _armar(db, fuentes)
    _armar(db, fuentes, DOMINGO + timedelta(days=29))
    assert fuentes.pedidos_sp == 1
    _armar(db, fuentes, DOMINGO + timedelta(days=31))
    assert fuentes.pedidos_sp == 2


def test_wikipedia_caida_usa_la_lista_guardada(db):
    _armar(db)
    texto = _armar(db, FuentesFalsas(falla_sp="Wikipedia respondió HTTP 500"),
                   DOMINGO + timedelta(days=40))
    assert "s/d" not in texto and "V — mar 27/10" in texto


def test_wikipedia_caida_sin_lista_guardada_dice_sd(db):
    texto = _armar(db, FuentesFalsas(falla_sp="Wikipedia respondió HTTP 500"))
    assert "S&P 500: s/d (no pude traer la lista: Wikipedia respondió HTTP 500)" in texto
    assert "1. KO" in texto                       # la lista de Franco sale igual
    assert "V — mar 27/10" not in texto


# ------------------------------------------------------------------ leer la respuesta

@pytest.fixture()
def prop(db):
    _armar(db)
    return _prop(db)


@pytest.mark.parametrize("texto, esperado", [
    ("1 3 7", Eleccion(numeros=(1, 3, 7))),
    ("1, 3,7", Eleccion(numeros=(1, 3, 7))),
    ("ko msft", Eleccion(tickers=("KO", "MSFT"))),
    ("KO 3", Eleccion(numeros=(3,), tickers=("KO",))),
    ("todas", Eleccion(todas=True)),
    ("Ninguna.", Eleccion(ninguna=True)),
    ("balances 1 3", Eleccion(numeros=(1, 3), explicita=True)),
])
def test_respuestas_que_eligen(prop, texto, esperado):
    assert leer_respuesta(texto, prop) == esperado


@pytest.mark.parametrize("texto", ["1500", "2500 super", "0", "999", "aapl", "ok", "no", "",
                                   "agenda", "1 transportes"])
def test_lo_que_no_es_una_respuesta(prop, texto):
    assert leer_respuesta(texto, prop) is None


# ------------------------------------------------------------------ anotar lo elegido

def test_anota_y_suma(db, prop):
    texto = balances.responder(db, prop, Eleccion(numeros=(1, 3)), LUNES)
    assert texto.startswith("✅ Anotado: KO (mar 27/10, pre-apertura), MSFT (mié 28/10, "
                            "post-cierre).")
    assert "próximo paso" in texto
    texto = balances.responder(db, _prop(db), Eleccion(tickers=("KO", "AMZN")), LUNES)
    assert "Anotado: AMZN" in texto and "Ya las tenías: KO." in texto
    assert _prop(db).elegidos == ["KO", "MSFT", "AMZN"]


def test_lo_que_ya_paso_no_se_agenda(db, prop):
    """Franco, 21/10/2026: si la lista llega tarde, lo que ya pasó no se agenda."""
    miercoles = date(2026, 10, 28)
    texto = balances.responder(db, prop, Eleccion(numeros=(1, 2)), miercoles)
    assert "Anotado: GOOGL" in texto                # el balance es hoy: todavía sirve
    assert "No las agendo porque ya pasaron: KO (mar 27/10, pre-apertura)." in texto
    assert _prop(db).elegidos == ["GOOGL"]


def test_todas_son_las_del_mensaje(db, prop):
    balances.responder(db, prop, Eleccion(todas=True), LUNES)
    assert len(_prop(db).elegidos) == prop.principales


def test_ninguna(db, prop):
    assert balances.responder(db, prop, Eleccion(ninguna=True), LUNES) == \
        "Listo, esta semana no agendo ninguna."
    balances.responder(db, prop, Eleccion(numeros=(1,)), LUNES)
    assert "sigue anotado: KO" in balances.responder(db, _prop(db), Eleccion(ninguna=True), LUNES)


def test_balances_todas_muestra_el_resto(prop):
    texto = balances.texto_resto(prop)
    assert texto.startswith(f"📊 Las otras {len(prop.items) - prop.principales} del S&P 500")
    assert f"{prop.principales + 1}. " in texto


# ------------------------------------------------------------------ por WhatsApp (procesar)

def test_el_comando_balances_arma_la_semana(db):
    martes = datetime(2026, 10, 27, 10, 0, tzinfo=ZONA)
    fuentes = FuentesFalsas()
    r = _p(db, "Balances", martes, fuentes)
    assert r.resultado == "consulta" and "📊 *Balances de la semana* (26/10 al 30/10)" in r.texto
    assert fuentes.pedidos_calendario == [(LUNES, date(2026, 10, 30))]
    # Un domingo arma la semana que viene.
    fuentes = FuentesFalsas()
    _p(db, "balances", DOMINGO, fuentes)
    assert fuentes.pedidos_calendario == [(LUNES, date(2026, 10, 30))]


def test_contestar_por_whatsapp(db):
    _armar(db)
    r = _p(db, "1 3")
    assert r.resultado == "consulta" and r.texto.startswith("✅ Anotado: KO")
    r = _p(db, "balances todas")
    assert r.texto.startswith("📊 Las otras")


def test_sin_fuentes_o_con_nasdaq_caido(db):
    assert _p(db, "balances").texto == "Los balances no están conectados."
    r = _p(db, "balances", fuentes=FuentesFalsas(falla_calendario="Nasdaq respondió HTTP 503"))
    assert r.resultado == "rechazado" and "Nasdaq respondió HTTP 503" in r.texto


def test_sin_lista_vigente(db):
    assert "No tengo una lista de balances vigente" in _p(db, "balances todas").texto
    assert "No tengo una lista de balances vigente" in _p(db, "balances 1 3").texto
    assert _p(db, "1 3").resultado == "rechazado"   # sin lista no es nada (ni un gasto)


def test_una_eleccion_que_no_se_entiende(db):
    _armar(db)
    assert "No entendí cuáles elegís" in _p(db, "balances aapl").texto


def test_un_gasto_sigue_siendo_un_gasto(db):
    _armar(db)
    r = _p(db, "2500, supermercado")
    assert r.resultado == "cargado"


def test_la_lista_no_descarta_un_lote_abierto(db):
    """Un lote nuevo descarta al anterior; la lista de balances, no."""
    r = _p(db, "2500, super\n800, transportes")
    assert r.resultado == "pendiente"
    _armar(db)
    assert lotes.vigente(db, workspace_id=_wid(db), ahora=DOMINGO) is not None
    # "1 2" puede ser de cualquiera de las dos: no se adivina.
    r = _p(db, "1 2")
    assert r.resultado == "rechazado" and "empezá con *balances*" in r.texto
    assert _prop(db).elegidos == []
    r = _p(db, "balances 1 2")
    assert r.texto.startswith("✅ Anotado: KO")
    # El lote sigue esperando su ok.
    assert _p(db, "ok").resultado == "lote"


def test_los_tickers_no_chocan_con_un_lote(db):
    _p(db, "2500, super\n800, transportes")
    _armar(db)
    assert _p(db, "ko msft").texto.startswith("✅ Anotado: KO")


def test_la_ayuda_nombra_los_balances(db):
    assert "balances" in _p(db, "ayuda").texto


# ------------------------------------------------------------------ POST /api/balances

@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    db_path = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(db_path)
    conn = connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) VALUES (1, 'franco', 'Franco')")
    conn.execute("UPDATE usuarios SET username = 'franco' WHERE id = 1")
    conn.close()
    set_current_workspace_id(None)

    fuentes = FuentesFalsas()
    enviados: list[tuple[str, str]] = []

    def armar(conn, datos, user_id):
        if datos.get("lunes") != LUNES.isoformat():
            raise ValueError("lunes equivocado")
        return balances.armar(conn, workspace_id=resolve_workspace_id(conn, user_id),
                              lunes=LUNES, fuentes=fuentes, ahora=DOMINGO)

    srv = crear_servidor(
        "127.0.0.1", 0, procesar=api._procesar, componer=api._componer, balances=armar,
        enviar=lambda cfg, numero, texto: enviados.append((numero, texto)) or ["w"],
        cargar_config=lambda: CFG, cargar_token_api=lambda: TOKEN, db_path=db_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield {"url": f"http://127.0.0.1:{srv.server_address[1]}", "db": db_path,
           "fuentes": fuentes, "enviados": enviados}
    srv.shutdown()
    srv.server_close()
    set_current_workspace_id(None)


def _post(url, cuerpo, token=TOKEN):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    pedido = urllib.request.Request(url + "/api/balances", data=json.dumps(cuerpo).encode(),
                                    headers=headers, method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


SEMANA_POST = {"accion": "semana", "lunes": "2026-10-26", "id": "balances-2026-10-26"}


def _salientes(db_path):
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT tipo, texto, id_origen FROM whatsapp_salientes ORDER BY id")]
    finally:
        conn.close()


def test_la_lista_del_domingo_va_a_la_cola(entorno):
    codigo, r = _post(entorno["url"], SEMANA_POST)
    assert codigo == 200 and r["ok"] is True and r["estado"] == "en_cola"   # ventana cerrada
    (fila,) = _salientes(entorno["db"])
    assert fila["tipo"] == "balances" and fila["id_origen"] == "balances-2026-10-26"
    assert fila["texto"].startswith("📊 *Balances de la semana*")
    assert entorno["enviados"] == []


def test_un_reintento_no_rearma_la_lista(entorno):
    _post(entorno["url"], SEMANA_POST)
    codigo, r = _post(entorno["url"], SEMANA_POST)
    assert codigo == 200 and r["repetido"] is True
    assert len(entorno["fuentes"].pedidos_calendario) == 1
    assert len(_salientes(entorno["db"])) == 1


def test_nasdaq_caido_es_503_para_que_el_apps_script_reintente(entorno):
    entorno["fuentes"].falla_calendario = "Nasdaq respondió HTTP 503"
    codigo, r = _post(entorno["url"], SEMANA_POST)
    assert codigo == 503 and r["error"] == "calendario_no_disponible"
    assert "Nasdaq" in r["detalle"] and _salientes(entorno["db"]) == []


@pytest.mark.parametrize("cuerpo", [
    {"accion": "otra", "lunes": "2026-10-26", "id": "x"},
    {"accion": "semana", "lunes": "2026-10-26"},
    {"accion": "semana", "lunes": "2026-10-27", "id": "x"},
])
def test_pedidos_que_no_sirven(entorno, cuerpo):
    codigo, r = _post(entorno["url"], cuerpo)
    assert codigo == 400 and r["error"] == "parametros_invalidos"


def test_sin_token_o_con_otro(entorno):
    assert _post(entorno["url"], SEMANA_POST, token=None)[0] == 401
    assert _post(entorno["url"], SEMANA_POST, token="otro")[0] == 401


def test_el_lunes_de_api_tiene_que_ser_lunes(db):
    with pytest.raises(ValueError, match="no es lunes"):
        api._balances(db, {"lunes": "2026-10-27"}, UID)
    with pytest.raises(ValueError, match="AAAA-MM-DD"):
        api._balances(db, {"lunes": "27/10"}, UID)
