"""Agenda por WhatsApp (Fase B, ADR-0008): `evento:`, `tarea:` y `agenda`.

Tres capas: el intérprete puro (`places/finanzas/core/agenda.py`), los
comandos dentro de `procesar` con un cliente falso, y el cliente real
(`core/api/google.py`) contra un **Apps Script de mentira** que hace lo mismo
que Google: contesta el POST con un 302 y da la respuesta por GET.
"""

from __future__ import annotations

import json
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import core.db as core_db
from core.api.google import AgendaNoDisponible, AgendaRechazo, ClienteAgenda
from core.context import set_current_workspace_id
from core.db import connect, init_db
from places.finanzas.core import agenda as ag
from places.finanzas.core.comandos import ZONA, procesar

HOY = date(2026, 10, 16)  # viernes
AHORA = datetime(2026, 10, 16, 12, 0, tzinfo=ZONA)


# ------------------------------------------------------------------ fechas y horas

@pytest.mark.parametrize("crudo, esperado", [
    ("hoy", date(2026, 10, 16)),
    ("mañana", date(2026, 10, 17)),
    ("manana", date(2026, 10, 17)),
    ("pasado mañana", date(2026, 10, 18)),
    ("viernes", date(2026, 10, 16)),      # hoy es viernes
    ("lunes", date(2026, 10, 19)),
    ("Miércoles", date(2026, 10, 21)),
    ("20/10", date(2026, 10, 20)),
    ("20/10/2026", date(2026, 10, 20)),
    ("2026-12-01", date(2026, 12, 1)),
    ("10/01", date(2027, 1, 10)),        # sin año y ya pasó → el año que viene
])
def test_fechas_de_agenda(crudo, esperado):
    assert ag.parsear_fecha_agenda(crudo, HOY) == esperado


def test_no_es_fecha():
    assert ag.parsear_fecha_agenda("Dentista", HOY) is None


@pytest.mark.parametrize("crudo, motivo", [("31/02", "no existe"), ("10/10/2026", "ya pasó")])
def test_fechas_de_agenda_invalidas(crudo, motivo):
    with pytest.raises(ag.AgendaInvalida, match=motivo):
        ag.parsear_fecha_agenda(crudo, HOY)


@pytest.mark.parametrize("crudo, esperado", [
    ("15", "15:00"), ("15hs", "15:00"), ("15 hs", "15:00"), ("15:30", "15:30"),
    ("9.30", "09:30"), ("15h30", "15:30"), ("Dentista", None), ("2026", None),
])
def test_horas(crudo, esperado):
    assert ag.parsear_hora(crudo) == esperado


def test_hora_imposible():
    with pytest.raises(ag.AgendaInvalida, match="no existe"):
        ag.parsear_hora("25:00")


# ------------------------------------------------------------------ evento y tarea

def test_evento_completo():
    assert ag.parsear_evento("20/10, 15:00, 16:00, Dentista, Llevar estudios", HOY) == {
        "fecha": "2026-10-20", "hora_inicio": "15:00", "hora_fin": "16:00",
        "titulo": "Dentista", "descripcion": "Llevar estudios"}


def test_evento_con_rango_en_un_bloque():
    ev = ag.parsear_evento("lunes, 9-10:30, Reunión", HOY)
    assert (ev["fecha"], ev["hora_inicio"], ev["hora_fin"], ev["titulo"]) == (
        "2026-10-19", "09:00", "10:30", "Reunión")


def test_evento_de_todo_el_dia_y_con_una_sola_hora():
    assert ag.parsear_evento("20/10, Cumple de Juan", HOY)["hora_inicio"] is None
    ev = ag.parsear_evento("mañana, 21hs, Cena", HOY)
    assert (ev["hora_inicio"], ev["hora_fin"], ev["titulo"]) == ("21:00", None, "Cena")


@pytest.mark.parametrize("cuerpo, motivo", [
    ("20/10", "Faltan datos"),
    ("20/10, 15:00", "Falta el título"),
    ("Dentista, 20/10", "no es una fecha"),
    ("20/10, 16:00, 15:00, Dentista", "después de la de inicio"),
])
def test_eventos_que_no_se_mandan(cuerpo, motivo):
    with pytest.raises(ag.AgendaInvalida, match=motivo):
        ag.parsear_evento(cuerpo, HOY)


