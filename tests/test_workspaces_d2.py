"""Tests del grupo familiar D2 (cutover) — plan definido en Mis-Finanzas MEJORAS.md.

Cubre: código de invitación único, join válido/inválido, leave que preserva
el workspace, firma de transacciones (creado_por_member_label) y el test
clave del premortem #5: las queries filtran por workspace (Franco Personal
≠ Franco+Agus Familiar).
"""

from __future__ import annotations

from datetime import date

import pytest

from core import db as core_db
from core.context import set_current_workspace_id
from core.db import connect, init_db
from core.workspaces import (
    create_family_workspace,
    ensure_personal_workspace,
    join_family_workspace,
    leave_family_workspace,
    list_members,
    list_user_workspaces,
    member_label_of,
)
from places.finanzas.core.metrics import load_transactions
from places.finanzas.core.transactions import insert_transaction, list_recent


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    init_db(db_path)
    conn = connect(db_path)
    # init_db puede haber creado ya el usuario local id=1.
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) VALUES (1, 'franco', 'Franco')"
    )
    conn.execute("UPDATE usuarios SET fullname = 'Franco' WHERE id = 1")
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) VALUES (2, 'agus', 'Agustina')"
    )
    set_current_workspace_id(None)  # contexto limpio en cada test
    yield conn
    set_current_workspace_id(None)
    conn.close()


def test_crear_workspace_genera_code_unico(db):
    _, code1 = create_family_workspace(db, "Casa", user_id=1)
    _, code2 = create_family_workspace(db, "Vacaciones", user_id=1)
    assert code1 and code2 and code1 != code2
    # En DB queda el hash, nunca el código en claro.
    hashes = [r["invitation_code_hash"] for r in db.execute(
        "SELECT invitation_code_hash FROM workspaces WHERE kind='familiar'")]
    assert code1 not in hashes and code2 not in hashes


def test_join_con_code_correcto_suma_miembro(db):
    ws_id, code = create_family_workspace(db, "Casa", user_id=1)
    joined = join_family_workspace(db, code, user_id=2)
    assert joined == ws_id
    labels = {m["member_label"] for m in list_members(db, ws_id)}
    assert labels == {"Franco", "Agustina"}


def test_join_con_code_invalido_rechaza(db):
    create_family_workspace(db, "Casa", user_id=1)
    with pytest.raises(LookupError):
        join_family_workspace(db, "codigo-falso", user_id=2)


def test_join_dos_veces_rechaza(db):
    _, code = create_family_workspace(db, "Casa", user_id=1)
    join_family_workspace(db, code, user_id=2)
    with pytest.raises(ValueError):
        join_family_workspace(db, code, user_id=2)


def test_leave_preserva_workspace_si_quedan_miembros(db):
    ws_id, code = create_family_workspace(db, "Casa", user_id=1)
    join_family_workspace(db, code, user_id=2)
    leave_family_workspace(db, ws_id, user_id=2)
    assert db.execute("SELECT 1 FROM workspaces WHERE id=?", (ws_id,)).fetchone()
    assert len(list_members(db, ws_id)) == 1


def test_leave_del_ultimo_miembro_elimina_workspace(db):
    ws_id, _ = create_family_workspace(db, "Casa", user_id=1)
    leave_family_workspace(db, ws_id, user_id=1)
    assert db.execute("SELECT 1 FROM workspaces WHERE id=?", (ws_id,)).fetchone() is None


def test_member_label_se_registra_al_insertar_en_familiar(db):
    ws_id, code = create_family_workspace(db, "Casa", user_id=1)
    join_family_workspace(db, code, user_id=2)
    set_current_workspace_id(ws_id)
    # Sin label explícito → usa la etiqueta del miembro.
    t1 = insert_transaction(db, date(2026, 7, 1), "Super", pasivos=100, user_id=1)
    # "Firmar como" explícito.
    t2 = insert_transaction(db, date(2026, 7, 2), "Nafta", pasivos=50, user_id=2,
                            member_label="Agustina")
    filas = {r["id"]: r for r in list_recent(db, user_id=1)}
    assert filas[t1]["creado_por_member_label"] == "Franco"
    assert filas[t2]["creado_por_member_label"] == "Agustina"


def test_en_personal_no_se_firma(db):
    insert_transaction(db, date(2026, 7, 1), "Super", pasivos=100, user_id=1)
    fila = list_recent(db, user_id=1)[0]
    assert fila["creado_por_member_label"] is None


