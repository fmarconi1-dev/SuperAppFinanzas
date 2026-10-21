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
from core.api.balances_fuentes import (
    CalendarioNoDisponible,
    FechaAnunciada,
    FilaCalendario,
    ListaNoDisponible,
    PrecioNoDisponible,
)
from core.api.google import AgendaNoDisponible, AgendaRechazo
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

    #: Lo que dice la ficha de Nasdaq de cada empresa: FechaAnunciada, None o
    #: una excepción. Las que no están, None (la ficha no dice nada).
    anuncios: dict = {}

    def fecha_anunciada(self, ticker):
        r = self.anuncios.get(ticker)
        if isinstance(r, Exception):
            raise r
        return r


class AgendaFalsa:
    """Se porta como `Codigo.gs`: un evento por clave; repetir la clave no duplica."""

    def __init__(self, falla=None):
        self.falla = falla
        self.calendario: dict[str, dict] = {}
        self.pedidos: list[tuple[str, object]] = []

    def agendar_balances(self, *, eventos):
        self.pedidos.append(("agendar", eventos))
        if self.falla:
            raise self.falla
        salida = []
        for e in eventos:
            creado = e["clave"] not in self.calendario
            self.calendario.setdefault(e["clave"], e)
            salida.append({"clave": e["clave"], "id": "ev-" + e["clave"], "creado": creado})
        return {"ok": True, "eventos": salida}

    def borrar_balances(self, *, claves):
        self.pedidos.append(("borrar", claves))
        if self.falla:
            raise self.falla
        borrados = [c for c in claves if self.calendario.pop(c, None)]
        return {"ok": True, "borrados": borrados,
                "no_estaban": [c for c in claves if c not in borrados]}


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


def _p(conn, texto, ahora=DOMINGO, fuentes=None, agenda=None):
    return procesar(conn, texto, user_id=UID, ahora=ahora, fuentes_balances=fuentes,
                    agenda=agenda)


def _prop(conn, ahora=DOMINGO):
    return balances.vigente(conn, workspace_id=_wid(conn), ahora=ahora)


def _responder(conn, eleccion, hoy=LUNES, agenda=None, fuentes=None, ahora=DOMINGO):
    """(texto, resultado), con una agenda falsa nueva si no se pasa una."""
    return balances.responder(conn, _prop(conn, ahora), eleccion, hoy, workspace_id=_wid(conn),
                              ahora=ahora, agenda=agenda if agenda is not None else AgendaFalsa(),
                              fuentes=fuentes)


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


def test_rearmar_la_misma_semana_no_pierde_lo_elegido(db):
    """`balances` el domingo a las 19 y el disparador a las 20: lo elegido sigue."""
    _armar(db)
    _responder(db, Eleccion(tickers=("KO", "MSFT")))
    _armar(db, FuentesFalsas(filas=[f for f in SEMANA if f.ticker != "MSFT"]),
           DOMINGO + timedelta(minutes=50))
    assert _prop(db).elegidos == ["KO"]            # MSFT ya no está en el calendario
    # Otra semana empieza de cero.
    balances.armar(db, workspace_id=_wid(db), lunes=LUNES + timedelta(days=7),
                   fuentes=FuentesFalsas(filas=[]), ahora=DOMINGO)
    assert _prop(db) is None


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


# ------------------------------------------------------------------ agendar lo elegido

def test_agenda_y_suma(db, prop):
    agenda = AgendaFalsa()
    texto, resultado = _responder(db, Eleccion(numeros=(1, 3)), agenda=agenda)
    assert resultado == "agendado"
    assert texto.startswith("📅 Agendé en tu Calendar: KO (mar 27/10, pre-apertura), "
                            "MSFT (mié 28/10, post-cierre).")
    assert texto.endswith("*deshacer* las saca del Calendar.")
    assert set(agenda.calendario) == {"KO:2026-10-27", "MSFT:2026-10-28"}
    ko = agenda.calendario["KO:2026-10-27"]
    assert ko["titulo"] == "📊 KO balance (pre-apertura)" and ko["momento"] == "pre"
    assert ko["fecha"] == "2026-10-27" and "Coca-Cola" in ko["descripcion"]
    texto, _ = _responder(db, Eleccion(tickers=("KO", "AMZN")), agenda=agenda)
    assert "Agendé en tu Calendar: AMZN" in texto and "Ya las tenías en el Calendar: KO." in texto
    # Se le pregunta todo al Calendar: él dice qué ya estaba.
    assert [e["clave"] for e in agenda.pedidos[-1][1]] == ["KO:2026-10-27", "AMZN:2026-10-29"]
    assert _prop(db).elegidos == ["KO", "MSFT", "AMZN"]


