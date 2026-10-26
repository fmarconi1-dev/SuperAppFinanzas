"""Frente 4 de rendimiento (21/10/2026): sin loops por fila y con el índice de fecha.

`grupos_efectivos` reemplaza los `iterrows` de `metrics`, `diario` y `budget`:
tiene que dar **exactamente** lo mismo que `efective_grupo` fila a fila, con la
regla dual de "Inversiones" incluida. Y M25 tiene que dejar a SQLite leer las
transacciones en orden sin un B-tree temporal.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from core import db as core_db
from core.context import set_current_user_id
from core.db import connect, init_db
from places.finanzas.core.categorizer import efective_grupo, grupos_efectivos


CATS = {
    "Inversiones": ("Inversion", "Activos financieros"),
    "Compras": ("Gasto Variable", "Consumo"),
    "Haberes": ("Ingreso", "Sueldo"),
    "Sin sub": ("Gasto Fijo", None),
}

FILAS = [
    ("Inversiones", 0.0, 50_000.0),      # dual: vuelve como ingreso → Ingreso/Desahorro
    ("Inversiones", 50_000.0, 0.0),      # va como pasivo → su grupo de siempre
    ("Inversiones", 10.0, 10.0),         # las dos cosas: no es la regla dual
    ("Compras", 3_500.0, 0.0),
    ("Haberes", 0.0, 900_000.0),
    ("Sin sub", 1.0, 0.0),
    ("No existe", 1.0, 0.0),             # → Sin categorizar
    ("Inversiones", 0, 1),               # enteros, como pueden venir de SQLite
]


def test_grupos_efectivos_da_lo_mismo_que_fila_por_fila():
    motivos, pasivos, ingresos = zip(*FILAS)
    esperado = [efective_grupo(m, float(p), float(i), CATS) for m, p, i in FILAS]
    grupos, subs = grupos_efectivos(pd.Series(motivos), pd.Series(pasivos), pd.Series(ingresos), CATS)
    assert list(zip(grupos, subs)) == esperado
    assert esperado[0] == ("Ingreso", "Desahorro")
    assert esperado[6] == ("Sin categorizar", None)


def test_grupos_efectivos_sin_filas():
    assert grupos_efectivos([], [], [], CATS) == ([], [])


@pytest.fixture()
def base(tmp_path, monkeypatch):
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(ruta)
    from places.finanzas.core.ingest import init_categorias
    from places.finanzas.core.transactions import insertar_sin_backup
    set_current_user_id(1)
    with connect(ruta) as conn:
        init_categorias(conn, user_id=1)
        hoy = date.today()
        insertar_sin_backup(conn, hoy - timedelta(days=40), "Compras", pasivos=1_000, user_id=1)
        insertar_sin_backup(conn, hoy - timedelta(days=30), "Inversiones", ingresos=5_000, user_id=1)
    return ruta


def test_m25_lee_las_transacciones_en_orden_sin_ordenar_aparte(base):
    with connect(base) as conn:
        plan = " | ".join(r[3] for r in conn.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM transacciones WHERE workspace_id = 1 "
            "ORDER BY fecha DESC, id DESC LIMIT 5"))
    assert "idx_transacciones_ws_fecha" in plan
    assert "TEMP B-TREE" not in plan


def test_el_libro_diario_sin_filas_en_la_ventana_trae_sus_columnas(base):
    from places.finanzas.core.diario import libro_diario

    with connect(base) as conn:
        df = libro_diario(conn, dias=7, user_id=1)
    assert df.empty
    assert {"grupo", "subcategoria", "caja_despues"} <= set(df.columns)


def test_el_libro_diario_aplica_la_regla_dual_y_el_saldo_de_toda_la_historia(base):
    from places.finanzas.core.diario import libro_diario

    with connect(base) as conn:
        df = libro_diario(conn, dias=35, user_id=1)
    assert list(df["motivo"]) == ["Inversiones"]          # el de hace 40 días queda afuera
    assert (df.loc[0, "grupo"], df.loc[0, "subcategoria"]) == ("Ingreso", "Desahorro")
    # El saldo cuenta también el gasto que quedó fuera de la ventana
    # (saldo inicial 0 en esta base).
    assert df.loc[0, "caja_despues"] == pytest.approx(-1_000 + 5_000, abs=0.01)
