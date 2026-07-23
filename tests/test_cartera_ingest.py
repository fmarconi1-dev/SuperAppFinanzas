"""Tests del ingest de cartera (Fase 3a): carga de instrumentos + movimientos.

Sintético y autocontenido (corre en CI): no depende del Excel real. La
reconciliación contra la planilla vive en `test_cartera_recon.py`.
"""

from __future__ import annotations

import pytest

from core import db as core_db
from core.db import connect, init_db
from places.inversiones.cartera.ingest import (
    cargar_instrumentos_en_db,
    importar_movimientos,
    instrumentos_desde_config,
)
from places.inversiones.cartera.parser import Instrumento, parse_filas
from places.inversiones.cartera.posiciones import posiciones_desde_db


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(db_path)
    conn = connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) "
        "VALUES (1, 'franco', 'Franco')"
    )
    yield conn
    conn.close()


@pytest.fixture()
def instrumentos():
    I = Instrumento
    return {
        "GGAL": I("GGAL", "GGALD", "Acciones", "ARS"),
        "SPY": I("SPY", "SPYD", "Cedears", "ARS"),
    }


def _movs(instrumentos):
    filas = [
        ["Compra", "2026-01-10", "2026-01-12", "GGAL | Grupo", -1000, 10, 100, "ARS"],
        ["Compra", "2026-02-10", "2026-02-12", "GGAL | Grupo", -1100, 5, 110, "ARS"],
        ["Venta", "2026-03-10", "2026-03-12", "GGAL | Grupo", 700, -4, 115, "ARS"],
        ["Compra", "2026-01-21", "2026-01-23", "SPYD | SPDR", -176.79, 5, 35.23, "USD"],
    ]
    return parse_filas(filas, instrumentos)


def _mini_excel(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Config"
    headers = ["Ticker ARS", "Ticker USD", "Descripción", "Categoría",
               "Panel Precio", "Activo en cartera", "Moneda Cotiz", "Divisor a USD"]
    for i, h in enumerate(headers):
        ws.cell(4, 7 + i, h)
    filas = [
        ("GGAL", "GGALD", "Grupo Financiero Galicia", "Acciones", "PANEL LIDER", "SI", "ARS", 1408),
        ("AE38", "AE38D", "Bono USD 2038", "Bonos", "BONOS", "SI", "USD/100", 100),
    ]
    for r, fila in enumerate(filas, start=5):
        for i, v in enumerate(fila):
            ws.cell(r, 7 + i, v)
    p = tmp_path / "mini.xlsx"
    wb.save(p)
    return p


# ---------------------------------------------------------------------------

def test_importar_y_dedupe(db, instrumentos):
    ins, skip = importar_movimientos(db, _movs(instrumentos), user_id=1)
    assert (ins, skip) == (4, 0)
    # re-importar el mismo archivo → todo saltado por el hash.
    ins2, skip2 = importar_movimientos(db, _movs(instrumentos), user_id=1)
    assert (ins2, skip2) == (0, 4)
    n = db.execute("SELECT COUNT(*) c FROM cartera_movimientos").fetchone()["c"]
    assert n == 4


def test_posiciones_desde_db(db, instrumentos):
    importar_movimientos(db, _movs(instrumentos), user_id=1)
    pos = posiciones_desde_db(db, user_id=1)
    assert pos["GGAL"].cant_actual == 11        # 10 + 5 - 4
    assert pos["SPY"].cant_actual == 5          # SPYD pliega a SPY (Config)
    assert pos["GGAL"].costo_ars_compras == pytest.approx(2100.0)  # 1000 + 1100


def test_ingest_aisla_por_usuario(db, instrumentos):
    importar_movimientos(db, _movs(instrumentos), user_id=1)
    # mismo archivo, otro usuario: entra (hash único por user_id).
    ins, _ = importar_movimientos(db, _movs(instrumentos), user_id=2)
    assert ins == 4
    assert "GGAL" in posiciones_desde_db(db, user_id=2)


def test_instrumentos_desde_config(tmp_path):
    insts = instrumentos_desde_config(_mini_excel(tmp_path))
    assert insts["GGAL"].ticker_usd == "GGALD"
    assert insts["AE38"].moneda_cotiz == "USD/100"
    assert insts["AE38"].divide_por_100 is True


def test_cargar_instrumentos_en_db(db, tmp_path):
    n = cargar_instrumentos_en_db(db, _mini_excel(tmp_path), user_id=1)
    db.commit()
    assert n == 2
    row = db.execute(
        "SELECT * FROM cartera_instrumentos WHERE ticker='AE38' AND user_id=1"
    ).fetchone()
    assert row["moneda_cotiz"] == "USD/100"
    assert row["divisor_usd"] == 100
    assert row["categoria_activo"] == "Bonos"