def test_tareas():
    assert ag.parsear_tarea("25/10, Pagar seguro", HOY) == {
        "fecha": "2026-10-25", "titulo": "Pagar seguro", "descripcion": None}
    assert ag.parsear_tarea("Llamar al contador, por el monotributo", HOY) == {
        "fecha": None, "titulo": "Llamar al contador", "descripcion": "por el monotributo"}
    # Una sola palabra que parece fecha es el título, no la fecha.
    assert ag.parsear_tarea("hoy", HOY)["titulo"] == "hoy"


def test_confirmaciones_muestran_el_dia_de_la_semana():
    ev = ag.parsear_evento("lunes, 15, 16, Dentista", HOY)
    assert ag.confirmar_evento(ev, HOY) == "✅ Evento agendado: Dentista (lun 19/10, 15:00–16:00)"
    ev = ag.parsear_evento("10/01, Feriado", HOY)
    assert ag.confirmar_evento(ev, HOY) == "✅ Evento agendado: Feriado (dom 10/01/2027, todo el día)"
    ta = ag.parsear_tarea("25/10, Pagar seguro", HOY)
    assert ag.confirmar_tarea(ta, HOY) == "✅ Tarea creada: Pagar seguro (vence dom 25/10)"


def test_formatear_semana():
    texto = ag.formatear_semana({
        "eventos": [
            {"titulo": "Feriado", "todo_el_dia": True, "inicio": "2026-10-16", "fin": "2026-10-16"},
            {"titulo": "Dentista", "todo_el_dia": False, "inicio": "2026-10-16T15:00:00-03:00"},
            {"titulo": "Cena", "todo_el_dia": False, "inicio": "2026-10-17T21:00:00-03:00"},
        ],
        "tareas": [{"titulo": "Pagar seguro", "vence": "2026-10-14"},
                   {"titulo": "Llamar al contador", "vence": None}],
    }, HOY)
    assert "*vie 16/10* · Hoy\n  Todo el día Feriado\n  15:00 Dentista" in texto
    assert "*sáb 17/10* · Mañana\n  21:00 Cena" in texto
    assert "• Pagar seguro (vence mié 14/10 — vencida)" in texto
    assert "• Llamar al contador" in texto


def test_semana_vacia():
    texto = ag.formatear_semana({"eventos": [], "tareas": []}, HOY)
    assert "Sin eventos" in texto and "Ninguna." in texto


# ------------------------------------------------------------------ comandos en procesar

class AgendaFalsa:
    def __init__(self, falla=None):
        self.llamados: list[tuple[str, dict]] = []
        self.falla = falla

    def _registrar(self, accion, **campos):
        self.llamados.append((accion, campos))
        if self.falla:
            raise self.falla
        return {"ok": True}

    def crear_evento(self, **campos):
        return self._registrar("crear_evento", **campos)

    def crear_tarea(self, **campos):
        return self._registrar("crear_tarea", **campos)

    def resumen_semana(self, **campos):
        self._registrar("resumen_semana", **campos)
        return {"ok": True, "eventos": [], "tareas": [{"titulo": "Pagar seguro", "vence": None}]}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(db_path)
    conn = connect(db_path)
    set_current_workspace_id(None)
    yield conn
    conn.close()


def test_evento_por_whatsapp_viaja_con_el_wamid(db):
    falsa = AgendaFalsa()
    r = procesar(db, "Evento: lunes, 15:00, 16:00, Dentista", user_id=1, ahora=AHORA,
                 agenda=falsa, id_mensaje="wamid.1")
    assert r.resultado == "agendado" and "Dentista (lun 19/10, 15:00–16:00)" in r.texto
    accion, campos = falsa.llamados[0]
    assert accion == "crear_evento" and campos["id_solicitud"] == "wamid.1"
    assert campos["fecha"] == "2026-10-19" and campos["titulo"] == "Dentista"


def test_tarea_por_whatsapp(db):
    falsa = AgendaFalsa()
    r = procesar(db, "tarea: Llamar al contador", user_id=1, ahora=AHORA, agenda=falsa)
    assert r.resultado == "agendado" and r.texto == "✅ Tarea creada: Llamar al contador"
    assert falsa.llamados[0][0] == "crear_tarea"