def test_lo_anotado_en_el_paso_2_se_agenda_igual(db, prop):
    """En el paso 2 lo elegido quedaba anotado sin llegar a Google: no cuenta como agendado."""
    db.execute("UPDATE balances_propuestas SET elegidos = '[\"KO\"]' WHERE id = ?", (prop.id,))
    agenda = AgendaFalsa()
    texto, resultado = _responder(db, Eleccion(numeros=(1,)), agenda=agenda)
    assert resultado == "agendado" and "KO:2026-10-27" in agenda.calendario
    assert "Ya las tenías" not in texto and _prop(db).elegidos == ["KO"]


def test_un_evento_borrado_a_mano_se_vuelve_a_crear(db, prop):
    """El Calendar es la fuente de verdad (Franco): si lo borró, elegirlo de nuevo lo crea."""
    agenda = AgendaFalsa()
    _responder(db, Eleccion(numeros=(1,)), agenda=agenda)
    del agenda.calendario["KO:2026-10-27"]                  # Franco lo borró a mano
    texto, resultado = _responder(db, Eleccion(numeros=(1,)), agenda=agenda)
    assert resultado == "agendado" and texto.startswith("📅 Agendé en tu Calendar: KO")
    assert "KO:2026-10-27" in agenda.calendario and "Ya las tenías" not in texto


def test_deshacer_no_borra_lo_que_ya_estaba_de_antes(db):
    _armar(db)
    agenda = AgendaFalsa()
    _p(db, "1", agenda=agenda)                                  # KO
    r = _p(db, "1 3", DOMINGO + timedelta(minutes=1), agenda=agenda)
    assert "Ya las tenías en el Calendar: KO." in r.texto       # solo MSFT es nuevo
    r = _p(db, "deshacer", DOMINGO + timedelta(minutes=2), agenda=agenda)
    assert r.texto == "↩️ Saqué de tu Calendar: MSFT (mié 28/10)."
    assert set(agenda.calendario) == {"KO:2026-10-27"}


def test_si_ya_estaban_todas_no_hay_tanda_que_deshacer(db, prop):
    agenda = AgendaFalsa()
    _responder(db, Eleccion(numeros=(1,)), agenda=agenda)
    texto, resultado = _responder(db, Eleccion(numeros=(1,)), agenda=agenda)
    assert resultado == "consulta" and texto == "Ya las tenías en el Calendar: KO."
    assert db.execute("SELECT COUNT(*) FROM balances_agendados").fetchone()[0] == 1


def test_lo_que_google_no_confirma_se_avisa_y_no_se_anota(db, prop):
    class AgendaMuda(AgendaFalsa):
        def agendar_balances(self, *, eventos):
            super().agendar_balances(eventos=eventos)
            return {"ok": True}                                  # sin "eventos"

    texto, resultado = _responder(db, Eleccion(numeros=(1,)), agenda=AgendaMuda())
    assert resultado == "consulta" and "Google no me confirmó estas: KO" in texto
    assert _prop(db).elegidos == []
    assert db.execute("SELECT COUNT(*) FROM balances_agendados").fetchone()[0] == 0


def test_lo_que_ya_paso_no_se_agenda(db, prop):
    """Franco, 21/10/2026: si la lista llega tarde, lo que ya pasó no se agenda."""
    miercoles = date(2026, 10, 28)
    texto, _ = _responder(db, Eleccion(numeros=(1, 2)), hoy=miercoles)
    assert "Agendé en tu Calendar: GOOGL" in texto       # el balance es hoy: todavía sirve
    assert "No las agendo porque ya pasaron: KO (mar 27/10, pre-apertura)." in texto
    assert _prop(db).elegidos == ["GOOGL"]


