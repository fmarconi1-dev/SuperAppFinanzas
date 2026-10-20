"""Fotos con Gemini (Fase D, paso 6, ADR-0009 §8).

Gemini solo extrae filas: acá se reemplaza por un lector falso (la propuesta,
la validación y el emparejamiento son el código de siempre) y el cliente real
se prueba contra un Gemini de mentira en un puerto local. Nombres inventados.
"""

from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from core.api import gemini
from core.api.archivos import ArchivoRecibido
from core.api.gemini import ClienteGemini, GeminiNoDisponible
from places.finanzas.core.comandos import ZONA, procesar, procesar_archivo
from places.finanzas.core.fotos import validar
from tests.test_conciliacion import _cargar, _q, db  # noqa: F401 — el fixture `db`

UID = 1
AHORA = datetime(2026, 11, 20, 12, tzinfo=ZONA)
HOY = AHORA.date()


class LectorFalso:
    def __init__(self, filas=None, error=None):
        self.filas, self.error, self.pedidos = filas or [], error, []

    def extraer_filas(self, datos, tipo):
        self.pedidos.append((len(datos), tipo))
        if self.error:
            raise GeminiNoDisponible(self.error)
        return self.filas


def _foto(db, lector):
    return procesar_archivo(db, ArchivoRecibido(tipo="jpeg", datos=b"\xff\xd8\xff" + b"0" * 10),
                            user_id=UID, ahora=AHORA, lector_fotos=lector)


def _p(db, texto):
    return procesar(db, texto, user_id=UID, ahora=AHORA)


DOS = [{"fecha": "2026-11-18", "descripcion": "PANADERIA INVENTADA", "monto": 4500},
       {"fecha": "2026-11-19", "descripcion": "VERDULERIA INVENTADA 123", "monto": 2300.5}]


# ---------------------------------------------------------------- validar (sin Gemini)

def test_validar_descarta_lo_que_no_cierra():
    filas, malas = validar([
        {"fecha": "2026-11-18", "descripcion": "BIEN", "monto": 100},
        {"fecha": "2026-13-40", "descripcion": "FECHA ROTA", "monto": 100},
        {"fecha": "2026-12-25", "descripcion": "FUTURA", "monto": 100},
        {"fecha": "2026-11-18", "descripcion": "NEGATIVO", "monto": -5},
        {"fecha": "2026-11-18", "descripcion": "", "monto": 5},
        {"fecha": "2026-11-18", "descripcion": "TEXTO", "monto": "mil"},
        "no soy una fila",
    ], HOY)
    assert [f["descripcion"] for f in filas] == ["BIEN"] and malas == 6


def test_sin_anio_es_la_fecha_mas_cercana_hacia_atras():
    filas, _ = validar([{"fecha": "0000-12-30", "descripcion": "X", "monto": 1}], HOY)
    assert filas[0]["fecha"] == "2025-12-30"


# ---------------------------------------------------------------- la propuesta

def test_sin_gemini_pide_el_archivo(db):
    r = _foto(db, None)
    assert r.resultado == "rechazado" and "no puedo leer fotos (falta configurar Gemini)" in r.texto


def test_una_foto_propone_y_no_carga_hasta_el_ok(db):
    lector = LectorFalso(DOS)
    r = _foto(db, lector)
    assert lector.pedidos == [(13, "jpeg")]
    assert r.resultado == "pendiente"
    assert "1. 18/11 PANADERIA INVENTADA $4.500 → ¿categoría?" in r.texto
    assert "Lo leí con Gemini: revisá montos y fechas" in r.texto
    assert _q(db, "SELECT COUNT(*) FROM transacciones WHERE comentario LIKE 'Foto%'") == [(0,)]
    r = _p(db, "1 compras, 2 compras, ok")
    assert r.resultado == "lote"
    assert _q(db, "SELECT fecha, motivo, pasivos FROM transacciones WHERE comentario LIKE 'Foto%' "
                  "ORDER BY id") == [("2026-11-18", "Compras", 4500.0),
                                     ("2026-11-19", "Compras", 2300.5)]


