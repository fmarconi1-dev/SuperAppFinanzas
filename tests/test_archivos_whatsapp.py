"""Recibir archivos por WhatsApp (Fase D, paso 3, ADR-0009 §7).

El webhook reconoce documentos y fotos, el archivo se baja de la Graph API en
dos pasos (id → URL → contenido) contra un **Meta de mentira** en un puerto
local, y el tipo se decide por el contenido, no por el nombre. El que llega
de punta a punta por el servidor real está en `test_api_whatsapp.py`.
"""

from __future__ import annotations

import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import openpyxl
import pytest

from core.api import whatsapp_meta as wa
from core.api.archivos import ArchivoRecibido, tamanio_legible, tipo_de_contenido

CFG = wa.ConfigWhatsApp(
    token="tok", phone_number_id="123", app_secret="s", verify_token="v",
    numero_autorizado="5491100001111", usuario="franco",
)


def _xlsx() -> bytes:
    libro = openpyxl.Workbook()
    libro.active["A1"] = "Fecha"
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


# ---------------------------------------------------------------- webhook

def test_el_webhook_reconoce_un_documento():
    payload = {"entry": [{"changes": [{"value": {"messages": [{
        "id": "w1", "from": "5491100001111", "type": "document",
        "document": {"id": "m9", "mime_type": "application/pdf",
                     "filename": "RESUMEN.pdf", "caption": "amex"}}]}}]}]}
    (m,), _ = wa.extraer_eventos(payload)
    assert m.tipo == "document" and m.texto is None
    assert m.archivo == wa.ArchivoEntrante("m9", "application/pdf", "RESUMEN.pdf", "amex")


def test_el_webhook_reconoce_una_foto_sin_nombre():
    payload = {"entry": [{"changes": [{"value": {"messages": [{
        "id": "w1", "from": "5491100001111", "type": "image",
        "image": {"id": "m3", "mime_type": "image/jpeg"}}]}}]}]}
    (m,), _ = wa.extraer_eventos(payload)
    assert m.archivo == wa.ArchivoEntrante("m3", "image/jpeg", None, None)


def test_un_audio_no_trae_archivo():
    payload = {"entry": [{"changes": [{"value": {"messages": [{
        "id": "w1", "from": "5491100001111", "type": "audio", "audio": {"id": "m4"}}]}}]}]}
    (m,), _ = wa.extraer_eventos(payload)
    assert m.archivo is None


def test_un_texto_sigue_igual():
    payload = {"entry": [{"changes": [{"value": {"messages": [{
        "id": "w1", "from": "5491100001111", "type": "text", "text": {"body": "hola"}}]}}]}]}
    (m,), _ = wa.extraer_eventos(payload)
    assert (m.texto, m.archivo) == ("hola", None)


# ---------------------------------------------------------------- qué es

def test_un_excel_se_reconoce_por_dentro():
    assert tipo_de_contenido(_xlsx()) == "xlsx"


def test_un_zip_cualquiera_no_es_un_excel():
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        z.writestr("hola.txt", "hola")
    assert tipo_de_contenido(salida.getvalue()) is None


@pytest.mark.parametrize("datos, tipo", [
    (b"%PDF-1.7\n%...", "pdf"),
    (b"\xff\xd8\xff\xe0\x00\x10JFIF", "jpeg"),
    (b"\x89PNG\r\n\x1a\n\x00\x00", "png"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"),
    (b"PK\x03\x04 roto", None),
    (b"\xd0\xcf\x11\xe0", None),   # un .xls viejo: no se acepta
    (b"Fecha;Monto\n", None),      # un CSV
    (b"", None),
])
def test_el_tipo_sale_de_los_primeros_bytes(datos, tipo):
    assert tipo_de_contenido(datos) == tipo


def test_describir_dice_que_llego():
    a = ArchivoRecibido(tipo="xlsx", datos=b"x" * 46_000, nombre="galicia.xlsx")
    assert a.describir() == "un Excel (galicia.xlsx, 45 KB)"
    assert ArchivoRecibido(tipo="png", datos=b"x" * 10).describir() == "una foto (10 B)"
    assert tamanio_legible(3 * 1024 * 1024 + 200_000) == "3,2 MB"


# ---------------------------------------------------------------- bajarlo de Meta

@pytest.fixture()
def meta_falso(monkeypatch):
    """Graph API de mentira: GET /v23.0/<id> da la URL; GET /archivo/<id>, el contenido."""
    estado = {"archivos": {}, "info": {}, "pedidos": []}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):  # noqa: N802
            estado["pedidos"].append((self.path, self.headers.get("Authorization")))
            partes = self.path.strip("/").split("/")
            if partes[0] == "v23.0" and partes[1] in estado["info"]:
                cuerpo = json.dumps(estado["info"][partes[1]]).encode()
            elif partes[0] == "archivo" and partes[1] in estado["archivos"]:
                cuerpo = estado["archivos"][partes[1]]
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setattr(wa, "GRAPH_BASE", base)

    def publicar(media_id, datos, file_size=None):
        estado["archivos"][media_id] = datos
        estado["info"][media_id] = {"url": f"{base}/archivo/{media_id}",
                                    "file_size": file_size if file_size is not None else len(datos)}

    estado["publicar"] = publicar
    yield estado
    srv.shutdown()
    srv.server_close()


def test_se_baja_en_dos_pasos_con_el_token(meta_falso):
    meta_falso["publicar"]("m1", b"%PDF-1.7 hola")
    assert wa.descargar_archivo(CFG, "m1") == b"%PDF-1.7 hola"
    assert meta_falso["pedidos"] == [("/v23.0/m1", "Bearer tok"), ("/archivo/m1", "Bearer tok")]


def test_un_archivo_que_no_existe(meta_falso):
    with pytest.raises(wa.ArchivoNoDisponible, match="HTTP 404"):
        wa.descargar_archivo(CFG, "nada")


def test_demasiado_grande_segun_meta_ni_se_baja(meta_falso, monkeypatch):
    monkeypatch.setattr(wa, "MAX_ARCHIVO", 100)
    meta_falso["publicar"]("m1", b"x" * 10, file_size=5000)
    with pytest.raises(wa.ArchivoNoDisponible, match="pasa de"):
        wa.descargar_archivo(CFG, "m1")
    assert [p for p, _ in meta_falso["pedidos"]] == ["/v23.0/m1"]


def test_demasiado_grande_aunque_meta_diga_otra_cosa(meta_falso, monkeypatch):
    monkeypatch.setattr(wa, "MAX_ARCHIVO", 100)
    meta_falso["publicar"]("m1", b"x" * 500, file_size=10)
    with pytest.raises(wa.ArchivoNoDisponible, match="pasa de"):
        wa.descargar_archivo(CFG, "m1")


def test_meta_sin_url(meta_falso):
    meta_falso["info"]["m1"] = {"id": "m1"}
    with pytest.raises(wa.ArchivoNoDisponible, match="dirección"):
        wa.descargar_archivo(CFG, "m1")


def test_meta_caido(monkeypatch):
    monkeypatch.setattr(wa, "GRAPH_BASE", "http://127.0.0.1:9")   # puerto cerrado
    with pytest.raises(wa.ArchivoNoDisponible, match="no pude conectar"):
        wa.descargar_archivo(CFG, "m1")