def test_si_todo_ya_paso_no_se_llama_a_google(db, prop):
    agenda = AgendaFalsa()
    texto, resultado = _responder(db, Eleccion(numeros=(1,)), hoy=date(2026, 10, 30),
                                  agenda=agenda)
    assert resultado == "consulta" and agenda.pedidos == []
    assert texto.startswith("No las agendo porque ya pasaron: KO")


def test_todas_son_las_del_mensaje(db, prop):
    agenda = AgendaFalsa()
    _responder(db, Eleccion(todas=True), agenda=agenda)
    assert len(_prop(db).elegidos) == prop.principales == len(agenda.calendario)


def test_ninguna(db, prop):
    assert _responder(db, Eleccion(ninguna=True)) == ("Listo, esta semana no agendo ninguna.",
                                                      "consulta")
    _responder(db, Eleccion(numeros=(1,)))
    assert "sigue: KO" in _responder(db, Eleccion(ninguna=True))[0]


def test_la_ficha_de_nasdaq_marca_la_fecha_estimada_y_completa_el_momento(db, prop):
    fuentes = FuentesFalsas()
    fuentes.anuncios = {
        "MSFT": FechaAnunciada(date(2026, 10, 28), "post", estimada=False),
        "VIST": FechaAnunciada(date(2026, 10, 28), None, estimada=True),
        "CAT": FechaAnunciada(date(2026, 10, 29), "pre", estimada=False),   # el calendario: sin hora
    }
    agenda = AgendaFalsa()
    cat = next(it["n"] for it in prop.items if it["ticker"] == "CAT")
    texto, _ = _responder(db, Eleccion(numeros=(3, 4, cat)), agenda=agenda, fuentes=fuentes)
    assert agenda.calendario["MSFT:2026-10-28"]["titulo"] == "📊 MSFT balance (post-cierre)"
    assert "confirmada por la empresa" in agenda.calendario["MSFT:2026-10-28"]["descripcion"]
    assert agenda.calendario["VIST:2026-10-28"]["titulo"] == \
        "📊 VIST balance (post-cierre, fecha estimada)"
    assert agenda.calendario["CAT:2026-10-29"]["momento"] == "pre"
    assert "VIST (mié 28/10, post-cierre) — fecha estimada" in texto


def test_si_la_ficha_dice_otra_fecha_gana_la_ficha(db, prop):
    fuentes = FuentesFalsas()
    fuentes.anuncios = {"KO": FechaAnunciada(date(2026, 10, 29), "pre", estimada=False)}
    agenda = AgendaFalsa()
    texto, _ = _responder(db, Eleccion(numeros=(1,)), agenda=agenda, fuentes=fuentes)
    assert set(agenda.calendario) == {"KO:2026-10-29"}
    assert "KO: Nasdaq ahora dice jue 29/10 (la lista decía mar 27/10)." in texto


def test_si_la_ficha_no_contesta_se_agenda_y_se_avisa(db, prop):
    fuentes = FuentesFalsas()
    fuentes.anuncios = {"KO": CalendarioNoDisponible("Nasdaq respondió HTTP 403")}
    agenda = AgendaFalsa()
    texto, resultado = _responder(db, Eleccion(numeros=(1,)), agenda=agenda, fuentes=fuentes)
    assert resultado == "agendado" and "KO:2026-10-27" in agenda.calendario
    assert "estimada" not in agenda.calendario["KO:2026-10-27"]["titulo"]
    assert "según el calendario de Nasdaq" in agenda.calendario["KO:2026-10-27"]["descripcion"]
    assert "No pude ver en Nasdaq si la fecha es estimada o confirmada: KO." in texto


@pytest.mark.parametrize("falla", [AgendaNoDisponible("no se pudo conectar con el Apps Script"),
                                   AgendaRechazo("error_interno", "Calendar")])
