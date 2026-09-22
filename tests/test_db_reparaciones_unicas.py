"""Las reparaciones de datos viejas corren **una vez**, no en cada arranque.

**Por qué existe (22/9/2026).** M3, M7 y M8.5 son `UPDATE`/`DELETE` sobre
filas, y corrían cada vez que arrancaba la app — en Fly, cada deploy y cada vez
que la máquina se despierta. Consecuencias que estos tests fijan:

* M3 volvía a pasar "Compra Divisa" a Inversión aunque el usuario la hubiera
  reclasificado a propósito.
* M7 volvía a llenar una subcategoría que el usuario vació.
* M8.5, la reparación del incidente del 17/7, **borraba** la fila correcta de
  un espacio si aparecía una huérfana.

Y M5 tenía el mismo guard incompleto que M4 el 17/7. Misma lección de la nota
post-incidente: los tests de migraciones corren **con datos** y verifican los
vínculos, no solo que no crashee.
"""

from __future__ import annotations

import sqlite3

import pytest

from core import db as core_db
from core.db import connect, init_db
from core.workspaces import ensure_personal_workspace


@pytest.fixture()
def ruta(tmp_path, monkeypatch):
    r = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(r))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(r)
    return r


def _ws(ruta) -> int:
    with connect(ruta) as conn:
        wid = ensure_personal_workspace(conn, 1)
        conn.commit()
    return wid


def test_init_db_marca_las_reparaciones_como_aplicadas(ruta):
    with connect(ruta) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == \
            core_db._NIVEL_REPARACIONES


def test_una_reclasificacion_del_usuario_sobrevive_al_reinicio(ruta):
    wid = _ws(ruta)
    with connect(ruta) as conn:
        conn.execute(
            "INSERT INTO categorias (motivo, grupo, subcategoria, user_id, workspace_id) "
            "VALUES ('Compra Divisa', 'Gasto Variable', 'Consumo', 1, ?)", (wid,))
        conn.commit()

    init_db(ruta)              # un deploy / Fly despertando la máquina

    with connect(ruta) as conn:
        fila = conn.execute(
            "SELECT grupo, subcategoria FROM categorias WHERE motivo = 'Compra Divisa'"
        ).fetchone()
    assert (fila["grupo"], fila["subcategoria"]) == ("Gasto Variable", "Consumo")


def test_una_subcategoria_vaciada_no_se_vuelve_a_llenar(ruta):
    wid = _ws(ruta)
    with connect(ruta) as conn:
        conn.execute(
            "INSERT INTO categorias (motivo, grupo, subcategoria, user_id, workspace_id) "
            "VALUES ('Auto', 'Gasto Fijo', NULL, 1, ?)", (wid,))
        conn.commit()

    init_db(ruta)

    with connect(ruta) as conn:
        sub = conn.execute(
            "SELECT subcategoria FROM categorias WHERE motivo = 'Auto'").fetchone()[0]
    assert sub is None


def test_una_fila_huerfana_nueva_no_borra_la_buena(ruta):
    """Una fila con `workspace_id NULL` hoy es un bug, no historia: no puede
    llevarse puesta la configuración correcta del espacio."""
    wid = _ws(ruta)
    with connect(ruta) as conn:
        conn.execute("INSERT INTO configuracion (clave, valor, user_id, workspace_id) "
                     "VALUES ('saldo_inicial_caja', '1000', 1, ?)", (wid,))
        conn.execute("INSERT INTO configuracion (clave, valor, user_id, workspace_id) "
                     "VALUES ('saldo_inicial_caja', '999999', 1, NULL)")
        conn.commit()

    init_db(ruta)

    with connect(ruta) as conn:
        valor = conn.execute(
            "SELECT valor FROM configuracion WHERE clave = 'saldo_inicial_caja' "
            "AND workspace_id = ?", (wid,)).fetchone()[0]
    assert valor == "1000"


def test_una_base_vieja_si_recibe_las_reparaciones_una_vez(ruta):
    """El camino legacy sigue andando: una base con `user_version` 0 (como la
    de producción antes de este cambio) corre las reparaciones y queda
    marcada."""
    wid = _ws(ruta)
    with connect(ruta) as conn:
        conn.execute(
            "INSERT INTO categorias (motivo, grupo, subcategoria, user_id, workspace_id) "
            "VALUES ('Compra Divisa', 'Gasto Variable', NULL, 1, ?)", (wid,))
        conn.execute("PRAGMA user_version = 0")
        conn.commit()

    init_db(ruta)

    with connect(ruta) as conn:
        fila = conn.execute(
            "SELECT grupo, subcategoria FROM categorias WHERE motivo = 'Compra Divisa'"
        ).fetchone()
        nivel = conn.execute("PRAGMA user_version").fetchone()[0]
    assert (fila["grupo"], fila["subcategoria"]) == ("Inversion", "Ahorro y Resguardo")
    assert nivel == core_db._NIVEL_REPARACIONES


def test_la_marca_es_transaccional(ruta):
    """`_migrate` pone la marca dentro de su transacción confiando en que un
    ROLLBACK la deshace — así, si una migración falla, las reparaciones se
    reintentan en el próximo arranque. Se verifica esa propiedad de SQLite."""
    with connect(ruta) as conn:
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(f"PRAGMA user_version = {core_db._NIVEL_REPARACIONES}")
        cur.execute("ROLLBACK")
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0


def test_m5_no_reconstruye_una_tabla_post_d2(ruta):
    """Mismo patrón de falla que M4 el 17/7: si `transacciones` post-D2 tuviera
    otra vez un DEFAULT en `user_id`, el rebuild de M5 descartaría
    `workspace_id` y desvincularía los datos."""
    wid = _ws(ruta)
    with connect(ruta) as conn:
        conn.execute("ALTER TABLE transacciones RENAME TO t_vieja")
        conn.execute("""
            CREATE TABLE transacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL, pasivos REAL NOT NULL DEFAULT 0,
                ingresos REAL NOT NULL DEFAULT 0, motivo TEXT NOT NULL,
                comentario TEXT,
                creado_en TEXT NOT NULL DEFAULT (datetime('now')),
                user_id INTEGER NOT NULL DEFAULT 1,
                workspace_id INTEGER REFERENCES workspaces(id),
                creado_por_member_label TEXT)""")
        conn.execute("DROP TABLE t_vieja")
        conn.execute("INSERT INTO transacciones (fecha, pasivos, motivo, user_id, "
                     "workspace_id) VALUES ('2026-09-01', 100, 'Auto', 1, ?)", (wid,))
        conn.commit()

    init_db(ruta)

    with connect(ruta) as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(transacciones)")}
        vinculadas = conn.execute(
            "SELECT COUNT(*) FROM transacciones WHERE workspace_id = ?",
            (wid,)).fetchone()[0]
    assert {"workspace_id", "creado_por_member_label"} <= cols
    assert vinculadas == 1
