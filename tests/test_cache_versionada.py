"""Caché por versión de la base (frente 3 de rendimiento, 21/10/2026).

Inicio, Dashboard y Diario reusan lo que calcularon mientras la base no cambie.
"No cambie" lo dice `core.db.version_datos()` (`PRAGMA data_version` sobre una
conexión vigía). Lo que hay que cuidar: que **nunca** se muestre un número
viejo, sobre todo después de algo que escribió el bot de WhatsApp, que corre
en **otro proceso** sobre la misma base.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

from core import db as core_db  # noqa: E402
from core.db import connect, init_db, version_datos  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
TIMEOUT = 60


@pytest.fixture()
def base(tmp_path, monkeypatch):
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(ruta)
    from places.finanzas.core.ingest import init_categorias
    from places.finanzas.core.transactions import insertar_sin_backup

    with connect(ruta) as conn:
        conn.execute("UPDATE usuarios SET username = 'franco', fullname = 'Franco' WHERE id = 1")
        init_categorias(conn, user_id=1)
        hoy = date.today()
        insertar_sin_backup(conn, hoy, "Haberes UCEMA", ingresos=900_000, user_id=1)
        insertar_sin_backup(conn, hoy, "Compras", pasivos=120_000, user_id=1)

    import streamlit as st
    st.cache_data.clear()
    return ruta


def _gasto_desde_otro_proceso(ruta: Path, monto: int) -> None:
    """Como el bot: otro proceso de Python escribe en la misma base. "Compras" es
    Gasto Variable en las categorías de fábrica: suma a "Gastos del mes"."""
    codigo = (
        "import sys, datetime\n"
        f"sys.path.insert(0, {str(RAIZ)!r})\n"
        "from core.context import set_current_user_id\n"
        "from core.db import connect\n"
        "from places.finanzas.core.transactions import insertar_sin_backup\n"
        "set_current_user_id(1)\n"
        "with connect() as c:\n"
        f"    insertar_sin_backup(c, datetime.date.today(), 'Compras', pasivos={monto}, user_id=1)\n"
    )
    subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, check=True, timeout=120,
                   env={**os.environ, "DB_PATH": str(ruta)})


def _inicio() -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco"
    return at


def _gastos_del_mes(at: AppTest) -> str:
    return next(m.value for m in at.metric if m.label.startswith("Gastos de"))


def test_la_version_no_se_mueve_si_nadie_escribe(base):
    antes = version_datos(base)
    with connect(base) as conn:
        conn.execute("SELECT * FROM transacciones").fetchall()
    assert version_datos(base) == antes


def test_la_version_ve_lo_que_escribe_otro_proceso(base):
    antes = version_datos(base)
    _gasto_desde_otro_proceso(base, 1_000)
    assert version_datos(base) != antes


def test_el_vigia_no_frena_los_checkpoints_del_wal(base):
    version_datos(base)  # abre el vigía
    with connect(base) as conn:
        conn.execute("INSERT INTO configuracion (clave, valor, user_id, workspace_id) "
                     "SELECT 'x', '1', 1, id FROM workspaces LIMIT 1")
        ocupado, _, _ = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    assert ocupado == 0


def test_el_inicio_no_recalcula_si_no_cambio_nada(base, monkeypatch):
    from places.inicio.core import resumen as rs

    llamadas = []
    original = rs.resumen_del_mes
    monkeypatch.setattr(rs, "resumen_del_mes", lambda *a, **k: llamadas.append(1) or original(*a, **k))

    at = _inicio()
    at.run()
    at.run()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(llamadas) == 1


def test_el_inicio_muestra_al_toque_lo_que_cargo_el_bot(base):
    at = _inicio()
    at.run()
    antes = _gastos_del_mes(at)

    _gasto_desde_otro_proceso(base, 12_345)
    at.run()

    assert not at.exception, [e.value for e in at.exception]
    assert _gastos_del_mes(at) != antes


def test_el_dashboard_y_el_diario_muestran_lo_que_cargo_el_bot(base):
    from places.finanzas.home import CLAVE_PESTANA, PESTANAS

    def pantalla():
        import streamlit as st
        from core import workspaces_ui
        from core.context import set_current_user_id
        from core.db import connect
        from places.finanzas import home
        set_current_user_id(st.session_state["current_user_id"])
        with connect() as c:
            workspaces_ui.activar_desde_sesion(c)
        home.render()

    etiquetas = list(PESTANAS)
    for etiqueta in (etiquetas[0], etiquetas[2]):  # Dashboard, Diario
        at = AppTest.from_function(pantalla, default_timeout=TIMEOUT)
        at.session_state["logged_in"] = True
        at.session_state["current_user_id"] = 1
        at.session_state[CLAVE_PESTANA] = etiqueta
        at.run()
        antes = [m.value for m in at.metric] + [str(d.value) for d in at.dataframe]
        _gasto_desde_otro_proceso(base, 7_777)
        at.run()
        assert not at.exception, [e.value for e in at.exception]
        despues = [m.value for m in at.metric] + [str(d.value) for d in at.dataframe]
        assert despues != antes, etiqueta