def test_lo_que_ya_estaba_no_se_vuelve_a_cargar(db):
    _cargar(db, date(2026, 11, 18), "Compras", pasivos=4500)
    r = _foto(db, LectorFalso(DOS))
    assert "✔ 18/11 PANADERIA INVENTADA $4.500 = ya lo tenías: Compras $4.500 (18/11)" in r.texto
    assert "1. 19/11 VERDULERIA" in r.texto
    _p(db, "1 compras, ok")
    assert _q(db, "SELECT COUNT(*) FROM transacciones WHERE motivo = 'Compras'") == [(2,)]


def test_aprende_la_categoria_de_la_descripcion(db):
    _foto(db, LectorFalso(DOS[:1]))
    _p(db, "1 salidas, ok")
    _p(db, "deshacer")                 # aunque lo deshaga, en otra foto...
    r = _foto(db, LectorFalso([{**DOS[0], "fecha": "2026-11-19"}]))
    # ...deshacer también se lleva la regla aprendida: vuelve a preguntar.
    assert "¿categoría?" in r.texto


def test_la_regla_se_recuerda(db):
    _foto(db, LectorFalso(DOS[:1]))
    _p(db, "1 salidas, ok")
    r = _foto(db, LectorFalso([{"fecha": "2026-11-20", "descripcion": "PANADERIA INVENTADA 9",
                                "monto": 999}]))
    assert "PANADERIA INVENTADA 9 $999 → Salidas" in r.texto


def test_gemini_caido_se_dice(db):
    r = _foto(db, LectorFalso(error="Gemini respondió 503"))
    assert r.resultado == "error" and "No pude leer la foto: Gemini respondió 503" in r.texto


def test_una_foto_sin_movimientos(db):
    r = _foto(db, LectorFalso([]))
    assert "No encontré movimientos en la foto" in r.texto


def test_un_ingreso_en_la_foto(db):
    _foto(db, LectorFalso([{"fecha": "2026-11-18", "descripcion": "AMIGA INVENTADA",
                            "monto": 12000, "es_ingreso": True}]))
    _p(db, "1 salidas, ok")             # devolución de una salida, no un ingreso
    assert _q(db, "SELECT pasivos, ingresos FROM transacciones WHERE comentario LIKE 'Foto%'") == [
        (-12000.0, 0.0)]


# ---------------------------------------------------------------- el cliente real

@pytest.fixture()
def gemini_falso(monkeypatch):
    estado = {"respuesta": None, "codigo": 200, "pedidos": []}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):  # noqa: N802
            largo = int(self.headers.get("Content-Length") or 0)
            estado["pedidos"].append((self.path, self.headers.get("x-goog-api-key"),
                                      json.loads(self.rfile.read(largo))))
            cuerpo = json.dumps(estado["respuesta"]).encode()
            self.send_response(estado["codigo"])
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(gemini, "BASE", f"http://127.0.0.1:{srv.server_address[1]}/models")
    yield estado
    srv.shutdown()
    srv.server_close()


def test_el_cliente_pide_json_y_devuelve_las_filas(gemini_falso):
    gemini_falso["respuesta"] = {"candidates": [{"content": {"parts": [
        {"text": json.dumps({"filas": DOS})}]}}]}
    filas = ClienteGemini("clave-de-prueba").extraer_filas(b"\xff\xd8\xff", "jpeg")
    assert filas == DOS
    ruta, clave, cuerpo = gemini_falso["pedidos"][0]
    assert ruta == "/models/gemini-3.5-flash-lite:generateContent"
    assert clave == "clave-de-prueba"                      # en la cabecera, no en la URL
    assert cuerpo["generationConfig"]["responseMimeType"] == "application/json"
    assert cuerpo["contents"][0]["parts"][0]["inline_data"]["mime_type"] == "image/jpeg"


def test_el_cliente_nombra_el_error(gemini_falso):
    gemini_falso["codigo"], gemini_falso["respuesta"] = 429, {"error": {}}
    with pytest.raises(GeminiNoDisponible, match="429"):
        ClienteGemini("k").extraer_filas(b"x", "png")


def test_una_respuesta_bloqueada_no_es_una_foto_vacia(gemini_falso):
    gemini_falso["respuesta"] = {"promptFeedback": {"blockReason": "SAFETY"}}
    with pytest.raises(GeminiNoDisponible, match="SAFETY"):
        ClienteGemini("k").extraer_filas(b"x", "png")


def test_sin_clave_no_hay_cliente(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ClienteGemini.desde_entorno() is None
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODELO", "otro-modelo")
    assert ClienteGemini.desde_entorno() == ClienteGemini("k", "otro-modelo")
