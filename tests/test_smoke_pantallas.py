"""Smoke tests: cada pantalla se **abre** sin romperse, con datos y sin red.

**Por qué existe (22/9/2026).** Los bugs que importaron los encontró Franco
usando la app, no los tests: los tests probaban la lógica pura y ninguno
*abría una pantalla*. Así estuvieron latentes:

* el `NameError: fecha_val` que tiraba la pantalla de Cartera entera en
  cuanto había un pagaré con tasa devengada (dos meses, desde M11; la
  Cartera se retiró el 14/10/2026, ADR-0007);
* el `SyntaxError` del 5/8 que dejó una pantalla caída en producción;
* el `UnboundLocalError: firma_val` al cargar un gasto desde el celular.

`streamlit.testing.v1.AppTest` corre el script de verdad, en este proceso, sin
navegador. La base es sintética (CI no tiene los datos de Franco).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

from core import db as core_db  # noqa: E402
from core.db import connect, init_db  # noqa: E402
from places.finanzas.home import CLAVE_PESTANA, PESTANAS  # noqa: E402

TIMEOUT = 60


@pytest.fixture()
def base(tmp_path, monkeypatch):
    """Una base con un usuario, gastos y categorías."""
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")

    init_db(ruta)
    from places.finanzas.core.ingest import init_categorias
    from places.finanzas.core.transactions import insert_transaction

    with connect(ruta) as conn:
        conn.execute("UPDATE usuarios SET username = 'franco', fullname = 'Franco' "
                     "WHERE id = 1")
        init_categorias(conn, user_id=1)
        # Todo dentro del mes en curso: el Dashboard abre en "Este mes" y sin
        # gastos no dibuja la dona (con "hoy − 10 días" el test fallaba del 1
        # al 10 de cada mes).
        hoy = date.today()
        for i, (motivo, pasivos, ingresos) in enumerate([
            ("Haberes UCEMA", 0, 900_000), ("Supermercado", 120_000, 0),
            ("Compra Divisa", 200_000, 0), ("Pago tarjeta", 80_000, 0),
        ]):
            insert_transaction(conn, min(hoy, hoy.replace(day=1) + timedelta(days=i)), motivo,
                               pasivos=pasivos, ingresos=ingresos, user_id=1)

        conn.commit()

    import streamlit as st
    st.cache_data.clear()
    return ruta


def _correr(funcion) -> AppTest:
    at = AppTest.from_function(funcion, default_timeout=TIMEOUT)
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco"
    at.run()
    return at


def _sin_errores(at: AppTest) -> None:
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_la_pantalla_de_finanzas_abre_con_sus_cinco_pestanas(base):
    def pantalla():
        import streamlit as st
        from core.context import set_current_user_id
        from places.finanzas import home
        set_current_user_id(st.session_state["current_user_id"])
        home.render()

    at = _correr(pantalla)
    _sin_errores(at)
    assert len(at.tabs) >= 5


@pytest.mark.parametrize("pestana", list(PESTANAS))
def test_cada_pestana_de_finanzas_abre(base, pestana):
    """Desde el 21/10/2026 solo corre la pestaña abierta (`on_change="rerun"`):
    abrir Finanzas ya no recorre las cinco, así que se abre cada una."""
    def pantalla():
        import streamlit as st
        from core.context import set_current_user_id
        from places.finanzas import home
        set_current_user_id(st.session_state["current_user_id"])
        home.render()

    at = AppTest.from_function(pantalla, default_timeout=TIMEOUT)
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco"
    at.session_state[CLAVE_PESTANA] = pestana
    at.run()
    _sin_errores(at)
    # Lo de Configuración aparece solo con Configuración abierta.
    es_configuracion = pestana.endswith("Configuración")
    assert ("Editor de categorías" in [s.value for s in at.subheader]) == es_configuracion


def test_los_controles_de_cada_grafico_del_dashboard_andan(base):
    """Las medias móviles y "Agrupar por" viven en fragmentos (21/10/2026):
    tocarlos redibuja solo su gráfico. Que sigan andando sin romper nada."""
    def pantalla():
        import streamlit as st
        from core.context import set_current_user_id
        from places.finanzas import home
        set_current_user_id(st.session_state["current_user_id"])
        home.render()

    at = _correr(pantalla)
    _sin_errores(at)
    at.multiselect(key="ma_ventanas").set_value([7]).run()
    _sin_errores(at)
    at.button_group(key="donut_agrupar_por").set_value(["Subcategoría"]).run()
    _sin_errores(at)


def test_los_filtros_del_dashboard_sobreviven_a_cambiar_de_pestana(base):
    """Con las pestañas diferidas, Streamlit borraba el estado de los filtros
    del Dashboard en cuanto se abría otra pestaña: al volver estaba otra vez en
    "Este mes". `FILTROS_QUE_PERSISTEN` lo evita."""
    def pantalla():
        import streamlit as st
        from core.context import set_current_user_id
        from places.finanzas import home
        set_current_user_id(st.session_state["current_user_id"])
        home.render()

    at = _correr(pantalla)
    at.button_group(key="dash_periodo").set_value("Año").run()
    at.multiselect(key="ma_ventanas").set_value([7]).run()
    etiquetas = list(PESTANAS)
    at.session_state[CLAVE_PESTANA] = etiquetas[2]  # Diario
    at.run()
    at.session_state[CLAVE_PESTANA] = etiquetas[0]  # de vuelta al Dashboard
    at.run()
    _sin_errores(at)
    assert at.button_group(key="dash_periodo").value == "Año"
    assert at.multiselect(key="ma_ventanas").value == [7]
    assert not [w.value for w in at.warning if "Session State" in str(w.value)]


def test_el_excel_se_arma_al_descargar_con_el_workspace_activo(base):
    """El Excel de Configuración se arma recién al descargar, en **otro hilo**
    de Streamlit, sin los contextvars del script: tiene que exportar el
    workspace que estaba activo (acá, uno familiar), no el personal."""
    import io
    import threading

    import pandas as pd

    from core.context import set_current_user_id, set_current_workspace_id
    from core.workspaces import create_family_workspace
    from places.finanzas.core.transactions import insertar_sin_backup
    from places.finanzas.views.configuracion import _generador_excel

    with connect(base) as conn:
        fam, _ = create_family_workspace(conn, "Casa", user_id=1)
        set_current_user_id(1)
        set_current_workspace_id(fam)
        insertar_sin_backup(conn, date.today(), "Gasto de la casa", pasivos=5_000, user_id=1)
        set_current_workspace_id(None)

    generar = _generador_excel(base, 1, fam)
    resultado = {}
    hilo = threading.Thread(target=lambda: resultado.update(xlsx=generar()))
    hilo.start()
    hilo.join()

    diario = pd.read_excel(io.BytesIO(resultado["xlsx"]), sheet_name="Diario")
    assert list(diario["Motivo"]) == ["Gasto de la casa"]


def test_el_shell_completo_abre_logueado(base):
    """`app.py` entero: migraciones, workspace activo, navegación."""
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco"
    at.run()
    _sin_errores(at)
