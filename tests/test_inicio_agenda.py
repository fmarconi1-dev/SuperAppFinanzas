"""Agenda en el Inicio (Fase C, pasos 3–5): semana, tareas con tilde y estado.

* Lógica pura (`places/inicio/core/semana.py`): días, eventos en curso, orden
  de tareas.
* `ClienteAgenda.completar_tarea` contra el Apps Script de mentira (302 como Google).
* La pantalla con `AppTest`: con agenda, completar una tarea (bien y con
  rechazo de Google), agenda caída y agenda sin configurar. El cliente se
  reemplaza por uno falso: no hay red.
"""

from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

from core import db as core_db  # noqa: E402
from core.api import google as g  # noqa: E402
from core.db import connect, init_db  # noqa: E402
from places.inicio.core import semana as sm  # noqa: E402
from tests.test_agenda_whatsapp import apps_script  # noqa: E402,F401 — fixture

HOY = date(2026, 10, 16)  # viernes
TIMEOUT = 60


# ------------------------------------------------------------------ lógica pura

def test_dias_de_la_semana():
    dias = sm.dias_de_la_semana([
        {"titulo": "Feriado", "todo_el_dia": True, "inicio": "2026-10-16", "fin": "2026-10-16"},
        {"titulo": "Dentista", "todo_el_dia": False, "inicio": "2026-10-16T15:00:00-03:00",
         "fin": "2026-10-16T16:00:00-03:00", "ubicacion": "Av. Santa Fe 1234"},
        {"titulo": "Cena", "todo_el_dia": False, "inicio": "2026-10-17T21:00:00-03:00",
         "fin": "2026-10-17T23:00:00-03:00"},
        {"titulo": "Congreso", "todo_el_dia": True, "inicio": "2026-10-20", "fin": "2026-10-22"},
    ], HOY)
    assert [(d.titulo, d.etiqueta) for d in dias] == [("vie 16/10", "Hoy"), ("sáb 17/10", "Mañana"),
                                                       ("mar 20/10", "")]
    assert [(e.hora, e.titulo) for e in dias[0].eventos] == [("Todo el día", "Feriado"), ("15:00", "Dentista")]
    assert dias[0].eventos[1].ubicacion == "Av. Santa Fe 1234"
    assert dias[2].eventos[0].hasta == date(2026, 10, 22)


def test_un_evento_que_empezo_antes_de_hoy_se_muestra_hoy_en_curso():
    dias = sm.dias_de_la_semana([
        {"titulo": "Vacaciones", "todo_el_dia": True, "inicio": "2026-10-14", "fin": "2026-10-18"},
        {"titulo": "Guardia", "todo_el_dia": False, "inicio": "2026-10-15T22:00:00-03:00",
         "fin": "2026-10-16T06:00:00-03:00"},
    ], HOY)
    assert len(dias) == 1 and dias[0].etiqueta == "Hoy"
    assert [(e.hora, e.titulo, e.hasta) for e in dias[0].eventos] == [
        ("Todo el día", "Vacaciones", date(2026, 10, 18)), ("En curso", "Guardia", None)]


def test_semana_vacia():
    assert sm.dias_de_la_semana([], HOY) == []


def test_tareas_vencidas_primero_despues_con_fecha_y_al_final_sin_fecha():
    tareas = sm.tareas_ordenadas([
        {"id": "1", "lista_id": "L", "titulo": "Llamar al contador", "vence": None},
        {"id": "2", "lista_id": "L", "titulo": "Renovar DNI", "vence": "2026-10-25"},
        {"id": "3", "lista_id": "L", "titulo": "Pagar seguro", "vence": "2026-10-14"},
        {"id": "4", "lista_id": "L", "titulo": "Turno médico", "vence": "2026-10-16"},
    ], HOY)
    assert [(t.titulo, t.detalle) for t in tareas] == [
        ("Pagar seguro", "vencida mié 14/10"),
        ("Turno médico", "vence hoy"),
        ("Renovar DNI", "vence dom 25/10"),
        ("Llamar al contador", ""),
    ]
    assert [t.vencida for t in tareas] == [True, False, False, False]


# ------------------------------------------------------------------ cliente

def test_completar_tarea_manda_lista_y_tarea(apps_script):  # noqa: F811
    cliente, estado = apps_script
    cliente.completar_tarea(lista_id="L1", tarea_id="T9")
    assert estado["recibido"] == {"secreto": "s3", "accion": "completar_tarea",
                                  "lista_id": "L1", "tarea_id": "T9"}


# ------------------------------------------------------------------ pantalla

