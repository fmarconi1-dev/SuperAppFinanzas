"""El editor de categorías de Configuración (`places/finanzas/core/categorias.py`).

Pendiente de la auditoría del 22/9/2026: estaba al 35% de cobertura. Lo que
importa: lo protegido no se toca, lo que está en uso no se borra, cada error
se dice (nada se ignora en silencio) y cada espacio edita solo lo suyo.
"""

from __future__ import annotations

from datetime import date

import pytest

import core.db as core_db
from core.context import set_current_workspace_id
from core.db import connect, init_db
from core.workspaces import create_family_workspace
from places.finanzas.core.categorias import (
    delete_categoria,
    insert_categoria,
    motivos_sin_uso,
    update_categoria,
)
from places.finanzas.core.transactions import insert_transaction

UID = 1


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(db_path)
    conn = connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) VALUES (1, 'franco', 'Franco')"
    )
    set_current_workspace_id(None)
    yield conn
    set_current_workspace_id(None)
    conn.close()


def _categoria(conn, motivo):
    fila = conn.execute(
        "SELECT grupo, subcategoria FROM categorias WHERE motivo = ?", (motivo,)).fetchone()
    return tuple(fila) if fila else None


# ---------------------------------------------------------------- alta

def test_crear_una_categoria(db):
    insert_categoria(db, "  Gimnasio ", "Gasto Fijo", "Salud", user_id=UID)
    assert _categoria(db, "Gimnasio") == ("Gasto Fijo", "Salud")      # sin los espacios


def test_crear_sin_grupo_queda_sin_categorizar(db):
    insert_categoria(db, "Regalos", user_id=UID)
    assert _categoria(db, "Regalos") == ("Sin categorizar", None)


@pytest.mark.parametrize("motivo", ["", "   "])
def test_un_motivo_vacio_no_se_crea(db, motivo):
    with pytest.raises(ValueError, match="vacío"):
        insert_categoria(db, motivo, user_id=UID)


def test_un_grupo_que_no_existe_no_se_acepta(db):
    with pytest.raises(ValueError, match="inválido"):
        insert_categoria(db, "Gimnasio", "Gasto Raro", user_id=UID)
    assert _categoria(db, "Gimnasio") is None


def test_no_se_duplica_una_categoria(db):
    insert_categoria(db, "Gimnasio", user_id=UID)
    with pytest.raises(ValueError, match="Ya existe"):
        insert_categoria(db, "Gimnasio", "Gasto Fijo", user_id=UID)


# ---------------------------------------------------------------- edición

def test_editar_grupo_y_subcategoria(db):
    insert_categoria(db, "Gimnasio", user_id=UID)
    update_categoria(db, "Gimnasio", "Gasto Variable", "Deporte", user_id=UID)
    assert _categoria(db, "Gimnasio") == ("Gasto Variable", "Deporte")
    update_categoria(db, "Gimnasio", "Gasto Variable", "", user_id=UID)
    assert _categoria(db, "Gimnasio") == ("Gasto Variable", None)     # "" → sin subcategoría


def test_editar_una_que_no_existe_lo_dice(db):
    with pytest.raises(LookupError):
        update_categoria(db, "Nunca Existió", "Gasto Fijo", None, user_id=UID)


def test_editar_con_un_grupo_invalido_no_toca_nada(db):
    insert_categoria(db, "Gimnasio", "Gasto Fijo", user_id=UID)
    with pytest.raises(ValueError, match="inválido"):
        update_categoria(db, "Gimnasio", "Cualquiera", None, user_id=UID)
    assert _categoria(db, "Gimnasio") == ("Gasto Fijo", None)


def test_caja_esta_protegida(db):
    with pytest.raises(ValueError, match="protegido"):
        update_categoria(db, "Caja", "Gasto Fijo", None, user_id=UID)
    with pytest.raises(ValueError, match="protegido"):
        delete_categoria(db, "Caja", user_id=UID)


# ---------------------------------------------------------------- borrado

def test_borrar_una_sin_uso(db):
    insert_categoria(db, "Gimnasio", user_id=UID)
    delete_categoria(db, "Gimnasio", user_id=UID)
    assert _categoria(db, "Gimnasio") is None


def test_no_se_borra_una_en_uso(db):
    insert_transaction(db, date(2026, 10, 1), "Supermercado", pasivos=100, user_id=UID)
    with pytest.raises(ValueError, match="en uso"):
        delete_categoria(db, "Supermercado", user_id=UID)
    assert _categoria(db, "Supermercado") is not None


def test_borrar_una_que_no_existe_lo_dice(db):
    with pytest.raises(LookupError):
        delete_categoria(db, "Nunca Existió", user_id=UID)


def test_cada_cambio_deja_backup(db, monkeypatch):
    llamadas = []
    monkeypatch.setattr("places.finanzas.core.categorias.backup_db",
                        lambda: llamadas.append(1))
    insert_categoria(db, "Gimnasio", user_id=UID)
    update_categoria(db, "Gimnasio", "Gasto Fijo", None, user_id=UID)
    delete_categoria(db, "Gimnasio", user_id=UID)
    assert len(llamadas) == 3


# ---------------------------------------------------------------- sin uso y espacios

def test_motivos_sin_uso(db):
    insert_transaction(db, date(2026, 10, 1), "Supermercado", pasivos=100, user_id=UID)
    insert_categoria(db, "Gimnasio", user_id=UID)
    insert_categoria(db, "Abono", user_id=UID)
    sin_uso = motivos_sin_uso(db, user_id=UID)
    assert {"Abono", "Gimnasio"} <= set(sin_uso)
    assert "Supermercado" not in sin_uso and "Caja" not in sin_uso
    assert sin_uso == sorted(sin_uso)


def test_cada_espacio_edita_solo_lo_suyo(db):
    """La misma categoría en el personal y en el familiar son dos categorías."""
    insert_categoria(db, "Gimnasio", "Gasto Fijo", user_id=UID)
    ws_fam, _ = create_family_workspace(db, "Casa", user_id=UID)
    set_current_workspace_id(ws_fam)
    insert_categoria(db, "Gimnasio", "Gasto Variable", user_id=UID)   # no choca
    delete_categoria(db, "Gimnasio", user_id=UID)
    with pytest.raises(LookupError):
        update_categoria(db, "Gimnasio", "Gasto Fijo", None, user_id=UID)
    set_current_workspace_id(None)
    assert _categoria(db, "Gimnasio") == ("Gasto Fijo", None)          # la personal sigue
