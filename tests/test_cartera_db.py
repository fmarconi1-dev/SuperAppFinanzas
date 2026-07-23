"""Tests de la migración M9 — cartera nativa (Fase 3a).

Cubre el esquema de las tres tablas nuevas (aditivas, scope por user_id):
creación, idempotencia de `init_db`, dedupe por hash en la carga recurrente,
y aislamiento entre usuarios. No toca las tablas de finanzas.
"""

from __future__ import annotations

import pytest

from core import db as core_db
from core.db import connect, init_db


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
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) "
        "VALUES (2, 'otro', 'Otro')"
    )
    yield conn
    conn.close()


TABLAS = frozenset({"cartera_instrumentos", "cartera_movimientos", "cartera_precios_cache"})


def _tablas(conn):
    return {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _mov(user_id=1, hash_dedupe="h1", **kw):
    base = dict(
        user_id=user_id,
        fecha_concertacion="2026-01-10",
        fecha_liquidacion="2026-01-12",
        categoria="COMPRA",
        descripcion="GGAL | Grupo",
        monto=-1000.0,
        cantidad=10.0,
        precio=100.0,
        moneda="ARS",
        ticker_crudo="GGAL",
        ticker_base="GGAL",
        operacion_original="Compra",
        formato="viejo",
        es_instrumento=1,
        es_espejo=0,
        es_saldo_inicial=0,
        precio_normalizado=None,
        tc_mep=None,
        hash_dedupe=hash_dedupe,
    )
    base.update(kw)
    return base


def _insert_mov(conn, m):
    cols = ", ".join(m.keys())
    ph = ", ".join(["?"] * len(m))
    conn.execute(
        f"INSERT OR IGNORE INTO cartera_movimientos ({cols}) VALUES ({ph})",
        list(m.values()),
    )


# ---------------------------------------------------------------------------

def test_m9_crea_las_tres_tablas(db):
    assert TABLAS <= _tablas(db)


def test_init_db_es_idempotente(db, tmp_path, monkeypatch):
    # correr init_db de nuevo no rompe ni borra datos.
    _insert_mov(db, _mov(hash_dedupe="a"))
    db.commit()
    db_path = tmp_path / "finanzas.db"
    init_db(db_path)          # segunda corrida
    init_db(db_path)          # tercera corrida
    n = db.execute("SELECT COUNT(*) c FROM cartera_movimientos").fetchone()["c"]
    assert n == 1
    assert TABLAS <= _tablas(db)


def test_no_toca_tablas_de_finanzas(db):
    # las tablas de finanzas siguen existiendo tras M9.
    assert {"transacciones", "categorias", "presupuesto", "configuracion"} <= _tablas(db)


def test_instrumentos_pk_por_ticker_y_usuario(db):
    db.execute(
        "INSERT INTO cartera_instrumentos (ticker, user_id, ticker_usd, "
        "categoria_activo, moneda_cotiz) VALUES ('GGAL', 1, 'GGALD', 'Acciones', 'ARS')"
    )
    # mismo ticker, otro usuario: permitido (PK compuesta).
    db.execute(
        "INSERT INTO cartera_instrumentos (ticker, user_id, moneda_cotiz) "
        "VALUES ('GGAL', 2, 'ARS')"
    )
    # mismo ticker y usuario: viola la PK.
    with pytest.raises(Exception):
        db.execute(
            "INSERT INTO cartera_instrumentos (ticker, user_id, moneda_cotiz) "
            "VALUES ('GGAL', 1, 'ARS')"
        )


def test_dedupe_por_hash_en_reimport(db):
    # dos filas idénticas del MISMO archivo llegan con hashes distintos
    # (contador de ocurrencia del parser) → ambas entran.
    _insert_mov(db, _mov(hash_dedupe="occ0"))
    _insert_mov(db, _mov(hash_dedupe="occ1"))
    # re-importar el mismo archivo repite los MISMOS hashes → OR IGNORE los saltea.
    _insert_mov(db, _mov(hash_dedupe="occ0"))
    _insert_mov(db, _mov(hash_dedupe="occ1"))
    db.commit()
    n = db.execute("SELECT COUNT(*) c FROM cartera_movimientos").fetchone()["c"]
    assert n == 2


def test_scope_por_usuario_aisla(db):
    _insert_mov(db, _mov(user_id=1, hash_dedupe="h"))
    _insert_mov(db, _mov(user_id=2, hash_dedupe="h"))  # mismo hash, otro user: entra
    db.commit()
    n1 = db.execute(
        "SELECT COUNT(*) c FROM cartera_movimientos WHERE user_id=1"
    ).fetchone()["c"]
    n2 = db.execute(
        "SELECT COUNT(*) c FROM cartera_movimientos WHERE user_id=2"
    ).fetchone()["c"]
    assert n1 == 1 and n2 == 1


def test_tc_mep_es_nullable(db):
    # el TC MEP se congela recién en el paso 3 (market_data); acá queda NULL.
    _insert_mov(db, _mov(tc_mep=None))
    db.commit()
    row = db.execute(
        "SELECT tc_mep FROM cartera_movimientos LIMIT 1"
    ).fetchone()
    assert row["tc_mep"] is None


def test_precios_cache_pk_ticker_fecha_moneda(db):
    db.execute(
        "INSERT INTO cartera_precios_cache (ticker, fecha, precio, moneda, fuente) "
        "VALUES ('GGAL', '2026-07-22', 7945.0, 'ARS', 'byma')"
    )
    # upsert manual: misma PK, otro precio → conflicto controlado.
    with pytest.raises(Exception):
        db.execute(
            "INSERT INTO cartera_precios_cache (ticker, fecha, precio, moneda) "
            "VALUES ('GGAL', '2026-07-22', 8000.0, 'ARS')"
        )
    # distinta moneda: permitido.
    db.execute(
        "INSERT INTO cartera_precios_cache (ticker, fecha, precio, moneda) "
        "VALUES ('GGAL', '2026-07-22', 5.2, 'USD')"
    )