def test_queries_filtran_por_workspace(db):
    """El test clave del premortem #5: Personal de Franco ≠ Familiar."""
    ws_fam, code = create_family_workspace(db, "Casa", user_id=1)
    join_family_workspace(db, code, user_id=2)

    # Franco carga 2 en su personal, 1 en el familiar; Agus 1 en el familiar.
    insert_transaction(db, date(2026, 7, 1), "Cine", pasivos=10, user_id=1)
    insert_transaction(db, date(2026, 7, 2), "Libros", pasivos=20, user_id=1)
    set_current_workspace_id(ws_fam)
    insert_transaction(db, date(2026, 7, 3), "Super", pasivos=100, user_id=1)
    insert_transaction(db, date(2026, 7, 4), "Farmacia", pasivos=30, user_id=2)

    # Vista familiar: 2 transacciones (de ambos miembros).
    fam = load_transactions(db, user_id=1)
    assert len(fam) == 2
    assert set(fam["motivo"]) == {"Super", "Farmacia"}

    # Vista personal de Franco: solo las suyas personales.
    set_current_workspace_id(None)
    per = load_transactions(db, user_id=1)
    assert len(per) == 2
    assert set(per["motivo"]) == {"Cine", "Libros"}

    # Vista personal de Agus: vacía.
    assert len(load_transactions(db, user_id=2)) == 0


def test_list_user_workspaces_personal_primero(db):
    ws_id, _ = create_family_workspace(db, "Casa", user_id=1)
    lista = list_user_workspaces(db, user_id=1)
    assert lista[0]["kind"] == "personal"
    assert any(w["id"] == ws_id and w["kind"] == "familiar" for w in lista)
    assert member_label_of(db, ws_id, user_id=1) == "Franco"


def test_ensure_personal_idempotente(db):
    a = ensure_personal_workspace(db, 1)
    b = ensure_personal_workspace(db, 1)
    assert a == b


# ---------- Regresión del incidente de producción (2026-07-17) ----------
# M4 se re-disparaba después de M8 (su guard miraba "PK contiene user_id"),
# reconstruía las tablas descartando workspace_id y desvinculaba TODO.
# Además, filas duplicadas escritas en la ventana rota hacían crashear la
# migración con UNIQUE constraint. Estos tests reproducen ambos modos.


def test_migrar_dos_veces_con_datos_no_desvincula(db, tmp_path, monkeypatch):
    """init_db repetido sobre una DB con datos: nada queda con workspace NULL."""
    insert_transaction(db, date(2026, 7, 1), "Super", pasivos=100, user_id=1)
    db.commit()
    db.close()

    init_db()  # segunda corrida completa de _migrate sobre la misma DB
    conn = connect()
    try:
        for tabla in ("transacciones", "categorias", "configuracion"):
            nulos = conn.execute(
                f"SELECT COUNT(*) AS n FROM {tabla} WHERE workspace_id IS NULL"
            ).fetchone()["n"]
            assert nulos == 0, f"{tabla} quedó con {nulos} filas desvinculadas"
        # Y la PK sigue siendo por workspace (M4 no debe re-dispararse).
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='configuracion'"
        ).fetchone()["sql"]
        assert "workspace_id" in sql.split("PRIMARY KEY")[-1]
        # Los datos siguen visibles por las queries del dominio.
        assert len(load_transactions(conn, user_id=1)) == 1
    finally:
        conn.close()


def test_reparacion_relinkea_filas_huerfanas(db):
    """Simula el estado roto de producción: filas con workspace_id NULL y un
    duplicado scoped escrito en la ventana rota. La migración debe reparar
    sin crashear, prefiriendo el dato original."""
    ws = ensure_personal_workspace(db, 1)
    insert_transaction(db, date(2026, 7, 1), "Super", pasivos=100, user_id=1)
    # Estado roto: todo desvinculado + duplicado scoped de configuracion.
    for tabla in ("transacciones", "categorias", "configuracion"):
        db.execute(f"UPDATE {tabla} SET workspace_id = NULL")
    db.execute(
        "INSERT INTO configuracion (clave, valor, user_id, workspace_id) "
        "VALUES ('saldo_inicial_caja', '999', 1, ?)", (ws,),
    )
    db.execute(
        "INSERT OR REPLACE INTO configuracion (clave, valor, user_id, workspace_id) "
        "VALUES ('saldo_inicial_caja', '123.45', 1, NULL)",
    )
    # La base rota del 17/7 es anterior a la marca de reparaciones únicas
    # (22/9/2026): tenía `user_version` 0. Sin esto el test simularía un
    # estado que nunca existió. Con la marca puesta, M8.5 ya no corre — ver
    # `test_db_reparaciones_unicas.py`.
    db.execute("PRAGMA user_version = 0")
    db.commit()
    db.close()

    init_db()  # no debe crashear y debe reparar
    conn = connect()
    try:
        nulos = conn.execute(
            "SELECT COUNT(*) AS n FROM configuracion WHERE workspace_id IS NULL"
        ).fetchone()["n"]
        assert nulos == 0
        # Gana el valor original (la fila NULL), no el duplicado de la ventana rota.
        valor = conn.execute(
            "SELECT valor FROM configuracion "
            "WHERE clave='saldo_inicial_caja' AND workspace_id = ?", (ws,),
        ).fetchone()["valor"]
        assert valor == "123.45"
        assert len(load_transactions(conn, user_id=1)) == 1
    finally:
        conn.close()
