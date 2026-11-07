"""Corregir lo cargado por chat y la fecha de los haberes de UCEMA (Fase E, paso 3).

Los dos casos de Franco del 6/11/2026: los haberes de UCEMA del 28/10 tienen
que contar para noviembre, y un café de 20.400 fueron 19.400 con tarjeta y
1.000 de propina. Nombres inventados.
"""

from __future__ import annotations

from datetime import date

import pytest

from places.finanzas.core.conciliacion import fecha_contable
from tests.test_conciliacion import (  # noqa: F401 — el fixture `db`
    AHORA, COMPRA, _cargar, _extracto, _mandar, _p, _q, _txns, db)

UCEMA = "TRANSFERENCIAS CASH SUELDOS\nUNIVERSIDAD INVENTADA\n30111111110\nVARIOS"


def _id(db, motivo, monto):
    return db.execute("SELECT id FROM transacciones WHERE motivo = ? AND (pasivos = ? OR "
                      "ingresos = ?)", (motivo, monto, monto)).fetchone()[0]


# ---------------------------------------------------------------- #N fecha

def test_cambiar_la_fecha_y_deshacer(db):
    txn = _cargar(db, date(2026, 10, 28), "Salidas", pasivos=5000)
    r = _p(db, f"#{txn} fecha 02/11")
    assert r.resultado == "lote" and "ahora es del 02/11" in r.texto
    assert _q(db, "SELECT fecha FROM transacciones WHERE id = ?", txn) == [("2026-11-02",)]
    assert _p(db, "deshacer").resultado == "deshecho"
    assert _q(db, "SELECT fecha FROM transacciones WHERE id = ?", txn) == [("2026-10-28",)]


def test_la_misma_fecha_o_un_numero_que_no_existe_no_cambian_nada(db):
    txn = _cargar(db, date(2026, 10, 28), "Salidas", pasivos=5000)
    assert "ya tiene esa fecha" in _p(db, f"#{txn} fecha 28/10").texto
    assert "No encuentro el #99999" in _p(db, "#99999 fecha 02/11").texto


def test_una_edicion_no_descarta_la_conciliacion_abierta(db):
    txn = _cargar(db, date(2026, 10, 28), "Salidas", pasivos=5000)
    _mandar(db, _extracto([("20/10/2026", COMPRA.format("FERRETERIA INVENTADA"), -41200)]))
    _p(db, f"#{txn} fecha 01/11")
    assert "Me falta la categoría de: 1" in _p(db, "ok").texto       # la propuesta sigue


# ---------------------------------------------------------------- partir

def test_partir_el_cafe_y_la_propina(db):
    """Franco cargó «19400+1000, salidas»: la tarjeta trae 19.400 y la propina fue efectivo."""
    _p(db, "19400+1000, salidas")
    txn = _id(db, "Salidas", 20400)
    r = _p(db, f"partir #{txn} 19400 + 1000 propina")
    assert r.resultado == "lote" and "Partí" in r.texto
    assert sorted((t["pasivos"], t["comentario"]) for t in _txns(db)) == [
        (1000.0, "propina"), (19400.0, None)]
    # La cuenta guardada ya no es "19400+1000": la conciliación busca 19.400.
    assert _q(db, "SELECT cuenta, bruto FROM gasto_cuentas WHERE transaccion_id = ?", txn) == [
        ("19400", 19400.0)]
    assert _p(db, "deshacer").resultado == "deshecho"
    assert [t["pasivos"] for t in _txns(db)] == [20400.0]
    assert _q(db, "SELECT cuenta, bruto FROM gasto_cuentas WHERE transaccion_id = ?", txn) == [
        ("19400+1000", 20400.0)]


def test_la_conciliacion_encuentra_la_parte_de_la_tarjeta(db):
    txn = _cargar(db, date(2026, 10, 25), "Salidas", pasivos=20400)
    _p(db, f"partir #{txn} 19400 + 1000 propina")
    r = _mandar(db, _extracto([("26/10/2026", COMPRA.format("CAFE INVENTADO"), -19400)]))
    assert "Coinciden 1" in r.texto


