"""Ensayo del ciclo de respaldo: backup → pérdida → restore → verificación.

**Por qué existe.** Un backup que nunca se restauró no es un backup: es un
archivo. Este test ejercita el procedimiento completo del `RUNBOOK` sobre una
base real, así que si alguien rompe el formato, la retención o el orden de los
pasos, se entera acá y no el día que lo necesita.

Cubre lo que estaba flojo hasta la Fase 4:

* que la copia sea **restaurable y completa**, no solo un archivo que existe;
* que la purga **nunca se lleve puesta la única copia buena**.
"""

from __future__ import annotations

import gc
import sqlite3
import time

import pytest

from core import db as core_db
from core.db import backup_db, connect, init_db


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


def _contar(ruta, tabla) -> int:
    con = sqlite3.connect(ruta)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
    finally:
        con.close()


def _perder_la_base(ruta) -> None:
    """Borra el archivo de la DB simulando que se perdió.

    **Por qué no es un simple `unlink()`.** En Linux se puede borrar un archivo
    aunque queden descriptores abiertos; **en Windows no**: mientras el proceso
    conserve un handle, `unlink` falla con `PermissionError [WinError 32]`. El
    test se escribió y se corrió en Linux (CI) y ahí pasaba; en la máquina de
    Franco fallaba. El defecto era del test, no del backup: se verificó que tras
    `init_db()` y `backup_db()` **no queda ninguna conexión abierta** — los
    handles que sobran son objetos ya cerrados esperando al recolector.

    Por eso: forzar la recolección, y reintentar unas pocas veces por si el
    sistema de archivos todavía no soltó el handle. Si igual no se puede
    borrar, se falla con un mensaje que lo explique en vez de un rastro
    confuso de permisos.
    """
    gc.collect()
    for extra in (".db-wal", ".db-shm", "-wal", "-shm"):
        companero = ruta.with_name(ruta.name.replace(".db", "") + extra)
        if companero.exists():
            try:
                companero.unlink()
            except OSError:
                pass
    ultimo: Exception | None = None
    for _ in range(10):
        try:
            ruta.unlink()
            return
        except PermissionError as exc:          # Windows: handle todavía vivo
            ultimo = exc
            gc.collect()
            time.sleep(0.05)
    raise AssertionError(
        f"no se pudo borrar {ruta} para simular la pérdida: {ultimo}. "
        "Si esto pasa siempre, hay una conexión sqlite que quedó abierta de "
        "verdad — revisá los call sites de `backup_db`."
    )


# ---------------------------------------------------------------------------
# El ciclo completo del RUNBOOK
# ---------------------------------------------------------------------------

def test_ciclo_completo_backup_perdida_restore(entorno):
    """El ensayo que faltaba: se respalda, se pierde todo y se vuelve."""
    conn, ruta, backups = entorno

    # Las transacciones personales NO existen en ningún otro lado.
    conn.execute(
        "INSERT INTO transacciones (user_id, fecha, motivo, pasivos) "
        "VALUES (1, '2026-01-15', 'Supermercado', 50000)"
    )
    conn.commit()

    copia = backup_db(db_path=ruta)
    assert copia.exists()
    assert _contar(copia, "transacciones") == 1

    # Verificación previa: es lo que hacen los scripts antes de restaurar.
    con = sqlite3.connect(copia)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()

    # Se pierde la base (el volumen de Fly, un borrado, lo que sea).
    conn.close()
    _perder_la_base(ruta)
    assert not ruta.exists()

    # Restore: la copia pasa a ser la base.
    ruta.write_bytes(copia.read_bytes())

    restaurada = connect(ruta)
    try:
        assert restaurada.execute(
            "SELECT COUNT(*) FROM transacciones").fetchone()[0] == 1
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

    _perder_la_base(ruta)
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


# ---------------------------------------------------------------------------
# El verificador que usan los scripts de PowerShell
# ---------------------------------------------------------------------------

def test_una_copia_buena_pasa_la_verificacion(entorno):
    from scripts.verificar_backup import verificar

    conn, ruta, _ = entorno
    conn.execute(
        "INSERT INTO transacciones (user_id, fecha, motivo, pasivos) "
        "VALUES (1, '2026-01-15', 'Supermercado', 50000)"
    )
    conn.commit()
    copia = backup_db(db_path=ruta)

    sirve, integridad, conteos = verificar(copia)
    assert sirve and integridad == "ok"
    assert conteos["transacciones"] == 1 and conteos["usuarios"] == 1


def test_una_copia_sin_transacciones_no_sirve(entorno):
    """Lo irreemplazable son los gastos personales: una copia sin eso no es
    una copia útil, aunque el archivo esté perfecto."""
    from scripts.verificar_backup import verificar

    _, ruta, _ = entorno
    sirve, integridad, conteos = verificar(backup_db(db_path=ruta))
    assert integridad == "ok"          # el archivo está sano...
    assert conteos["transacciones"] == 0
    assert not sirve                   # ...pero no sirve


@pytest.mark.parametrize("contenido,motivo", [
    (b"x", "vacio"),                          # truncada
    (b"no soy una base" * 500, "ilegible"),   # basura
])
def test_una_copia_rota_se_detecta_antes_de_restaurar(tmp_path, contenido, motivo):
    """Restaurar una copia rota encima de una base viva convierte un problema
    en un desastre: por eso se verifica ANTES."""
    from scripts.verificar_backup import verificar

    p = tmp_path / "rota.db"
    p.write_bytes(contenido)
    sirve, integridad, _ = verificar(p)
    assert not sirve
    assert motivo in integridad


def test_un_archivo_que_no_existe_no_explota(tmp_path):
    from scripts.verificar_backup import verificar

    sirve, integridad, _ = verificar(tmp_path / "fantasma.db")
    assert not sirve and integridad == "no existe"