def test_si_google_falla_no_se_anota_nada(db, prop, falla):
    texto, resultado = _responder(db, Eleccion(numeros=(1, 3)), agenda=AgendaFalsa(falla))
    assert resultado == "error" and texto.startswith("⚠️ No pude agendar en tu Calendar")
    assert _prop(db).elegidos == []
    assert db.execute("SELECT COUNT(*) FROM balances_agendados").fetchone()[0] == 0
    # El reintento anda y no duplica.
    agenda = AgendaFalsa()
    _responder(db, Eleccion(numeros=(1, 3)), agenda=agenda)
    assert _prop(db).elegidos == ["KO", "MSFT"]


def test_sin_agenda_conectada(db, prop):
    texto, resultado = balances.responder(db, prop, Eleccion(numeros=(1,)), LUNES,
                                          workspace_id=_wid(db), ahora=DOMINGO, agenda=None)
    assert resultado == "rechazado" and "no está conectada" in texto
    assert _prop(db).elegidos == []


# ------------------------------------------------------------------ deshacer

def test_deshacer_saca_del_calendar_lo_ultimo_agendado(db):
    _armar(db)
    agenda = AgendaFalsa()
    _p(db, "1 3", agenda=agenda)
    _p(db, "5", DOMINGO + timedelta(minutes=1), agenda=agenda)
    r = _p(db, "deshacer", DOMINGO + timedelta(minutes=2), agenda=agenda)
    assert r.resultado == "deshecho" and r.texto == "↩️ Saqué de tu Calendar: AMZN (jue 29/10)."
    assert set(agenda.calendario) == {"KO:2026-10-27", "MSFT:2026-10-28"}
    assert _prop(db).elegidos == ["KO", "MSFT"]
    r = _p(db, "deshacer", DOMINGO + timedelta(minutes=3), agenda=agenda)
    assert r.texto == "↩️ Saqué de tu Calendar: KO (mar 27/10), MSFT (mié 28/10)."
    assert agenda.calendario == {} and _prop(db).elegidos == []
    # Ya no queda nada: lo dice como siempre.
    assert "No hay nada" in _p(db, "deshacer", DOMINGO + timedelta(minutes=4), agenda=agenda).texto
    # Y se pueden volver a elegir.
    assert _p(db, "1", DOMINGO + timedelta(minutes=5), agenda=agenda).resultado == "agendado"


def _registrar(conn, wamid, r, cuando):
    """Lo que hace el servidor después de `procesar`."""
    conn.execute(
        "INSERT INTO whatsapp_mensajes (wamid, recibido_en, remitente, texto, transaccion_id, "
        "resultado) VALUES (?, ?, '541100000000', '', ?, ?)",
        (wamid, cuando.isoformat(), r.transaccion_id, r.resultado))


def test_deshacer_respeta_el_orden_con_un_gasto(db):
    _armar(db)
    agenda = AgendaFalsa()
    _p(db, "1", agenda=agenda)
    cuando = DOMINGO + timedelta(minutes=1)
    _registrar(db, "w1", _p(db, "2500, supermercado", cuando), cuando)
    # Lo último fue el gasto: se borra el gasto, el Calendar queda igual.
    r = _p(db, "deshacer", DOMINGO + timedelta(minutes=2), agenda=agenda)
    assert r.texto.startswith("↩️ Borré #") and "KO:2026-10-27" in agenda.calendario
    # Ahora sí, lo de los balances.
    r = _p(db, "deshacer", DOMINGO + timedelta(minutes=3), agenda=agenda)
    assert r.texto.startswith("↩️ Saqué de tu Calendar: KO")


def test_deshacer_con_google_caido_no_marca_nada(db):
    _armar(db)
    agenda = AgendaFalsa()
    _p(db, "1", agenda=agenda)
    agenda.falla = AgendaNoDisponible("timeout")
    r = _p(db, "deshacer", DOMINGO + timedelta(minutes=1), agenda=agenda)
    assert r.resultado == "error" and "No pude sacar los balances" in r.texto
    assert _prop(db).elegidos == ["KO"]
    agenda.falla = None
    assert _p(db, "deshacer", DOMINGO + timedelta(minutes=2), agenda=agenda).resultado == "deshecho"


