"""API de WhatsApp (Fase A, ADR-0008): canal de Meta y servidor HTTP real.

El servidor se levanta de verdad en un puerto libre y se le pega por HTTP
con webhooks firmados como los firma Meta. Lo único falso es el envío a Meta
(`enviar`), que captura lo que se habría mandado.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pytest

import api
import core.db as core_db
from core.api import whatsapp_meta as wa
from core.api.servidor import crear_servidor
from core.context import set_current_workspace_id
from core.db import connect, init_db
from places.finanzas.core.transactions import insert_transaction

RAIZ = Path(__file__).resolve().parents[1]
SECRETO = "secreto-de-la-app"
NUMERO = "5491100001111"  # celular argentino: en WhatsApp lleva el 9

CFG = wa.ConfigWhatsApp(
    token="tok", phone_number_id="123", app_secret=SECRETO, verify_token="verif",
    numero_autorizado=NUMERO, usuario="franco",
)


# ------------------------------------------------------------------ canal

def test_canonico_saca_el_9_de_los_celulares_argentinos():
    assert wa.canonico("+54 9 11 0000-1111") == "541100001111"
    assert wa.canonico("541100001111") == "541100001111"
    assert wa.canonico("59899123456") == "59899123456"


def test_el_remitente_autorizado_se_reconoce_con_o_sin_el_9():
    assert wa.canonico("5491100001111") == wa.canonico("541100001111")


def test_firma():
    cuerpo = b'{"a":1}'
    buena = "sha256=" + hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()
    assert wa.firma_valida(cuerpo, buena, SECRETO)
    assert not wa.firma_valida(cuerpo + b" ", buena, SECRETO)
    assert not wa.firma_valida(cuerpo, None, SECRETO)
    assert not wa.firma_valida(cuerpo, "sha1=abc", SECRETO)


def test_verificar_suscripcion():
    ok = {"hub.mode": "subscribe", "hub.verify_token": "verif", "hub.challenge": "123"}
    assert wa.verificar_suscripcion(ok, "verif") == "123"
    assert wa.verificar_suscripcion({**ok, "hub.verify_token": "otro"}, "verif") is None
    assert wa.verificar_suscripcion({**ok, "hub.mode": "x"}, "verif") is None


def test_extraer_eventos():
    payload = _payload([("w1", NUMERO, "hola")])
    payload["entry"][0]["changes"][0]["value"]["statuses"] = [
        {"status": "delivered"},
        {"status": "failed", "errors": [{"code": 131047, "title": "Re-engagement"}]},
    ]
    mensajes, fallidos = wa.extraer_eventos(payload)
    assert mensajes == [wa.MensajeEntrante("w1", NUMERO, "text", "hola")]
    assert [f["errors"][0]["code"] for f in fallidos] == [131047]


def test_partir_texto():
    assert wa.partir_texto("corto") == ["corto"]
    largo = "\n\n".join(["a" * 3000, "b" * 3000, "c" * 100])
    partes = wa.partir_texto(largo)
    assert all(len(p) <= wa.LIMITE_TEXTO for p in partes)
    assert "".join(partes).replace("\n", "") == largo.replace("\n", "")
    gigante = wa.partir_texto("x" * 9000)
    assert [len(p) for p in gigante] == [4096, 4096, 808]


def test_config_sin_variables_no_inventa_defaults(monkeypatch):
    for var in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_APP_SECRET",
                "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_NUMERO_AUTORIZADO",
                "SUPERAPP_DEFAULT_USER", "SUPERAPP_DEFAULT_WORKSPACE"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(wa.ConfigIncompleta) as e:
        wa.ConfigWhatsApp.desde_entorno()
    assert "WHATSAPP_TOKEN" in e.value.faltantes and "SUPERAPP_DEFAULT_USER" in e.value.faltantes


def test_enviar_a_un_celular_argentino_va_sin_el_9(monkeypatch):
    """Producción, 15/10/2026: el `from` llega como 549…, pero mandar a 549…
    da 131030; Meta acepta y entrega 54… (con la lista del panel CON el 9)."""
    llamados = []
    monkeypatch.setattr(wa, "_post_mensaje",
                        lambda cfg, numero, cuerpo: llamados.append(numero) or {"messages": [{"id": "w"}]})
    assert wa.enviar_texto(CFG, "+54 9 11 0000-1111", "hola") == ["w"]
    assert llamados == ["541100001111"]


def test_enviar_reintenta_con_el_9_ante_un_131030(monkeypatch):
    llamados = []

    def falso(cfg, numero, cuerpo):
        llamados.append(numero)
        if numero == "541100001111":
            raise wa.CanalNoDisponible("no en la lista", wa.NO_AUTORIZADO)
        return {"messages": [{"id": "w"}]}

    monkeypatch.setattr(wa, "_post_mensaje", falso)
    assert wa.enviar_texto(CFG, NUMERO, "hola") == ["w"]
    assert llamados == ["541100001111", "5491100001111"]


def test_si_ningun_formato_sirve_dice_que_revisar(monkeypatch):
    llamados = []

    def falso(cfg, numero, cuerpo):
        llamados.append(numero)
        raise wa.CanalNoDisponible("no en la lista", wa.NO_AUTORIZADO)

    monkeypatch.setattr(wa, "_post_mensaje", falso)
    with pytest.raises(wa.CanalNoDisponible, match="CON el 9"):
        wa.enviar_texto(CFG, NUMERO, "hola")
    assert llamados == ["541100001111", "5491100001111"]


def test_un_numero_no_argentino_se_manda_tal_cual(monkeypatch):
    llamados = []
    monkeypatch.setattr(wa, "_post_mensaje",
                        lambda cfg, numero, cuerpo: llamados.append(numero) or {"messages": [{"id": "w"}]})
    wa.enviar_texto(CFG, "59899123456", "hola")
    assert llamados == ["59899123456"]


def test_enviar_no_traga_otros_errores(monkeypatch):
    def falso(cfg, numero, cuerpo):
        raise wa.CanalNoDisponible("ventana cerrada", 131047)

    monkeypatch.setattr(wa, "_post_mensaje", falso)
    with pytest.raises(wa.CanalNoDisponible) as e:
        wa.enviar_texto(CFG, NUMERO, "hola")
    assert e.value.codigo == 131047


#: Todo lo que arma o manda mensajes del Secretario. Desde la Fase D se
#: recorren las carpetas enteras (antes era una lista fija): un módulo nuevo
#: del canal queda vigilado sin que nadie se acuerde de sumarlo.
_ARCHIVOS_DEL_CANAL = sorted(
    str(p.relative_to(RAIZ)).replace("\\", "/")
    for carpeta in ("core/api", "places/finanzas/core")
    for p in (RAIZ / carpeta).glob("*.py")
) + ["api.py"]


def test_la_lista_del_canal_incluye_lo_conocido():
    for archivo in ("core/api/whatsapp_meta.py", "core/api/servidor.py",
                    "places/finanzas/core/comandos.py", "places/finanzas/core/lotes.py"):
        assert archivo in _ARCHIVOS_DEL_CANAL


@pytest.mark.parametrize("archivo", _ARCHIVOS_DEL_CANAL)
def test_costo_cero_el_codigo_no_sabe_mandar_plantillas(archivo):
    """Candado 2 de ADR-0008: lo único que Meta cobra son las plantillas."""
    assert "template" not in (RAIZ / archivo).read_text(encoding="utf-8").lower()


# ------------------------------------------------------------------ servidor real

@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    db_path = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(db_path)
    conn = connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) VALUES (1, 'franco', 'Franco')"
    )
    # init_db ya pudo crear el usuario 1 como 'local': el webhook lo busca por nombre.
    conn.execute("UPDATE usuarios SET username = 'franco' WHERE id = 1")
    set_current_workspace_id(None)
    insert_transaction(conn, fecha=date(2026, 9, 1), motivo="Nafta", pasivos=1, user_id=1)
    conn.execute("DELETE FROM transacciones")
    conn.close()

    enviados: list[tuple[str, str]] = []
    estado = {"cfg": CFG, "procesar": api._procesar, "descargar": _sin_descargas}

    def cargar_config():
        if estado["cfg"] is None:
            raise wa.ConfigIncompleta(["WHATSAPP_TOKEN"])
        return estado["cfg"]

    srv = crear_servidor(
        "127.0.0.1", 0,
        procesar=lambda c, t, u, w: estado["procesar"](c, t, u, w),
        enviar=lambda cfg, numero, texto: enviados.append((numero, texto)) or ["w"],
        cargar_config=cargar_config,
        db_path=db_path,
        procesar_archivo=api._procesar_archivo,
        descargar=lambda cfg, media_id: estado["descargar"](cfg, media_id),
    )
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    yield {"srv": srv, "url": f"http://127.0.0.1:{srv.server_address[1]}",
           "db": db_path, "enviados": enviados, "estado": estado}
    srv.shutdown()
    srv.server_close()
    set_current_workspace_id(None)


def _sin_descargas(cfg, media_id):
    raise AssertionError("este test no esperaba bajar archivos")


def _payload(mensajes, tipo="text"):
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "messages": [
            {"id": wamid, "from": de, "type": tipo,
             **({"text": {"body": texto}} if tipo == "text" else {})}
            for wamid, de, texto in mensajes
        ]}}]}]}


def _post(url, payload, firma=True, secreto=SECRETO):
    cuerpo = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if firma:
        headers["X-Hub-Signature-256"] = "sha256=" + hmac.new(
            secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    pedido = urllib.request.Request(url + "/api/whatsapp", data=cuerpo, headers=headers,
                                    method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def _filas(db_path, sql):
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def test_health_y_privacidad(entorno):
    assert _get(entorno["url"] + "/api/health") == (200, '{"ok": true}')
    codigo, html = _get(entorno["url"] + "/api/privacidad")
    assert codigo == 200 and "Política de privacidad" in html


def test_verificacion_de_meta(entorno):
    url = entorno["url"] + "/api/whatsapp?hub.mode=subscribe&hub.verify_token=verif&hub.challenge=42"
    assert _get(url) == (200, "42")
    assert _get(url.replace("verif", "mal"))[0] == 403


def test_gasto_de_punta_a_punta(entorno):
    assert _post(entorno["url"], _payload([("w1", NUMERO, "2500, nafta")])) == 200
    entorno["srv"].cola.join()
    txns = _filas(entorno["db"], "SELECT id, motivo, pasivos FROM transacciones")
    assert len(txns) == 1 and txns[0]["motivo"] == "Nafta" and txns[0]["pasivos"] == 2500.0
    # El servidor le pasa al canal el `from` tal como vino; el formato de
    # envío (en AR, sin el 9) lo resuelve `enviar_texto` (tests de arriba).
    numero, texto = entorno["enviados"][0]
    assert numero == NUMERO and "✅ Cargado" in texto
    msg = _filas(entorno["db"], "SELECT resultado, transaccion_id FROM whatsapp_mensajes")
    assert msg == [{"resultado": "cargado", "transaccion_id": txns[0]["id"]}]
    estado = _filas(entorno["db"], "SELECT clave FROM whatsapp_estado")
    assert {"clave": "ultimo_entrante"} in estado


def test_deshacer_de_punta_a_punta(entorno):
    _post(entorno["url"], _payload([("w1", NUMERO, "2500, nafta")]))
    entorno["srv"].cola.join()
    (txn,) = _filas(entorno["db"], "SELECT id FROM transacciones")
    _post(entorno["url"], _payload([("w2", NUMERO, "deshacer")]))
    entorno["srv"].cola.join()
    assert _filas(entorno["db"], "SELECT id FROM transacciones") == []
    assert f"Borré #{txn['id']}" in entorno["enviados"][1][1]


def test_varios_gastos_ok_y_deshacer_de_punta_a_punta(entorno):
    """Fase D, paso 2, por el servidor real: el hilo trabajador arranca sin
    contextvars, así que el lote tiene que encontrar el espacio solo."""
    url, srv = entorno["url"], entorno["srv"]
    _post(url, _payload([("w1", NUMERO, "2500, nafta\n4.000, nafta, peaje\n100-50, nafta")]))
    srv.cola.join()
    assert _filas(entorno["db"], "SELECT id FROM transacciones") == []
    assert "Te cargo 3" in entorno["enviados"][-1][1]

    _post(url, _payload([("w2", NUMERO, "ok")]))
    srv.cola.join()
    txns = _filas(entorno["db"], "SELECT pasivos FROM transacciones ORDER BY id")
    assert [t["pasivos"] for t in txns] == [2500.0, 4000.0, 50.0]
    assert _filas(entorno["db"], "SELECT cuenta, bruto FROM gasto_cuentas") == [
        {"cuenta": "100-50", "bruto": 100.0}]
    assert "Cargados 3" in entorno["enviados"][-1][1]

    _post(url, _payload([("w3", NUMERO, "deshacer")]))
    srv.cola.join()
    assert _filas(entorno["db"], "SELECT id FROM transacciones") == []
    assert _filas(entorno["db"], "SELECT * FROM gasto_cuentas") == []
    assert "Borré los 3" in entorno["enviados"][-1][1]


def test_firma_invalida_no_procesa(entorno):
    assert _post(entorno["url"], _payload([("w1", NUMERO, "2500, nafta")]), firma=False) == 401
    assert _post(entorno["url"], _payload([("w1", NUMERO, "2500, nafta")]), secreto="otro") == 401
    assert _filas(entorno["db"], "SELECT * FROM whatsapp_mensajes") == []


def test_numero_no_autorizado_se_ignora(entorno, caplog):
    with caplog.at_level(logging.WARNING, logger="superapp.api"):
        assert _post(entorno["url"], _payload([("w1", "5491199998888", "2500, nafta")])) == 200
    entorno["srv"].cola.join()
    assert _filas(entorno["db"], "SELECT * FROM whatsapp_mensajes") == []
    assert entorno["enviados"] == []
    assert "no autorizado" in caplog.text and "99998888" not in caplog.text


def test_reintento_de_meta_no_duplica(entorno):
    p = _payload([("w1", NUMERO, "2500, nafta")])
    assert _post(entorno["url"], p) == 200
    assert _post(entorno["url"], p) == 200
    entorno["srv"].cola.join()
    assert len(_filas(entorno["db"], "SELECT id FROM transacciones")) == 1
    assert len(entorno["enviados"]) == 1


def test_mensaje_que_no_es_texto(entorno):
    _post(entorno["url"], _payload([("w1", NUMERO, None)], tipo="audio"))
    entorno["srv"].cola.join()
    assert "entiendo texto, archivos" in entorno["enviados"][0][1]
    assert _filas(entorno["db"], "SELECT resultado FROM whatsapp_mensajes") == [
        {"resultado": "ignorado"}]


def test_sin_configuracion_responde_503(entorno):
    entorno["estado"]["cfg"] = None
    assert _post(entorno["url"], _payload([("w1", NUMERO, "2500, nafta")])) == 503
    assert _get(entorno["url"] + "/api/health")[0] == 200


def test_usuario_inexistente_responde_503(entorno):
    entorno["estado"]["cfg"] = wa.ConfigWhatsApp(**{**CFG.__dict__, "usuario": "nadie"})
    assert _post(entorno["url"], _payload([("w1", NUMERO, "2500, nafta")])) == 503


def test_un_fallo_al_procesar_queda_registrado_y_se_avisa(entorno, caplog):
    def explota(conn, texto, uid, wamid):
        raise RuntimeError("bug")

    entorno["estado"]["procesar"] = explota
    with caplog.at_level(logging.ERROR, logger="superapp.api"):
        _post(entorno["url"], _payload([("w1", NUMERO, "2500, nafta")]))
        entorno["srv"].cola.join()
    assert _filas(entorno["db"], "SELECT resultado FROM whatsapp_mensajes") == [
        {"resultado": "error"}]
    assert "Algo falló" in entorno["enviados"][0][1]
    assert "RuntimeError: bug" in caplog.text


def test_envio_fallido_que_informa_meta_queda_en_el_log(entorno, caplog):
    payload = {"entry": [{"changes": [{"value": {"statuses": [
        {"status": "failed", "errors": [{"code": 131042, "title": "Business eligibility payment issue"}]},
    ]}}]}]}
    with caplog.at_level(logging.ERROR, logger="superapp.api"):
        assert _post(entorno["url"], payload) == 200
    assert "131042" in caplog.text


def test_ruta_inexistente(entorno):
    assert _get(entorno["url"] + "/api/nada")[0] == 404


# ------------------------------------------------------------------ archivos (Fase D, paso 3)

def _payload_archivo(wamid, tipo, media_id="m1", nombre=None, pie=None,
                     mime="application/octet-stream"):
    datos = {"id": media_id, "mime_type": mime}
    if nombre:
        datos["filename"] = nombre
    if pie:
        datos["caption"] = pie
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "messages": [{"id": wamid, "from": NUMERO, "type": tipo, tipo: datos}]}}]}]}


def _xlsx() -> bytes:
    import io
    import openpyxl
    libro = openpyxl.Workbook()
    libro.active["A1"] = "Fecha"
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _archivos_en(carpeta):
    return sorted(str(p.relative_to(carpeta)) for p in carpeta.rglob("*") if p.is_file()
                  and "backups" not in p.parts)


def test_el_extracto_por_whatsapp_de_punta_a_punta(entorno, tmp_path):
    """Fase D, paso 4, por el servidor real: el extracto llega como documento, se
    propone, `ok` lo aplica, y el archivo nunca toca el disco."""
    from tests.test_extracto_galicia import armar_extracto

    pedidos = []
    extracto = armar_extracto([
        ("16/10/2026", "COMPRA DEBITO\nKIOSCO INVENTADO\n4517XXXX\nA1", -100),
        ("20/10/2026", "COMPRA DEBITO\nFERRETERIA INVENTADA\n4517XXXX\nA1", -2500),
    ])
    entorno["estado"]["descargar"] = lambda cfg, mid: pedidos.append(mid) or extracto
    antes = _archivos_en(tmp_path)
    _post(entorno["url"], _payload_archivo("w1", "document", "media-9",
                                           nombre="galicia.xlsx", pie="octubre"))
    entorno["srv"].cola.join()
    assert pedidos == ["media-9"]
    texto = entorno["enviados"][-1][1]
    assert "Punto de partida" in texto and "FERRETERIA INVENTADA $2.500 → ¿categoría?" in texto
    assert _filas(entorno["db"], "SELECT texto, resultado FROM whatsapp_mensajes") == [
        {"texto": "[document] galicia.xlsx · octubre", "resultado": "pendiente"}]
    assert _filas(entorno["db"], "SELECT id FROM transacciones") == []

    _post(entorno["url"], _payload([("w2", NUMERO, "1 nafta, ok")]))
    entorno["srv"].cola.join()
    assert "✅ Listo: cargué 1" in entorno["enviados"][-1][1]
    assert _filas(entorno["db"], "SELECT motivo, pasivos FROM transacciones") == [
        {"motivo": "Nafta", "pasivos": 2500.0}]
    # Nada nuevo en disco más allá de la base (el archivo vivió en memoria).
    nuevos = set(_archivos_en(tmp_path)) - set(antes)
    assert all(n.startswith("finanzas.db") for n in nuevos), nuevos


def test_un_excel_que_no_es_el_extracto(entorno):
    entorno["estado"]["descargar"] = lambda cfg, mid: _xlsx()
    _post(entorno["url"], _payload_archivo("w1", "document", nombre="planilla.xlsx"))
    entorno["srv"].cola.join()
    assert "No pude leer el extracto: No encontré movimientos" in entorno["enviados"][-1][1]


def test_una_foto_se_reconoce_por_el_contenido(entorno, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)   # sin Gemini: se reconoce y se dice
    entorno["estado"]["descargar"] = lambda cfg, mid: b"\xff\xd8\xff\xe0" + b"0" * 2000
    _post(entorno["url"], _payload_archivo("w1", "image"))
    entorno["srv"].cola.join()
    assert "Recibí una foto (2 KB), pero no puedo leer fotos" in entorno["enviados"][-1][1]


def test_un_pdf_que_no_es_un_resumen(entorno):
    """Un PDF roto (o que no es un resumen de Galicia) se contesta, no rompe el hilo."""
    entorno["estado"]["descargar"] = lambda cfg, mid: b"%PDF-1.7\n..."
    _post(entorno["url"], _payload_archivo("w1", "document", nombre="RESUMEN.pdf"))
    entorno["srv"].cola.join()
    assert "No pude leer el resumen: No pude abrir el PDF" in entorno["enviados"][-1][1]


def test_un_archivo_que_no_es_excel_pdf_ni_foto(entorno):
    entorno["estado"]["descargar"] = lambda cfg, mid: b"hola, soy un .txt"
    _post(entorno["url"], _payload_archivo("w1", "document", nombre="notas.xlsx"))
    entorno["srv"].cola.join()
    assert "No sé leer ese archivo" in entorno["enviados"][-1][1]
    assert _filas(entorno["db"], "SELECT resultado FROM whatsapp_mensajes") == [
        {"resultado": "rechazado"}]


def test_un_pdf_que_no_llego_como_pdf_es_una_descarga_rota(entorno):
    """Meta dice PDF y llegan bytes que no lo son: "no contestó" ≠ "no sé leerlo"."""
    entorno["estado"]["descargar"] = lambda cfg, mid: b"\x00\x01 cortado"
    _post(entorno["url"], _payload_archivo("w1", "document", nombre="RESUMEN.pdf",
                                           mime="application/pdf"))
    entorno["srv"].cola.join()
    texto = entorno["enviados"][-1][1]
    assert "No pude bajar bien el archivo" in texto and "No sé leer" not in texto
    assert _filas(entorno["db"], "SELECT resultado FROM whatsapp_mensajes") == [
        {"resultado": "error"}]


def test_si_meta_no_da_el_archivo_se_avisa(entorno):
    def falla(cfg, mid):
        raise wa.ArchivoNoDisponible("Meta no me dio el archivo (HTTP 404)")

    entorno["estado"]["descargar"] = falla
    _post(entorno["url"], _payload_archivo("w1", "document"))
    entorno["srv"].cola.join()
    texto = entorno["enviados"][-1][1]
    assert "No pude bajar el archivo: Meta no me dio el archivo (HTTP 404)" in texto
    assert "Mandalo de nuevo" in texto
    assert _filas(entorno["db"], "SELECT resultado FROM whatsapp_mensajes") == [
        {"resultado": "error"}]


def test_un_archivo_no_se_mete_en_la_propuesta_ni_carga_nada(entorno):
    entorno["estado"]["descargar"] = lambda cfg, mid: _xlsx()
    _post(entorno["url"], _payload_archivo("w1", "document"))
    entorno["srv"].cola.join()
    assert _filas(entorno["db"], "SELECT id FROM transacciones") == []

