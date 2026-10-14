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
        hoy = date.today()
        for i, (motivo, pasivos, ingresos) in enumerate([
            ("Haberes UCEMA", 0, 900_000), ("Supermercado", 120_000, 0),
            ("Compra Divisa", 200_000, 0), ("Pago tarjeta", 80_000, 0),
        ]):
            insert_transaction(conn, hoy - timedelta(days=10 - i), motivo,
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


def test_el_shell_completo_abre_logueado(base):
    """`app.py` entero: migraciones, workspace activo, navegación."""
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco"
    at.run()
    _sin_errores(at)
