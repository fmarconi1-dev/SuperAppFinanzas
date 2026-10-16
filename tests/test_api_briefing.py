"""Briefings de Gemini por WhatsApp (Fase B, ADR-0008): armado y cola de salida.

Lo que el bot manda por su cuenta solo es gratis dentro de la ventana de 24 h
desde el último mensaje de Franco. Estos tests fijan las dos ramas (sale ya /
queda en cola), la entrega de lo pendiente cuando Franco escribe, el dedupe
por id del mail y la autenticación del endpoint. Servidor real en un puerto
libre; solo el envío a Meta es falso.
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
from core.api import whatsapp_meta as wa
from core.api.servidor import AVISO_PENDIENTES, ZONA, crear_servidor
from core.context import set_current_workspace_id
from core.db import connect, init_db
from places.finanzas.core import briefing
from places.finanzas.core.transactions import insert_transaction
from tests.test_api_whatsapp import CFG, NUMERO, _payload, _post

TOKEN = "token-de-la-api"
HOY = date(2026, 10, 16)


def _base(tmp_path, monkeypatch):
    db_path = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(db_path)
    conn = connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) VALUES (1, 'franco', 'Franco')")
    conn.execute("UPDATE usuarios SET username = 'franco' WHERE id = 1")
    set_current_workspace_id(None)
    return db_path, conn


# ------------------------------------------------------------------ armado

@pytest.fixture()
def db(tmp_path, monkeypatch):
    _, conn = _base(tmp_path, monkeypatch)
    for motivo, grupo, monto in [("Supermercado", "Gasto Variable", 10000),
                                 ("Sueldo", "Ingreso", 0)]:
        insert_transaction(conn, fecha=HOY, motivo=motivo, pasivos=monto,
                           ingresos=300000 if motivo == "Sueldo" else 0, user_id=1)
        conn.execute("UPDATE categorias SET grupo = ? WHERE motivo = ?", (grupo, motivo))
    yield conn
    set_current_workspace_id(None)
    conn.close()


def test_el_briefing_sale_tal_cual_sin_finanzas(db):
    """Franco, 16/10/2026: "El briefing es una cosa, mis finanzas son otra"."""
    final = briefing.componer(db, "Buen día.\r\nAgenda: nada.\n", "briefing", user_id=1, hoy=HOY)
    assert final == "Buen día.\nAgenda: nada."
    assert "FINANZAS" not in final and "$" not in final


def test_el_cierre_sale_tal_cual(db):
    texto = "*📈 CIERRE 16/10*\nS&P 500 7.744 (+0,4%)"
    assert briefing.componer(db, texto, "cierre", user_id=1, hoy=HOY) == texto


def test_tipo_desconocido_o_texto_vacio(db):
    with pytest.raises(ValueError, match="tipo"):
        briefing.componer(db, "hola", "otro", user_id=1, hoy=HOY)
    with pytest.raises(ValueError, match="vacío"):
        briefing.componer(db, "   ", "briefing", user_id=1, hoy=HOY)


# ------------------------------------------------------------------ servidor real

@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    db_path, conn = _base(tmp_path, monkeypatch)
    insert_transaction(conn, fecha=date(2026, 9, 1), motivo="Nafta", pasivos=1, user_id=1)
    conn.execute("DELETE FROM transacciones")
    conn.close()

    enviados: list[tuple[str, str]] = []
    estado = {"token": TOKEN, "falla": None}

    def enviar(cfg, numero, texto):
        if estado["falla"]:
            raise wa.CanalNoDisponible("ventana cerrada", estado["falla"])
        enviados.append((numero, texto))
        return ["w"]

    srv = crear_servidor(
        "127.0.0.1", 0,
        procesar=api._procesar,
        componer=api._componer,
        enviar=enviar,
        cargar_config=lambda: CFG,
        cargar_token_api=lambda: estado["token"],
        db_path=db_path,
    )
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    yield {"srv": srv, "url": f"http://127.0.0.1:{srv.server_address[1]}", "db": db_path,
           "enviados": enviados, "estado": estado}
    srv.shutdown()
    srv.server_close()
    set_current_workspace_id(None)


def _briefing(url, cuerpo, token=TOKEN):
    datos = json.dumps(cuerpo).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    pedido = urllib.request.Request(url + "/api/briefing", data=datos, headers=headers,
                                    method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _ultimo_entrante(db_path, hace: timedelta):
    cuando = (datetime.now(ZONA) - hace).isoformat()
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO whatsapp_estado (clave, valor, actualizado_en) VALUES "
            "('ultimo_entrante', ?, ?) ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (cuando, cuando))
    finally:
        conn.close()


def _salientes(db_path):
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT tipo, enviado_en IS NOT NULL AS enviado, error FROM whatsapp_salientes "
            "ORDER BY id")]
    finally:
        conn.close()


def test_con_la_ventana_abierta_sale_en_el_momento(entorno):
    _ultimo_entrante(entorno["db"], timedelta(hours=2))
    codigo, r = _briefing(entorno["url"], {"texto": "Buen día", "tipo": "briefing", "id": "m1"})
    assert codigo == 200 and r["ok"] is True and r["estado"] == "enviado"
    (numero, texto), = entorno["enviados"]
    assert numero == NUMERO and texto == "Buen día"


def test_el_cierre_sale_tal_cual(entorno):
    _ultimo_entrante(entorno["db"], timedelta(minutes=5))
    _briefing(entorno["url"], {"texto": "*📈 CIERRE*", "tipo": "cierre"})
    assert entorno["enviados"] == [(NUMERO, "*📈 CIERRE*")]


@pytest.mark.parametrize("hace", [None, timedelta(hours=25), timedelta(hours=23, minutes=55)])
def test_con_la_ventana_cerrada_queda_en_cola_y_no_se_manda(entorno, hace):
    if hace is not None:
        _ultimo_entrante(entorno["db"], hace)
    codigo, r = _briefing(entorno["url"], {"texto": "Buen día", "tipo": "briefing"})
    assert codigo == 200 and r["ok"] is True and r["estado"] == "en_cola"
    assert entorno["enviados"] == []
    assert _salientes(entorno["db"]) == [{"tipo": "briefing", "enviado": 0, "error": None}]


def test_lo_pendiente_sale_cuando_franco_escribe_antes_de_la_respuesta(entorno):
    _briefing(entorno["url"], {"texto": "Buen día", "tipo": "briefing", "id": "m1"})
    _briefing(entorno["url"], {"texto": "*📈 CIERRE*", "tipo": "cierre", "id": "m2"})
    assert entorno["enviados"] == []

    _post(entorno["url"], _payload([("w1", NUMERO, "ayuda")]))
    entorno["srv"].cola.join()

    textos = [t for _, t in entorno["enviados"]]
    assert len(textos) == 3
    assert textos[0].startswith(AVISO_PENDIENTES + "\n\nBuen día")      # aviso solo en el primero
    assert textos[1] == "*📈 CIERRE*"
    assert "Cómo cargar" in textos[2]                                     # recién ahí, la respuesta
    assert all(s["enviado"] for s in _salientes(entorno["db"]))


def test_el_mismo_mail_dos_veces_sale_una_sola(entorno):
    _ultimo_entrante(entorno["db"], timedelta(hours=1))
    _briefing(entorno["url"], {"texto": "Buen día", "id": "mail-123"})
    codigo, r = _briefing(entorno["url"], {"texto": "Buen día", "id": "mail-123"})
    assert codigo == 200 and r["repetido"] is True and r["estado"] == "enviado"
    assert len(entorno["enviados"]) == 1


def test_si_meta_rechaza_queda_en_cola_con_el_error_y_sale_despues(entorno):
    _ultimo_entrante(entorno["db"], timedelta(hours=1))
    entorno["estado"]["falla"] = 131047
    codigo, r = _briefing(entorno["url"], {"texto": "Buen día", "id": "m1"})
    assert codigo == 200 and r["estado"] == "en_cola"
    assert "131047" in _salientes(entorno["db"])[0]["error"]

    entorno["estado"]["falla"] = None
    _post(entorno["url"], _payload([("w1", NUMERO, "ayuda")]))
    entorno["srv"].cola.join()
    assert entorno["enviados"][0][1].startswith(AVISO_PENDIENTES)
    assert _salientes(entorno["db"]) == [{"tipo": "briefing", "enviado": 1, "error": None}]


def test_sin_tipo_es_briefing(entorno):
    _ultimo_entrante(entorno["db"], timedelta(hours=1))
    _briefing(entorno["url"], {"texto": "Buen día"})
    codigo, r = _briefing(entorno["url"], {"texto": "Otro"})
    assert codigo == 200 and r["ok"] is True
    assert [t for _, t in entorno["enviados"]] == ["Buen día", "Otro"]


@pytest.mark.parametrize("token, esperado", [(None, 401), ("otro", 401)])
def test_sin_token_o_token_malo_no_entra(entorno, token, esperado):
    codigo, r = _briefing(entorno["url"], {"texto": "Buen día"}, token=token)
    assert codigo == esperado and r["ok"] is False
    assert _salientes(entorno["db"]) == []


def test_sin_token_configurado_responde_503(entorno):
    entorno["estado"]["token"] = None
    codigo, r = _briefing(entorno["url"], {"texto": "Buen día"})
    assert codigo == 503 and r["error"] == "sin_configurar"


@pytest.mark.parametrize("cuerpo", [{"tipo": "briefing"}, {"texto": 5}, {"texto": "x", "tipo": "otro"},
                                    {"texto": "  "}])
def test_cuerpos_invalidos_responden_400(entorno, cuerpo):
    codigo, r = _briefing(entorno["url"], cuerpo)
    assert codigo == 400 and r["ok"] is False
    assert _salientes(entorno["db"]) == []