def test_deshacer_avisa_lo_que_ya_no_estaba(db):
    _armar(db)
    agenda = AgendaFalsa()
    _p(db, "1 3", agenda=agenda)
    del agenda.calendario["KO:2026-10-27"]                 # Franco lo borró a mano
    r = _p(db, "deshacer", DOMINGO + timedelta(minutes=1), agenda=agenda)
    assert "Ya no estaban (¿los borraste a mano?): KO." in r.texto


def test_deshacer_no_alcanza_lo_de_hace_mas_de_un_dia(db):
    _armar(db)
    agenda = AgendaFalsa()
    _p(db, "1", agenda=agenda)
    r = _p(db, "deshacer", DOMINGO + timedelta(hours=25), agenda=agenda)
    assert r.resultado == "rechazado" and "KO:2026-10-27" in agenda.calendario


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
    r = _p(db, "1 3", agenda=AgendaFalsa())
    assert r.resultado == "agendado" and r.texto.startswith("📅 Agendé en tu Calendar: KO")
    r = _p(db, "balances todas")
    assert r.texto.startswith("📊 Las otras")
    assert _p(db, "balances todos").texto == r.texto


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
    r = _p(db, "balances 1 2", agenda=AgendaFalsa())
    assert r.texto.startswith("📅 Agendé en tu Calendar: KO")
    # El lote sigue esperando su ok.
    assert _p(db, "ok").resultado == "lote"


def test_los_tickers_no_chocan_con_un_lote(db):
    _p(db, "2500, super\n800, transportes")
    _armar(db)
    assert _p(db, "ko msft", agenda=AgendaFalsa()).texto.startswith("📅 Agendé en tu Calendar: KO")


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
        if datos.get("accion") == "resumen":
            return balances.resumen_del_dia(date.fromisoformat(datos["fecha"]), datos["empresas"],
                                            PreciosFalsos())
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


# ------------------------------------------------------------------ el resumen del día (paso 4)

MIERCOLES = date(2026, 10, 28)


class PreciosFalsos:
    """Cierres y posmercado como los daría Yahoo. Un valor Exception se tira."""

    def __init__(self, cierres=None, post=None):
        self._cierres = cierres if cierres is not None else {
            "MSFT": {date(2026, 10, 27): 400.0, MIERCOLES: 410.0},
            "KO": {date(2026, 10, 27): 70.0, MIERCOLES: 68.39},
            "CAT": {date(2026, 10, 27): 300.0, MIERCOLES: 302.7},
        }
        self._post = post if post is not None else {"MSFT": 426.81, "CAT": 303.0}
        self.pedidos: list[tuple] = []

    def cierres(self, ticker):
        self.pedidos.append(("cierres", ticker))
        r = self._cierres.get(ticker, PrecioNoDisponible("Yahoo respondió HTTP 404"))
        if isinstance(r, Exception):
            raise r
        return r

    def ultimo_del_posmercado(self, ticker, fecha):
        self.pedidos.append(("post", ticker, fecha))
        r = self._post.get(ticker, PrecioNoDisponible(f"{ticker} no operó en el posmercado"))
        if isinstance(r, Exception):
            raise r
        return r


def test_el_resumen_como_lo_pidio_franco():
    texto = balances.resumen_del_dia(MIERCOLES, [{"ticker": "MSFT", "momento": "post"},
                                                 {"ticker": "KO", "momento": "pre"}],
                                     PreciosFalsos())
    assert texto == ("📊 *Balances del mié 28/10*\n"
                     "MSFT (post-cierre): posmercado positiva (+4,1%).\n"
                     "KO (pre-apertura): rueda negativa (−2,3%).")


def test_sin_hora_lleva_la_rueda_y_el_posmercado():
    texto = balances.resumen_del_dia(MIERCOLES, [{"ticker": "CAT", "momento": ""}], PreciosFalsos())
    assert texto.endswith("CAT (sin hora): rueda neutra (+0,9%), posmercado neutra (+0,1%).")


