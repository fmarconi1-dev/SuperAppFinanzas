"""Inicio y rebranding (Fase C, pasos 1–2, ADR-0008).

* La lógica del Inicio (`places/inicio/core/resumen.py`): mes anterior,
  variación contra el **mismo período**, signos.
* **Los KPIs del Inicio son los mismos números que `resumen` por WhatsApp.**
* La pantalla abre (con y sin movimientos) y la app entera abre en Inicio.
* La marca es "Secretario": no queda "Radar Financiero" en la interfaz.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

from core import db as core_db  # noqa: E402
from core.context import set_current_workspace_id  # noqa: E402
from core.db import connect, init_db  # noqa: E402
from places.finanzas.core import comandos  # noqa: E402
from places.finanzas.core.transactions import insert_transaction  # noqa: E402
from places.inicio.core import resumen as rs  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
HOY = date(2026, 10, 17)
TIMEOUT = 60


# ------------------------------------------------------------------ lógica pura

@pytest.mark.parametrize("hoy, esperado", [
    (date(2026, 10, 17), date(2026, 9, 1)),
    (date(2026, 1, 5), date(2025, 12, 1)),
    (date(2026, 3, 31), date(2026, 2, 1)),
])
def test_mes_anterior(hoy, esperado):
    assert rs.mes_anterior(hoy) == esperado


def test_variacion_y_formato():
    assert rs.variacion(110, 100) == pytest.approx(10.0)
    assert rs.variacion(10, 0) is None and rs.variacion(10, None) is None   # nada de "inf%"
    assert rs.formatear_variacion(4.25) == "+4,2%" or rs.formatear_variacion(4.25) == "+4,3%"
    # ASCII "-": st.metric decide flecha y color por el primer carácter.
    assert rs.formatear_variacion(-3.0) == "-3,0%"
    assert rs.formatear_variacion(None) is None


@pytest.mark.parametrize("hora, texto", [(8, "Buen día"), (15, "Buenas tardes"), (23, "Buenas noches"),
                                         (3, "Buenas noches")])
def test_saludo(hora, texto):
    assert rs.saludo(hora) == texto


def test_fecha_larga():
    assert rs.fecha_larga(HOY) == "sábado 17 de octubre de 2026"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(ruta)
    conn = connect(ruta)
    set_current_workspace_id(None)
    for motivo, grupo in [("Supermercado", "Gasto Variable"), ("Sueldo", "Ingreso")]:
        insert_transaction(conn, fecha=date(2026, 1, 1), motivo=motivo, pasivos=1, user_id=1)
        conn.execute("UPDATE categorias SET grupo = ? WHERE motivo = ?", (grupo, motivo))
    conn.execute("DELETE FROM transacciones")
    yield conn
    conn.close()


def _cargar(conn, fecha, motivo, pasivos=0.0, ingresos=0.0):
    insert_transaction(conn, fecha=fecha, motivo=motivo, pasivos=pasivos, ingresos=ingresos, user_id=1)


def test_la_comparacion_es_contra_el_mismo_periodo(db):
    _cargar(db, date(2026, 10, 5), "Supermercado", pasivos=1100)
    _cargar(db, date(2026, 9, 5), "Supermercado", pasivos=1000)
    _cargar(db, date(2026, 9, 25), "Supermercado", pasivos=50_000)   # después del 17: no cuenta
    r = rs.resumen_del_mes(db, user_id=1, hoy=HOY)
    assert r.actual.gastos == 1100 and r.previo.gastos == 1000
    assert rs.variacion(r.actual.gastos, r.previo.gastos) == pytest.approx(10.0)
    assert r.periodo_previo() == "1 al 17 de septiembre"


def test_sin_mes_anterior_no_hay_comparacion(db):
    _cargar(db, date(2026, 10, 5), "Supermercado", pasivos=1100)
    assert rs.resumen_del_mes(db, user_id=1, hoy=HOY).previo is None


def test_el_31_compara_hasta_el_ultimo_dia_del_mes_anterior(db):
    _cargar(db, date(2026, 10, 31), "Supermercado", pasivos=10)
    _cargar(db, date(2026, 9, 30), "Supermercado", pasivos=20)
    r = rs.resumen_del_mes(db, user_id=1, hoy=date(2026, 10, 31))
    assert r.previo.gastos == 20 and r.periodo_previo() == "1 al 30 de septiembre"


def test_los_kpis_del_inicio_son_los_de_resumen(db):
    """El Inicio y el bot no pueden mostrar cifras distintas."""
    _cargar(db, date(2026, 10, 3), "Supermercado", pasivos=25_000)
    _cargar(db, date(2026, 10, 4), "Sueldo", ingresos=900_000)
    _cargar(db, date(2026, 10, 6), "Regalo", pasivos=7000)            # sin categorizar
    r = rs.resumen_del_mes(db, user_id=1, hoy=HOY)
    texto = comandos.resumen_mes(db, user_id=1, hoy=HOY)
    assert f"Gastos: {comandos.pesos(r.actual.gastos)}" in texto
    assert f"Ingresos: {comandos.pesos(r.actual.ingresos)}" in texto
    assert f"Movimientos: {r.actual.movimientos}" in texto
    assert f"Sin categorizar: {comandos.pesos(r.actual.sin_categorizar)}" in texto
    assert r.balance == 900_000 - 25_000


def test_ultimos_movimientos_con_signo(db):
    _cargar(db, date(2026, 10, 3), "Supermercado", pasivos=25_000)
    _cargar(db, date(2026, 10, 4), "Sueldo", ingresos=900_000)
    filas = rs.ultimos_movimientos(db, user_id=1)
    assert [(f["motivo"], f["monto"]) for f in filas] == [("Sueldo", 900_000.0), ("Supermercado", -25_000.0)]


# ------------------------------------------------------------------ pantallas

@pytest.fixture()
def base(tmp_path, monkeypatch):
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(ruta)
    from places.finanzas.core.ingest import init_categorias
    with connect(ruta) as conn:
        conn.execute("UPDATE usuarios SET username = 'franco', fullname = 'Franco Marconi' WHERE id = 1")
        init_categorias(conn, user_id=1)
        conn.commit()
    import streamlit as st
    st.cache_data.clear()
    return ruta


def _inicio(con_movimientos: bool):
    # AppTest corre la función como un script aparte: no ve variables de
    # afuera. El dato viaja por session_state.
    def pantalla():
        from datetime import date as _date

        import streamlit as st
        from core.context import set_current_user_id
        from core.db import connect as _connect
        from places.finanzas.core.transactions import insert_transaction as _ins
        from places.inicio import home

        set_current_user_id(st.session_state["current_user_id"])
        if st.session_state.get("_con_movimientos") and not st.session_state.get("_sembrado"):
            with _connect() as c:
                hoy = _date.today()
                _ins(c, hoy, "Supermercado", pasivos=120_000, user_id=1)
                _ins(c, hoy, "Haberes UCEMA", ingresos=900_000, user_id=1)
            st.session_state["_sembrado"] = True
        home.render()

    at = AppTest.from_function(pantalla, default_timeout=TIMEOUT)
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco Marconi"
    at.session_state["_con_movimientos"] = con_movimientos
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    return at


def test_el_inicio_abre_con_movimientos(base):
    at = _inicio(con_movimientos=True)
    assert "Franco" in at.title[0].value
    etiquetas = [m.label for m in at.metric]
    assert any(e.startswith("Ingresos − gastos") for e in etiquetas)
    assert {"Gastos", "Ingresos", "Movimientos"} <= set(etiquetas)


def test_el_inicio_abre_sin_movimientos(base):
    at = _inicio(con_movimientos=False)
    assert not at.metric
    assert any("Todavía no hay movimientos" in i.value for i in at.info)


def test_la_app_abre_en_inicio(base):
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=TIMEOUT)
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco Marconi"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Franco" in at.title[0].value          # el saludo del Inicio, no el título de Finanzas


# ------------------------------------------------------------------ marca

def test_la_marca_es_secretario():
    app = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert 'page_title="Secretario"' in app
    assert ">\n                    Secretario\n" in (RAIZ / "core/auth/login.py").read_text(encoding="utf-8")


def test_no_queda_radar_financiero_en_la_interfaz():
    """Solo puede aparecer en docstrings y comentarios (historia), nunca en un texto que se muestra."""
    culpables = []
    for archivo in [RAIZ / "app.py", *(RAIZ / "places").rglob("*.py"), *(RAIZ / "core").rglob("*.py")]:
        if "__pycache__" in archivo.parts:
            continue
        for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if "Radar Financiero" in linea and re.search(r"st\.|title|label|caption|<h\d|>\s*Radar", linea):
                culpables.append(f"{archivo.relative_to(RAIZ)}:{n}")
    assert culpables == []


def test_las_pestanas_de_finanzas_usan_iconos_material():
    home = (RAIZ / "places/finanzas/home.py").read_text(encoding="utf-8")
    for nombre in ("Dashboard", "Transacciones", "Diario", "Mensual", "Configuración"):
        assert re.search(rf":material/\w+: {nombre}", home), nombre
