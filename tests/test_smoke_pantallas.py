"""Smoke tests: cada pantalla se **abre** sin romperse, con datos y sin red.

**Por qué existe (22/9/2026).** Los bugs que importaron los encontró Franco
usando la app, no los tests: los tests probaban la lógica pura y ninguno
*abría una pantalla*. Así estuvieron latentes:

* el `NameError: fecha_val` que tiraba la pantalla de Cartera entera en
  cuanto había un pagaré con tasa devengada (dos meses, desde M11);
* el `SyntaxError` del 5/8 que dejó una pantalla caída en producción;
* el `UnboundLocalError: firma_val` al cargar un gasto desde el celular.

`streamlit.testing.v1.AppTest` corre el script de verdad, en este proceso, sin
navegador. La base es sintética (CI no tiene los datos de Franco) y la red
está cortada a propósito: todas las fuentes externas "se caen", así que de
paso se prueba que una fuente caída no tumba ninguna pantalla.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

from core import db as core_db  # noqa: E402
from core.db import connect, init_db  # noqa: E402

TIMEOUT = 60


def _sin_red(*a, **k):
    raise OSError("sin red en los tests")


@pytest.fixture()
def base(tmp_path, monkeypatch):
    """Una base con un usuario, gastos, categorías y una cartera chica."""
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    monkeypatch.setenv("CARTERA_USER_IDS", "1")
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    for modulo in ("precios", "mep", "sectores", "indices", "cronogramas"):
        monkeypatch.setattr(f"core.market_data.{modulo}._fetch_http", _sin_red)

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

        conn.executemany(
            "INSERT INTO cartera_instrumentos (ticker, user_id, descripcion, "
            " categoria_activo, moneda_cotiz, activo, tasa_anual_usd) "
            "VALUES (?, 1, ?, ?, ?, 1, ?)",
            [("AL30", "Bono Rep. Argentina USD Step Up Vto. 09/07/2030",
              "Bonos", "ARS/100", None),
             ("GGAL", "Grupo Financiero Galicia", "Acciones", "ARS", None),
             # El caso de B1: un pagaré con tasa devengada cargada.
             ("#PAGARE1", "Pagaré MAV", "Pagares", "ARS", 0.10)])
        movs = [
            ("2026-01-05", "DEPOSITO", "Depósito", 3_000_000, 0, 0, "DEPOSITO", 0),
            ("2026-01-06", "COMPRA", "AL30 | Bono", -800_000, 1000, 80_000, "AL30", 1),
            ("2026-01-07", "COMPRA", "GGAL | Galicia", -600_000, 100, 6_000, "GGAL", 1),
            ("2026-01-08", "COMPRA", "#PAGARE1 | Pagaré", -1_000_000, 1000, 1_000,
             "#PAGARE1", 1),
            ("2026-03-02", "VENTA", "GGAL | Galicia", 350_000, -50, 7_000, "GGAL", 1),
        ]
        conn.executemany(
            "INSERT INTO cartera_movimientos (user_id, fecha_concertacion, "
            " categoria, descripcion, monto, cantidad, precio, moneda, "
            " ticker_crudo, ticker_base, es_instrumento, tc_mep, hash_dedupe) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, 'ARS', ?, ?, ?, 1200.0, ?)",
            [(f, c, d, m, q, p, t, t, e, f"h{i}")
             for i, (f, c, d, m, q, p, t, e) in enumerate(movs)])
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


def test_la_pantalla_de_cartera_abre_con_un_pagare_con_tasa(base):
    """⚠️ El caso exacto de B1: con una tasa devengada cargada, `_resolver`
    leía `fecha_val` antes de que existiera y la pantalla entera moría."""
    def pantalla():
        import streamlit as st
        from core.context import set_current_user_id
        from places.inversiones import home
        set_current_user_id(st.session_state["current_user_id"])
        home.render()

    at = _correr(pantalla)
    _sin_errores(at)
    textos = " ".join(m.value for m in at.markdown)
    assert "Cómo te fue en total" in textos


def test_quitar_la_tasa_devengada_funciona(base):
    """El botón "Quitar" (22/9/2026): antes no había forma de sacar una tasa
    desde la app — y con B1, eso dejaba la pantalla caída para siempre."""
    def pantalla():
        import streamlit as st
        from core.context import set_current_user_id
        from places.inversiones import home
        set_current_user_id(st.session_state["current_user_id"])
        home.render()

    at = _correr(pantalla)
    at.selectbox(key="cartera_dev_ticker").set_value("#PAGARE1")
    at.run()
    at.button(key="cartera_btn_dev_quitar").click()
    at.run()
    _sin_errores(at)
    with connect(base) as conn:
        tasa = conn.execute(
            "SELECT tasa_anual_usd FROM cartera_instrumentos WHERE ticker = '#PAGARE1'"
        ).fetchone()[0]
    assert tasa is None


def test_el_shell_completo_abre_logueado(base):
    """`app.py` entero: migraciones, workspace activo, navegación."""
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco"
    at.run()
    _sin_errores(at)
