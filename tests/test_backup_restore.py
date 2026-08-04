"""Ensayo del ciclo de respaldo: backup → pérdida → restore → verificación.

**Por qué existe.** Un backup que nunca se restauró no es un backup: es un
archivo. Este test ejercita el procedimiento completo del `RUNBOOK` sobre una
base real, así que si alguien rompe el formato, la retención o el orden de los
pasos, se entera acá y no el día que lo necesita.

Cubre lo que estaba flojo hasta la Fase 4:

* que **importar cartera deje un punto de retorno** (antes solo las escrituras
  de Finanzas Personales disparaban copia: cargar 585 movimientos no dejaba
  ninguna);
* que la copia sea **restaurable y completa**, no solo un archivo que existe;
* que la purga **nunca se lleve puesta la única copia buena**.
"""

from __future__ import annotations

import sqlite3

import pytest

from core import db as core_db
from core.db import backup_db, connect, init_db
from places.inversiones.cartera.ingest import importar_movimientos
from places.inversiones.cartera.parser import Instrumento, parse_filas


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    """DB y directorio de backups aislados, como en producción pero en tmp."""
    ruta = tmp_path / "finanzas.db"
    backups = tmp_path / "backups"
    monkeypatch.setenv("DB_PATH", str(ruta))
    monkeypatch.setattr(core_db, "BACKUP_DIR", backups)
    init_db(ruta)
    conn = connect(ruta)
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) "
        "VALUES (1, 'franco', 'Franco')"
    )
    conn.commit()
    yield conn, ruta, backups
    conn.close()


def _filas_movimientos(n: int):
    filas = [["Operación", "Concertación", "Liquidación", "Descripción",
              "Monto", "Cantidad", "Precio", "Moneda"]]
    for i in range(n):
        filas.append(["Compra", f"2026-01-{i % 28 + 1:02d}", None,
                      "GGAL | Grupo Galicia", -1000.0 - i, 10, 100.0, "ARS"])
    return filas


def _contar(ruta, tabla) -> int:
    con = sqlite3.connect(ruta)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# La cartera tiene que dejar punto de retorno
# ---------------------------------------------------------------------------

def test_importar_cartera_deja_una_copia_antes_de_escribir(entorno):
    """El agujero que se tapó en la Fase 4: un import masivo es la operación
    más destructiva de la app y no generaba ningún respaldo."""
    conn, _, backups = entorno
    insts = {"GGAL": Instrumento(ticker="GGAL", categoria_activo="Acciones")}

    assert not list(backups.glob("finanzas-*.db"))
    importar_movimientos(conn, parse_filas(_filas_movimientos(5), insts), 1)
    conn.commit()

    copias = list(backups.glob("finanzas-*.db"))
    assert copias, "importar movimientos no dejó copia de seguridad"


def test_la_copia_es_anterior_al_import_o_sea_sirve_para_volver(entorno):
    """La copia se saca ANTES de escribir: si el archivo importado estaba mal,
    volver a ella deshace el daño."""
    conn, _, backups = entorno
    insts = {"GGAL": Instrumento(ticker="GGAL", categoria_activo="Acciones")}

    importar_movimientos(conn, parse_filas(_filas_movimientos(3), insts), 1)
    conn.commit()
    primera = sorted(backups.glob("finanzas-*.db"))[0]
    assert _contar(primera, "cartera_movimientos") == 0

    importar_movimientos(conn, parse_filas(_filas_movimientos(9), insts), 1)
    conn.commit()
    ultima = sorted(backups.glob("finanzas-*.db"))[-1]
    assert _contar(ultima, "cartera_movimientos") == 3   # el estado previo


# ---------------------------------------------------------------------------
# El ciclo completo del RUNBOOK
# ---------------------------------------------------------------------------

def test_ciclo_completo_backup_perdida_restore(entorno):
    """El ensayo que faltaba: se respalda, se pierde todo y se vuelve."""
    conn, ruta, backups = entorno
    insts = {"GGAL": Instrumento(ticker="GGAL", categoria_activo="Acciones")}

    # Datos de los dos lugares: la cartera se puede reconstruir del Excel,
    # las transacciones personales NO existen en ningún otro lado.
    conn.execute(
        "INSERT INTO transacciones (user_id, fecha, motivo, pasivos) "
        "VALUES (1, '2026-01-15', 'Supermercado', 50000)"
    )
    conn.commit()
    importar_movimientos(conn, parse_filas(_filas_movimientos(7), insts), 1)
    conn.commit()

    copia = backup_db(db_path=ruta)
    assert copia.exists()
    assert _contar(copia, "transacciones") == 1
    assert _contar(copia, "cartera_movimientos") == 7

    # Verificación previa: es lo que hacen los scripts antes de restaurar.
    con = sqlite3.connect(copia)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()

    # Se pierde la base (el volumen de Fly, un borrado, lo que sea).
    conn.close()
    ruta.unlink()
    assert not ruta.exists()

    # Restore: la copia pasa a ser la base.
    ruta.write_bytes(copia.read_bytes())

    restaurada = connect(ruta)
    try:
        assert restaurada.execute(
            "SELECT COUNT(*) FROM transacciones").fetchone()[0] == 1
        assert restaurada.execute(
            "SELECT COUNT(*) FROM cartera_movimientos").fetchone()[0] == 7
        assert restaurada.execute(
            "SELECT motivo FROM transacciones").fetchone()[0] == "Supermercado"
    finally:
        restaurada.close()


def test_la_base_restaurada_sigue_siendo_escribible(entorno):
    """Restaurar y que la app no pueda escribir sería medio restore."""
    conn, ruta, _ = entorno
    conn.execute(
        "INSERT INTO transacciones (user_id, fecha, motivo, pasivos) "
        "VALUES (1, '2026-01-15', 'Alquiler', 300000)"
    )
    conn.commit()
    copia = backup_db(db_path=ruta)
    conn.close()

    ruta.unlink()
    ruta.write_bytes(copia.read_bytes())
    restaurada = connect(ruta)
    try:
        restaurada.execute(
            "INSERT INTO transacciones (user_id, fecha, motivo, pasivos) "
            "VALUES (1, '2026-02-01', 'Nafta', 20000)"
        )
        restaurada.commit()
        assert restaurada.execute(
            "SELECT COUNT(*) FROM transacciones").fetchone()[0] == 2
    finally:
        restaurada.close()


# ---------------------------------------------------------------------------
# La purga no puede dejarte sin nada
# ---------------------------------------------------------------------------

def test_la_purga_conserva_las_copias_recientes(entorno):
    """`_purge_old_backups` guarda las 10 más nuevas + la última de cada día
    dentro de la ventana. Con muchas copias del mismo día no puede vaciarse."""
    conn, ruta, backups = entorno
    conn.execute(
        "INSERT INTO transacciones (user_id, fecha, motivo, pasivos) "
        "VALUES (1, '2026-01-15', 'Test', 1)"
    )
    conn.commit()
    for _ in range(15):
        backup_db(db_path=ruta)

    quedan = list(backups.glob("finanzas-*.db"))
    assert quedan, "la purga borró TODAS las copias"
    assert all(_contar(p, "transacciones") >= 1 for p in quedan)