SEMANA = {
    "ok": True,
    "eventos": [{"titulo": "Dentista", "todo_el_dia": False,
                 "inicio": date.today().isoformat() + "T15:00:00-03:00",
                 "fin": date.today().isoformat() + "T16:00:00-03:00"}],
    "tareas": [{"id": "T1", "lista_id": "L1", "titulo": "Pagar seguro", "vence": None},
               {"id": "T2", "lista_id": "L1", "titulo": "Llamar al contador", "vence": None}],
}


@pytest.fixture()
def falso(tmp_path, monkeypatch):
    """Base con categorías + agenda configurada con un cliente falso."""
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(ruta)
    from places.finanzas.core.ingest import init_categorias
    with connect(ruta) as conn:
        conn.execute("UPDATE usuarios SET username = 'franco', fullname = 'Franco' WHERE id = 1")
        init_categorias(conn, user_id=1)
        conn.commit()

    monkeypatch.setenv("GOOGLE_WORKSPACE_WEBHOOK_URL", "https://script.example/exec")
    monkeypatch.setenv("GOOGLE_WORKSPACE_SECRET", "s")
    estado = {"semana": SEMANA, "falla_semana": None, "falla_completar": None, "completadas": []}

    def resumen_semana(self, **_):
        if estado["falla_semana"]:
            raise estado["falla_semana"]
        return estado["semana"]

    def completar_tarea(self, *, lista_id, tarea_id, id_solicitud=None):
        if estado["falla_completar"]:
            raise estado["falla_completar"]
        estado["completadas"].append((lista_id, tarea_id))
        estado["semana"] = {**estado["semana"],
                            "tareas": [t for t in estado["semana"]["tareas"] if t["id"] != tarea_id]}
        return {"ok": True}

    monkeypatch.setattr(g.ClienteAgenda, "resumen_semana", resumen_semana)
    monkeypatch.setattr(g.ClienteAgenda, "completar_tarea", completar_tarea)
    import streamlit as st
    st.cache_data.clear()
    yield estado
    st.cache_data.clear()


def _pantalla():
    import streamlit as st
    from core.context import set_current_user_id
    from places.inicio import home

    set_current_user_id(st.session_state["current_user_id"])
    home.render()


def _abrir() -> AppTest:
    at = AppTest.from_function(_pantalla, default_timeout=TIMEOUT)
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _textos_html(at: AppTest) -> str:
    return " ".join(str(getattr(e, "proto", e)) for e in at.get("html"))


def test_el_inicio_muestra_la_semana_y_las_tareas(falso):
    at = _abrir()
    assert not at.error
    assert [s.value for s in at.subheader][:2] == ["Esta semana", "Tareas pendientes"]
    assert "Dentista" in _textos_html(at)
    assert [c.label for c in at.checkbox] == ["Pagar seguro", "Llamar al contador"]
    assert any("agenda conectada" in c.value for c in at.caption)


def test_tildar_una_tarea_la_completa_en_google(falso):
    at = _abrir()
    at.checkbox[0].check().run()
    assert falso["completadas"] == [("L1", "T1")]
    assert not at.error
    assert [c.label for c in at.checkbox] == ["Llamar al contador"]     # ya no está


def test_si_google_rechaza_la_tarea_no_se_tacha(falso):
    falso["falla_completar"] = g.AgendaRechazo("error_interno", "Tasks caído")
    at = _abrir()
    at.checkbox[0].check().run()
    assert falso["completadas"] == []
    assert any("No pude completar «Pagar seguro»" in e.value for e in at.error)
    assert at.checkbox[0].label == "Pagar seguro" and at.checkbox[0].value is False


def test_agenda_caida_muestra_el_motivo_y_reintentar(falso):
    falso["falla_semana"] = g.AgendaNoDisponible("timeout")
    at = _abrir()
    assert any("No pude traer tu agenda: timeout" in w.value for w in at.warning)
    assert any(b.label == "Reintentar" for b in at.button)
    falso["falla_semana"] = None
    next(b for b in at.button if b.label == "Reintentar").click().run()
    assert [c.label for c in at.checkbox] == ["Pagar seguro", "Llamar al contador"]


def test_sin_agenda_configurada_el_resto_anda(falso, monkeypatch):
    monkeypatch.delenv("GOOGLE_WORKSPACE_WEBHOOK_URL")
    at = _abrir()
    assert any("no está conectada" in i.value for i in at.info)
    assert not at.checkbox
    assert any("agenda sin conectar" in c.value for c in at.caption)


def test_el_estado_cuenta_los_mensajes_en_cola(falso):
    with connect() as conn:
        conn.execute("INSERT INTO whatsapp_salientes (tipo, texto, creado_en) VALUES ('briefing', 'x', '2026-10-16')")
        conn.commit()
    at = _abrir()
    assert any("1 mensaje esperando" in c.value for c in at.caption)