def test_agenda_por_whatsapp(db):
    r = procesar(db, "Agenda", user_id=1, ahora=AHORA, agenda=AgendaFalsa())
    assert r.resultado == "consulta" and "Agenda de la semana" in r.texto and "Pagar seguro" in r.texto


@pytest.mark.parametrize("falla, texto", [
    (AgendaRechazo("parametros_invalidos", "falta titulo"), "Google no lo aceptó"),
    (AgendaNoDisponible("timeout"), "No pude hablar con Google"),
])
def test_si_google_falla_no_se_confirma(db, falla, texto):
    r = procesar(db, "evento: lunes, Dentista", user_id=1, ahora=AHORA, agenda=AgendaFalsa(falla))
    assert r.resultado == "error" and texto in r.texto and "✅" not in r.texto


def test_sin_agenda_configurada(db):
    r = procesar(db, "evento: lunes, Dentista", user_id=1, ahora=AHORA, agenda=None)
    assert r.resultado == "rechazado" and "no está conectada" in r.texto


def test_un_evento_mal_escrito_no_llega_a_google(db):
    falsa = AgendaFalsa()
    r = procesar(db, "evento: Dentista", user_id=1, ahora=AHORA, agenda=falsa)
    assert r.resultado == "rechazado" and falsa.llamados == []


def test_un_gasto_sigue_siendo_un_gasto(db):
    """Que "evento:" exista no cambia nada de la carga de gastos."""
    r = procesar(db, "2500, super", user_id=1, ahora=AHORA, agenda=AgendaFalsa())
    assert r.resultado in {"pendiente", "cargado"}


# ------------------------------------------------------------------ cliente real vs Apps Script de mentira

@pytest.fixture()
def apps_script():
    """Hace lo que hace Google: POST /exec → 302 → GET devuelve el JSON."""
    estado = {"recibido": None, "respuesta": {"ok": True, "id": "ev1"}, "html": False}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            largo = int(self.headers.get("Content-Length") or 0)
            estado["recibido"] = json.loads(self.rfile.read(largo))
            self.send_response(302)
            self.send_header("Location", "/macros/echo?user_content_key=x")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if estado["html"]:
                cuerpo, tipo = b"<html>Iniciar sesion</html>", "text/html"
            else:
                cuerpo, tipo = json.dumps(estado["respuesta"]).encode(), "application/json"
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cliente = ClienteAgenda(url=f"http://127.0.0.1:{srv.server_address[1]}/exec", secreto="s3")
    yield cliente, estado
    srv.shutdown()
    srv.server_close()


def test_el_cliente_sigue_el_302_y_manda_secreto_e_id(apps_script):
    cliente, estado = apps_script
    r = cliente.crear_evento(fecha="2026-10-19", titulo="Dentista", hora_inicio="15:00",
                             id_solicitud="wamid.9")
    assert r["ok"] is True
    assert estado["recibido"] == {"secreto": "s3", "accion": "crear_evento", "fecha": "2026-10-19",
                                  "titulo": "Dentista", "hora_inicio": "15:00",
                                  "id_solicitud": "wamid.9"}


def test_ok_false_es_un_rechazo_aunque_el_http_sea_200(apps_script):
    cliente, estado = apps_script
    estado["respuesta"] = {"ok": False, "error": "no_autorizado"}
    with pytest.raises(AgendaRechazo) as e:
        cliente.crear_tarea(titulo="x")
    assert e.value.codigo == "no_autorizado"


def test_una_pagina_de_login_no_es_una_respuesta(apps_script):
    cliente, estado = apps_script
    estado["html"] = True
    with pytest.raises(AgendaNoDisponible, match="Cualquier persona"):
        cliente.resumen_semana()


def test_sin_apps_script_corriendo():
    cliente = ClienteAgenda(url="http://127.0.0.1:9/exec", secreto="s")
    with pytest.raises(AgendaNoDisponible):
        cliente.resumen_semana()


def test_sin_variables_la_agenda_queda_apagada(monkeypatch):
    monkeypatch.delenv("GOOGLE_WORKSPACE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("GOOGLE_WORKSPACE_SECRET", "s")
    assert ClienteAgenda.desde_entorno() is None