@pytest.mark.parametrize("cierre, palabra", [(100.94, "neutra (+0,9%)"),
                                              (100.96, "positiva (+1,0%)"),
                                              (101.0, "positiva (+1,0%)"),
                                              (99.06, "neutra (−0,9%)"),
                                              (99.0, "negativa (−1,0%)"),
                                              (100.0, "neutra (+0,0%)")])
def test_neutra_si_se_movio_menos_de_uno_por_ciento(cierre, palabra):
    precios = PreciosFalsos(cierres={"X": {date(2026, 10, 27): 100.0, MIERCOLES: cierre}})
    texto = balances.resumen_del_dia(MIERCOLES, [{"ticker": "X", "momento": "pre"}], precios)
    assert texto.endswith(f"X (pre-apertura): rueda {palabra}.")


def test_la_rueda_es_contra_el_cierre_anterior_aunque_haya_un_feriado():
    precios = PreciosFalsos(cierres={"X": {date(2026, 10, 23): 100.0, date(2026, 10, 26): 90.0,
                                           MIERCOLES: 99.0}})
    texto = balances.resumen_del_dia(MIERCOLES, [{"ticker": "X", "momento": "pre"}], precios)
    assert "rueda positiva (+10,0%)" in texto                 # contra el 26, no contra el 23


def test_lo_que_yahoo_no_da_es_sd_con_el_motivo():
    precios = PreciosFalsos(cierres={"MSFT": {MIERCOLES: 410.0},
                                     "KO": {date(2026, 10, 27): 70.0}},
                            post={"MSFT": PrecioNoDisponible("Yahoo respondió HTTP 429")})
    texto = balances.resumen_del_dia(MIERCOLES, [{"ticker": "MSFT", "momento": "post"},
                                                 {"ticker": "KO", "momento": "pre"},
                                                 {"ticker": "ZZZZ", "momento": "pre"}], precios)
    assert "MSFT (post-cierre): posmercado s/d (Yahoo respondió HTTP 429)." in texto
    assert "KO (pre-apertura): rueda s/d (Yahoo no tiene el cierre del 28/10)." in texto
    assert "ZZZZ (pre-apertura): rueda s/d (Yahoo respondió HTTP 404)." in texto


def test_sin_cierre_del_dia_no_se_pide_el_posmercado():
    precios = PreciosFalsos(cierres={"MSFT": {date(2026, 10, 27): 400.0}})
    texto = balances.resumen_del_dia(MIERCOLES, [{"ticker": "MSFT", "momento": "post"}], precios)
    assert "posmercado s/d (Yahoo no tiene el cierre del 28/10)" in texto
    assert ("post", "MSFT", MIERCOLES) not in precios.pedidos


RESUMEN_POST = {"accion": "resumen", "fecha": "2026-10-28", "tanda": "post",
                "empresas": [{"ticker": "MSFT", "momento": "post"}],
                "id": "resumen-post-2026-10-28"}


def test_el_resumen_del_dia_va_a_la_cola_aparte(entorno):
    codigo, r = _post(entorno["url"], RESUMEN_POST)
    assert codigo == 200 and r["estado"] == "en_cola"
    (fila,) = _salientes(entorno["db"])
    assert fila["tipo"] == "balances_resumen" and fila["id_origen"] == "resumen-post-2026-10-28"
    assert fila["texto"] == ("📊 *Balances del mié 28/10*\n"
                             "MSFT (post-cierre): posmercado positiva (+4,1%).")
    assert _post(entorno["url"], RESUMEN_POST)[1]["repetido"] is True
    assert len(_salientes(entorno["db"])) == 1


@pytest.mark.parametrize("datos", [
    {"accion": "resumen", "fecha": "2026-10-28", "empresas": []},
    {"accion": "resumen", "fecha": "2026-10-28", "empresas": [{"ticker": "MSFT", "momento": "x"}]},
    {"accion": "resumen", "fecha": "2026-10-28", "empresas": [{"ticker": " ", "momento": "pre"}]},
    {"accion": "resumen", "fecha": "28/10", "empresas": [{"ticker": "MSFT", "momento": "pre"}]},
])
def test_el_resumen_de_api_valida_lo_que_llega(db, datos):
    with pytest.raises(ValueError):
        api._balances(db, datos, UID)