@pytest.mark.parametrize("orden,error", [
    ("partir #{id} 19000 + 1000", "suman $20.000"),
    ("partir #{id} 20400", "al menos dos montos"),
    ("partir #{id} 20400 + 0", "mayor que cero"),
])
def test_partir_mal_no_cambia_nada(db, orden, error):
    txn = _cargar(db, date(2026, 10, 25), "Salidas", pasivos=20400)
    r = _p(db, orden.format(id=txn))
    assert error in r.texto and [t["pasivos"] for t in _txns(db)] == [20400.0]


# ---------------------------------------------------------------- la fecha de UCEMA

@pytest.mark.parametrize("motivo,fecha,esperada", [
    ("Haberes UCEMA", date(2026, 10, 28), date(2026, 11, 2)),   # el 1/11 es domingo
    ("Haberes UCEMA", date(2026, 10, 24), date(2026, 10, 24)),  # antes del 25, queda
    ("Haberes UCEMA", date(2026, 12, 30), date(2027, 1, 1)),    # cambia el año (viernes)
    ("Haberes SBT", date(2026, 10, 28), date(2026, 10, 28)),    # otra categoría, queda
    (None, date(2026, 10, 28), date(2026, 10, 28)),
])
def test_fecha_contable(motivo, fecha, esperada):
    assert fecha_contable(motivo, fecha) == esperada


def _con_categoria_ucema(db):
    _cargar(db, date(2026, 9, 1), "Haberes UCEMA", ingresos=1)
    db.execute("UPDATE categorias SET grupo = 'Ingreso' WHERE motivo = 'Haberes UCEMA'")
    db.execute("DELETE FROM transacciones WHERE motivo = 'Haberes UCEMA'")


def test_los_haberes_de_ucema_de_fin_de_mes_se_cargan_el_mes_siguiente(db):
    _con_categoria_ucema(db)
    r = _mandar(db, _extracto([("28/10/2026", UCEMA, 404625)]))
    assert "(cuenta para el 02/11)" not in r.texto          # todavía sin categoría
    r = _p(db, "1 haberes ucema")
    assert "Haberes UCEMA (cuenta para el 02/11)" in r.texto
    _p(db, "ok")
    assert _q(db, "SELECT fecha, ingresos FROM transacciones WHERE motivo = 'Haberes UCEMA'") == [
        ("2026-11-02", 404625.0)]
    # El banco sigue diciendo su fecha.
    assert _q(db, "SELECT fecha FROM banco_filas WHERE monto = 40462500") == [("2026-10-28",)]


def test_partir_algo_conciliado_se_rechaza(db):
    """La fila del banco quedaría atada a un monto menor y la parte nueva saldría como
    un sobrante tomado por efectivo."""
    _mandar(db, _extracto([("20/10/2026", COMPRA.format("CAFE INVENTADO"), -20400)]))
    _p(db, "1 salidas, ok")
    txn = _txns(db)[0]["id"]
    r = _p(db, f"partir #{txn} 19400 + 1000 propina")
    assert "ya está conciliado con el banco" in r.texto
    assert [t["pasivos"] for t in _txns(db)] == [20400.0]


def test_los_haberes_movidos_no_reaparecen_en_el_extracto_siguiente(db):
    """Conciliados el 28/10 y cargados el 2/11: el extracto que cubre el 2/11 no los
    tiene que mostrar como sobrantes ni emparejar de nuevo."""
    _con_categoria_ucema(db)
    _mandar(db, _extracto([("28/10/2026", UCEMA, 404625)]))
    _p(db, "1 haberes ucema, ok")
    r = _mandar(db, _extracto([("28/10/2026", UCEMA, 404625),
                               ("03/11/2026", COMPRA.format("KIOSCO INVENTADO"), -1500)]))
    assert "Sobran" not in r.texto and "Coinciden" not in r.texto
    assert "1 movimientos nuevos" in r.texto


def test_cargados_a_mano_con_la_fecha_del_mes_siguiente_coinciden(db):
    """Así los cargaba Franco: el 1/10 los de septiembre. No se duplican."""
    _con_categoria_ucema(db)
    _cargar(db, date(2026, 11, 2), "Haberes UCEMA", ingresos=404625)
    r = _mandar(db, _extracto([("28/10/2026", UCEMA, 404625)]))
    assert "Coinciden 1" in r.texto
