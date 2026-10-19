"""Varios gastos en un mensaje = el sistema de lotes (Fase D, paso 2, ADR-0009 §6).

Propone → `ok` → aplica todo o nada (un backup antes) → `deshacer` del lote
entero. Y el **bruto** de los gastos con cuenta (`150000-25000*5` se carga
como $25.000, pero salieron $150.000). Base sintética, sin red.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

import core.db as core_db
from core.context import set_current_workspace_id
from core.db import connect, init_db
from places.finanzas.core import comandos, lotes
from places.finanzas.core.comandos import ZONA, bruto_de_cuenta, procesar
from places.finanzas.core.transactions import delete_transaction, insert_transaction

UID = 1
AHORA = datetime(2026, 10, 19, 12, 0, tzinfo=ZONA)


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
    for motivo, grupo in [("Supermercado", "Gasto Variable"), ("Nafta", "Gasto Variable"),
                          ("Salidas", "Gasto Variable"), ("Sueldo", "Ingreso"),
                          ("Transportes", "Gasto Variable")]:
        insert_transaction(conn, fecha=date(2026, 9, 1), motivo=motivo, pasivos=1, user_id=UID)
        conn.execute("UPDATE categorias SET grupo = ? WHERE motivo = ?", (grupo, motivo))
    conn.execute("DELETE FROM transacciones")
    yield conn
    set_current_workspace_id(None)
    conn.close()


def _p(conn, texto, cuando=AHORA):
    return procesar(conn, texto, user_id=UID, ahora=cuando)


def _registrar(conn, wamid, r, cuando):
    """Lo que hace el servidor después de `procesar`."""
    conn.execute(
        "INSERT INTO whatsapp_mensajes (wamid, recibido_en, remitente, texto, transaccion_id, "
        "resultado) VALUES (?, ?, '541100000000', '', ?, ?)",
        (wamid, cuando.isoformat(), r.transaccion_id, r.resultado),
    )


def _txns(conn):
    return [dict(r) for r in conn.execute(
        "SELECT fecha, pasivos, ingresos, motivo, comentario FROM transacciones ORDER BY id")]


def _cuentas(conn):
    return [dict(r) for r in conn.execute(
        "SELECT cuenta, bruto FROM gasto_cuentas ORDER BY transaccion_id")]


TRES = "2500, super\n13/10, 30.000, nafta, YPF\n60000-15000*3, salidas"


# ---------------------------------------------------------------- el bruto

@pytest.mark.parametrize("cuenta, bruto", [
    ("150000-25000*5", 150000.0),   # el caso real del 16/10/2026
    ("100-50", 100.0),
    ("12.000/3", 12000.0),          # pagó todo y lo dividen entre tres
    ("3x2.500", 7500.0),            # nadie devuelve nada
    ("2500+1500", 4000.0),
    ("1000+500*2-300", 2000.0),     # "antes del primer −", no "el primer número"
    ("$25.000-5.000", 25000.0),
])
def test_el_bruto_es_lo_que_esta_antes_del_primer_menos(cuenta, bruto):
    assert bruto_de_cuenta(cuenta) == bruto


def test_un_gasto_suelto_con_cuenta_guarda_el_bruto(db):
    r = _p(db, "150000-25000*5, salidas")
    assert r.resultado == "cargado"
    assert _txns(db)[0]["pasivos"] == 25000.0
    assert _cuentas(db) == [{"cuenta": "150000-25000*5", "bruto": 150000.0}]


def test_sin_cuenta_no_hay_bruto(db):
    _p(db, "2500, super")
    assert _cuentas(db) == []


def test_el_bruto_sobrevive_a_la_pregunta_de_categoria(db):
    assert _p(db, "60000/3, regalos").resultado == "pendiente"    # categoría nueva
    assert _p(db, "sí").resultado == "cargado"
    assert _cuentas(db) == [{"cuenta": "60000/3", "bruto": 60000.0}]


def test_borrar_un_gasto_desde_la_app_se_lleva_su_bruto(db):
    r = _p(db, "100-50, supermercado")
    assert _cuentas(db) != []
    delete_transaction(db, r.transaccion_id, user_id=UID)
    assert _cuentas(db) == []


# ---------------------------------------------------------------- la propuesta

def test_varios_renglones_proponen_y_no_escriben_nada(db):
    r = _p(db, TRES)
    assert r.resultado == "pendiente"
    assert _txns(db) == []
    assert "Te cargo 3:" in r.texto
    assert "1. Supermercado $2.500 (19/10)  ← ¿quisiste decir? (escribiste «super»)" in r.texto
    assert "2. Nafta $30.000 (13/10) · YPF" in r.texto
    assert "3. Salidas $15.000 (19/10) = 60000-15000*3" in r.texto
    assert "Total: gastos $47.500" in r.texto


def test_ok_carga_todo_junto(db):
    _p(db, TRES)
    r = _p(db, "ok")
    assert r.resultado == "lote"
    assert "Cargados 3 (gastos $47.500)" in r.texto and "*deshacer* borra los 3" in r.texto
    assert _txns(db) == [
        {"fecha": "2026-10-19", "pasivos": 2500.0, "ingresos": 0.0, "motivo": "Supermercado",
         "comentario": None},
        {"fecha": "2026-10-13", "pasivos": 30000.0, "ingresos": 0.0, "motivo": "Nafta",
         "comentario": "YPF"},
        {"fecha": "2026-10-19", "pasivos": 15000.0, "ingresos": 0.0, "motivo": "Salidas",
         "comentario": None},
    ]
    assert _cuentas(db) == [{"cuenta": "60000-15000*3", "bruto": 60000.0}]


def test_ok_tambien_con_si(db):
    _p(db, TRES)
    assert _p(db, "Sí").resultado == "lote"


def test_un_ingreso_en_la_lista(db):
    _p(db, "+350000, sueldo\n2500, nafta")
    r = _p(db, "ok")
    assert "ingresos $350.000" in r.texto
    assert _txns(db)[0]["ingresos"] == 350000.0


def test_un_backup_por_lote_y_no_uno_por_fila(db, monkeypatch):
    llamadas = []
    monkeypatch.setattr(lotes, "backup_db", lambda: llamadas.append(1))
    _p(db, TRES)
    _p(db, "ok")
    assert len(llamadas) == 1


def test_todo_o_nada(db, monkeypatch):
    """Si la segunda fila falla, no queda la primera, y la propuesta sigue en pie."""
    _p(db, TRES)
    real = lotes.insertar_sin_backup
    cuantas = []

    def falla_en_la_segunda(*a, **k):
        cuantas.append(1)
        if len(cuantas) == 2:
            raise RuntimeError("disco lleno")
        return real(*a, **k)

    monkeypatch.setattr(lotes, "insertar_sin_backup", falla_en_la_segunda)
    with pytest.raises(RuntimeError):
        _p(db, "ok")
    assert _txns(db) == [] and _cuentas(db) == []
    monkeypatch.setattr(lotes, "insertar_sin_backup", real)
    assert _p(db, "ok").resultado == "lote"
    assert len(_txns(db)) == 3


def test_un_renglon_que_no_se_entiende_frena_todo(db):
    r = _p(db, "2500, super\n2500.50, nafta\n300, salidas")
    assert r.resultado == "rechazado"
    assert "2. «2500.50, nafta»" in r.texto and "No cargué nada" in r.texto
    assert _p(db, "ok").texto == "No tengo nada pendiente de confirmar."
    assert _txns(db) == []


def test_un_mensaje_de_dos_renglones_que_no_es_de_gastos_sigue_como_antes(db):
    r = _p(db, "hola\nqué tal")
    assert r.resultado == "rechazado" and "Te cargo" not in r.texto


# ---------------------------------------------------------------- correcciones

def test_corregir_la_categoria_y_ok_en_el_mismo_mensaje(db):
    _p(db, TRES)
    r = _p(db, "1 transportes, ok")
    assert r.resultado == "lote"
    assert [t["motivo"] for t in _txns(db)] == ["Transportes", "Nafta", "Salidas"]


def test_una_correccion_dudosa_se_muestra_antes_de_cargar(db):
    """"1 trnasportes, ok" no carga a ciegas: muestra la sugerencia y espera."""
    _p(db, TRES)
    r = _p(db, "1 trnasportes, ok")
    assert r.resultado == "pendiente" and "Revisá las marcadas" in r.texto
    assert "1. Transportes $2.500 (19/10)  ← ¿quisiste decir? (escribiste «trnasportes»)" in r.texto
    assert _txns(db) == []
    assert _p(db, "ok").resultado == "lote"
    assert _txns(db)[0]["motivo"] == "Transportes"


def test_corregir_sin_ok_vuelve_a_mostrar(db):
    _p(db, TRES)
    r = _p(db, "2 supermercado")
    assert r.resultado == "pendiente" and "2. Supermercado $30.000" in r.texto
    assert _txns(db) == []


def test_sacar_un_renglon(db):
    _p(db, TRES)
    r = _p(db, "2 no, ok")
    assert r.resultado == "lote" and "Cargados 2" in r.texto
    assert [t["motivo"] for t in _txns(db)] == ["Supermercado", "Salidas"]


def test_sacar_todos_no_carga_nada(db):
    _p(db, "2500, nafta\n300, nafta")
    r = _p(db, "1 no, 2 no, ok")
    assert r.resultado == "rechazado" and _txns(db) == []
    assert _p(db, "ok").texto == "No tengo nada pendiente de confirmar."


@pytest.mark.parametrize("texto", ["cancelar", "no"])
def test_cancelar_descarta_la_propuesta(db, texto):
    _p(db, TRES)
    r = _p(db, texto)
    assert r.resultado == "rechazado" and "descarté la propuesta" in r.texto
    assert _p(db, "ok").texto == "No tengo nada pendiente de confirmar."
    assert _txns(db) == []


# ---------------------------------------------------------------- convivencia

def test_un_gasto_suelto_no_descarta_la_propuesta(db):
    _p(db, TRES)
    assert _p(db, "2.500 nafta").resultado == "cargado"   # 2.500 no es el renglón 2
    assert _p(db, "ok").resultado == "lote"
    assert len(_txns(db)) == 4


def test_un_numero_fuera_de_la_lista_es_un_gasto(db):
    _p(db, TRES)
    assert _p(db, "9 nafta").resultado == "cargado"        # hay 3 renglones, no 9
    assert len(_txns(db)) == 1


def test_el_si_de_un_gasto_suelto_va_primero(db):
    """La pregunta más nueva es la del gasto suelto: su "sí" no aplica el lote."""
    _p(db, TRES)
    assert _p(db, "500, kiosco").resultado == "pendiente"  # categoría nueva
    assert _p(db, "sí").resultado == "cargado"
    assert [t["motivo"] for t in _txns(db)] == ["Kiosco"]
    assert _p(db, "ok").resultado == "lote"


def test_una_propuesta_nueva_reemplaza_a_la_vieja(db):
    _p(db, TRES)
    r = _p(db, "100, nafta\n200, nafta")
    assert "Descarté la propuesta anterior" in r.texto
    _p(db, "ok")
    assert [t["pasivos"] for t in _txns(db)] == [100.0, 200.0]


def test_la_propuesta_vence_a_las_48_horas(db):
    _p(db, TRES)
    r = _p(db, "ok", cuando=AHORA + timedelta(hours=49))
    assert r.texto == "No tengo nada pendiente de confirmar."
    assert _txns(db) == []


def test_a_las_47_horas_todavia_vale(db):
    _p(db, TRES)
    assert _p(db, "ok", cuando=AHORA + timedelta(hours=47)).resultado == "lote"


# ---------------------------------------------------------------- deshacer

def test_deshacer_borra_el_lote_entero(db):
    _p(db, TRES)
    _p(db, "ok")
    r = _p(db, "deshacer", cuando=AHORA + timedelta(minutes=5))
    assert r.resultado == "deshecho" and "Borré los 3 que cargaste juntos" in r.texto
    assert _txns(db) == [] and _cuentas(db) == []


def test_deshacer_va_por_lo_ultimo_gasto_suelto_despues_del_lote(db):
    _p(db, TRES)
    _p(db, "ok")
    suelto = _p(db, "800, nafta", cuando=AHORA + timedelta(minutes=1))
    _registrar(db, "w1", suelto, AHORA + timedelta(minutes=1))
    r = _p(db, "deshacer", cuando=AHORA + timedelta(minutes=2))
    assert f"Borré #{suelto.transaccion_id}" in r.texto
    assert len(_txns(db)) == 3
    # El segundo deshacer va por el lote.
    r = _p(db, "deshacer", cuando=AHORA + timedelta(minutes=3))
    assert "Borré los 3" in r.texto and _txns(db) == []


def test_deshacer_va_por_lo_ultimo_lote_despues_del_gasto_suelto(db):
    suelto = _p(db, "800, nafta", cuando=AHORA - timedelta(minutes=10))
    _registrar(db, "w1", suelto, AHORA - timedelta(minutes=10))
    _p(db, TRES)
    _p(db, "ok")
    assert "Borré los 3" in _p(db, "deshacer", cuando=AHORA + timedelta(minutes=1)).texto
    assert [t["pasivos"] for t in _txns(db)] == [800.0]
    assert f"Borré #{suelto.transaccion_id}" in _p(
        db, "deshacer", cuando=AHORA + timedelta(minutes=2)).texto


def test_un_lote_de_hace_mas_de_24_horas_no_se_deshace(db):
    _p(db, TRES)
    _p(db, "ok")
    r = _p(db, "deshacer", cuando=AHORA + timedelta(hours=25))
    assert r.resultado == "rechazado" and len(_txns(db)) == 3


def test_no_se_deshace_un_lote_que_cambio_desde_la_app(db):
    _p(db, TRES)
    _p(db, "ok")
    editado = db.execute("SELECT id FROM transacciones ORDER BY id LIMIT 1 OFFSET 1").fetchone()[0]
    db.execute("UPDATE transacciones SET pasivos = 31000 WHERE id = ?", (editado,))
    r = _p(db, "deshacer", cuando=AHORA + timedelta(minutes=5))
    assert r.resultado == "rechazado" and f"#{editado} cambió" in r.texto
    assert "No toqué nada" in r.texto
    assert len(_txns(db)) == 3                       # ni siquiera los que no cambiaron


def test_no_se_deshace_un_lote_con_una_fila_borrada_desde_la_app(db):
    _p(db, TRES)
    _p(db, "ok")
    borrado = db.execute("SELECT id FROM transacciones ORDER BY id LIMIT 1").fetchone()[0]
    delete_transaction(db, borrado, user_id=UID)    # la FK no traba el borrado
    r = _p(db, "deshacer", cuando=AHORA + timedelta(minutes=5))
    assert r.resultado == "rechazado" and f"#{borrado} ya no está" in r.texto
    assert len(_txns(db)) == 2


def test_deshacer_hace_backup_antes(db, monkeypatch):
    _p(db, TRES)
    _p(db, "ok")
    llamadas = []
    monkeypatch.setattr(lotes, "backup_db", lambda: llamadas.append(1))
    _p(db, "deshacer", cuando=AHORA + timedelta(minutes=5))
    assert llamadas == [1]


def test_la_ayuda_explica_los_varios_gastos(db):
    texto = _p(db, "ayuda").texto
    assert "Varios gastos: uno por renglón" in texto and "Cuentas: 100-50" in texto
