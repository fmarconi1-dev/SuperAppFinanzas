"""Conciliación con el extracto de la caja (Fase D, paso 4, ADR-0009).

De punta a punta por `comandos`: el Excel llega como archivo, se arma la
propuesta, Franco contesta y con el `ok` se aplica el lote. Lo que más
importa: **cada gasto queda una sola vez**. Excel sintéticos, nombres
inventados; el corte es el 17/10/2026, como en producción.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import core.db as core_db
from core.api.archivos import ArchivoRecibido
from core.context import set_current_workspace_id
from core.db import connect, init_db
from places.finanzas.core.comandos import ZONA, procesar, procesar_archivo, totales_mes
from places.finanzas.core.transactions import insert_transaction
from tests.test_extracto_galicia import armar_extracto

UID = 1
AHORA = datetime(2026, 11, 18, 12, 0, tzinfo=ZONA)
SALDO = "153263,01"

CATEGORIAS = [
    ("Compras", "Gasto Variable"), ("Salidas", "Gasto Variable"), ("Auto", "Gasto Fijo"),
    ("Transportes", "Gasto Variable"), ("Servicios", "Gasto Fijo"), ("Impuestos", "Gasto Fijo"),
    ("Haberes SBT", "Ingreso"), ("Otros ingresos", "Ingreso"), ("Compra Divisa", "Inversion"),
    ("Venta divisa", "Ingreso"), ("Inversiones", "Inversion"),
    ("Ajuste Reconciliación", "Gasto Variable"),
]

COMPRA = "COMPRA DEBITO\n{}\n4517XXXXXXXXXX12\nA123"
FIMA = "SUSCRIPCION FIMA\nFIMA PREMIUM CLASE A\nNro Operacion: 1"
PROPIA = "TRANSF. CTAS PROPIAS\nFRANCO INVENTADO\n20999999990\nVARIOS"
TERCEROS = "TRANSFERENCIA DE TERCEROS\nAMIGA INVENTADA\n27111111110\nVARIOS"
A_TERCEROS = "TRANSFERENCIA A TERCEROS\nPLOMERO INVENTADO\n20222222220\nVARIOS\nBANCO X"


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
    for motivo, grupo in CATEGORIAS:
        insert_transaction(conn, fecha=date(2026, 9, 1), motivo=motivo, pasivos=1, user_id=UID)
        conn.execute("UPDATE categorias SET grupo = ? WHERE motivo = ?", (grupo, motivo))
    conn.execute("DELETE FROM transacciones")
    # El ajuste inicial que cargó Franco el 18/10/2026 (la hora es la de la base: UTC).
    _cargar(conn, date(2026, 10, 18), "Ajuste Reconciliación", ingresos=82758.25,
            creado_en="2026-10-18 21:00:00")
    yield conn
    set_current_workspace_id(None)
    conn.close()


def _cargar(conn, fecha, motivo, *, pasivos=0.0, ingresos=0.0, creado_en=None):
    txn = insert_transaction(conn, fecha=fecha, motivo=motivo, pasivos=pasivos,
                             ingresos=ingresos, user_id=UID)
    if creado_en:
        conn.execute("UPDATE transacciones SET creado_en = ? WHERE id = ?", (creado_en, txn))
    return txn


def _mandar(conn, datos, cuando=AHORA):
    return procesar_archivo(conn, ArchivoRecibido(tipo="xlsx", datos=datos,
                                                  nombre="galicia.xlsx"),
                            user_id=UID, ahora=cuando)


def _p(conn, texto, cuando=AHORA):
    return procesar(conn, texto, user_id=UID, ahora=cuando)


def _q(conn, sql, *params) -> list[tuple]:
    """Las filas como tuplas (sqlite3.Row no se compara con una tupla)."""
    return [tuple(r) for r in conn.execute(sql, params)]


def _saldo_app(conn) -> float:
    r = conn.execute("SELECT COALESCE(SUM(ingresos - pasivos), 0) FROM transacciones").fetchone()
    return round(r[0], 2)


def _txns(conn):
    return [dict(r) for r in conn.execute(
        "SELECT id, fecha, pasivos, ingresos, motivo, comentario FROM transacciones "
        "WHERE motivo != 'Ajuste Reconciliación' OR fecha != '2026-10-18' ORDER BY id")]


def _extracto(movimientos):
    """Siempre con un movimiento del 16/10 adelante: el ancla, antes del corte."""
    return armar_extracto([("16/10/2026", COMPRA.format("KIOSCO INVENTADO"), -100)]
                          + movimientos, saldo_inicial=SALDO)


# ---------------------------------------------------------------- el punto de partida

def test_un_extracto_anterior_al_corte_es_el_punto_de_partida(db):
    r = _mandar(db, armar_extracto([("15/10/2026", COMPRA.format("X"), -1000),
                                    ("16/10/2026", COMPRA.format("Y"), -2000)],
                                   saldo_inicial=SALDO))
    assert r.resultado == "pendiente" and "Punto de partida" in r.texto
    assert "$150.263,01 el 16/10/2026" in r.texto
    assert _p(db, "ok").resultado == "lote"
    assert _q(db, "SELECT parte, fecha, monto FROM saldos_declarados") == [
        ("caja", "2026-10-16", 15026301)]
    assert _txns(db) == []                       # nada anterior al corte se carga


def test_sin_ancla_y_sin_nada_antes_del_corte_no_arranca(db):
    r = _mandar(db, armar_extracto([("20/10/2026", COMPRA.format("X"), -1000)]))
    assert r.resultado == "rechazado" and "antes del 17/10/2026" in r.texto


@pytest.mark.skipif(not sorted((Path(__file__).resolve().parents[1] / "data" / "extractos")
                               .glob("galicia-caja-ahorro-*.xlsx")) if (
        Path(__file__).resolve().parents[1] / "data" / "extractos").is_dir() else True,
    reason="sin el extracto de Franco (data/extractos)")
def test_el_extracto_real_es_el_punto_de_partida(db):
    """El de Franco termina el 16/10: todo es anterior al corte y solo deja el ancla."""
    real = sorted((Path(__file__).resolve().parents[1] / "data" / "extractos")
                  .glob("galicia-caja-ahorro-*.xlsx"))[0]
    r = _mandar(db, real.read_bytes())
    assert "la caja tenía $153.263,01 el 16/10/2026" in r.texto
    _p(db, "ok")
    assert _txns(db) == []


# ---------------------------------------------------------------- lo que falta

def test_lo_que_falta_se_propone_con_su_categoria(db):
    r = _mandar(db, _extracto([
        ("20/10/2026", COMPRA.format("FERRETERIA INVENTADA"), -41200),
        ("21/10/2026", "PAGO EN TRANSPORTE\nSUBTE INVENTADO\n4517XXXX\nA1", -1100),
        ("22/10/2026", "IVA", -150),
        ("23/10/2026", "DEP.EFVO.AUTOSERVICIO TICKET:  12345", 300000),
        ("24/10/2026", FIMA, -50000),
        ("25/10/2026", "PAGO TARJETA VISA\nOPERACION 1", -80000),
    ]))
    t = r.texto
    assert "Faltan" in t
    assert "1. 20/10 Compra Debito · FERRETERIA INVENTADA $41.200 → ¿categoría?" in t
    assert "Pago En Transporte · SUBTE INVENTADO $1.100 → Transportes" in t
    assert "Iva $150 → Impuestos" in t
    assert "+$300.000 → Haberes SBT" in t
    assert "Internos 1 (FIMA y cajero)" in t
    assert "Esperando el resumen: 25/10 Pago Tarjeta Visa $80.000" in t
    # Sin la categoría de la 1, el ok no aplica.
    r = _p(db, "ok")
    assert r.resultado == "pendiente" and "Me falta la categoría de: 1" in r.texto
    r = _p(db, "1 compras, ok")
    assert r.resultado == "lote" and "cargué 4" in r.texto
    assert [(t["motivo"], t["pasivos"], t["ingresos"]) for t in _txns(db)] == [
        ("Compras", 41200.0, 0.0), ("Transportes", 1100.0, 0.0), ("Impuestos", 150.0, 0.0),
        ("Haberes SBT", 0.0, 300000.0)]
    # El FIMA no se carga y el pago de la tarjeta espera su resumen.
    estados = dict(_q(db, "SELECT tipo, estado FROM banco_filas"))
    assert estados["SUSCRIPCION FIMA"] == "interna"
    assert estados["PAGO TARJETA VISA"] == "esperando_resumen"


def test_aprende_la_categoria_del_comercio(db):
    _mandar(db, _extracto([("20/10/2026", COMPRA.format("FERRETERIA INVENTADA"), -41200)]))
    _p(db, "1 compras, ok")
    r = _mandar(db, _extracto([
        ("20/10/2026", COMPRA.format("FERRETERIA INVENTADA"), -41200),
        ("02/11/2026", COMPRA.format("FERRETERIA INVENTADA"), -9000),
    ]))
    assert "FERRETERIA INVENTADA $9.000 → Compras" in r.texto


def test_transferencias_a_terceros_aprenden_por_destinatario(db):
    _mandar(db, _extracto([("20/10/2026", A_TERCEROS, -30000)]))
    r = _p(db, "1 servicios, ok")
    assert r.resultado == "lote"
    r = _mandar(db, _extracto([("20/10/2026", A_TERCEROS, -30000),
                               ("05/11/2026", A_TERCEROS, -32000)]))
    assert "PLOMERO INVENTADO $32.000 → Servicios" in r.texto


def test_un_tipo_desconocido_se_pregunta_y_se_recuerda(db):
    _mandar(db, _extracto([("20/10/2026", "MOVIMIENTO NUNCA VISTO", -5000)]))
    _p(db, "1 salidas, ok")
    assert _q(db, "SELECT tipo, tratamiento FROM reglas_tipo") == [
        ("MOVIMIENTO NUNCA VISTO", "movimiento")]


def test_la_percepcion_del_30_va_a_la_linea_neutra(db):
    _mandar(db, _extracto([("20/10/2026", "PERCEPCION RG 5617/24", -30000)]))
    assert _p(db, "ok").resultado == "lote"
    assert _q(db, "SELECT grupo FROM categorias WHERE motivo = ?",
              "Percepción 30% (se devuelve)") == [("Flujo Capital",)]
    t = totales_mes(db, user_id=UID, hoy=date(2026, 10, 31))
    assert t.gastos == 0 and t.sin_categorizar == 0       # no es gasto


def test_un_credito_de_terceros_en_una_categoria_de_gasto_es_devolucion(db):
    _mandar(db, _extracto([("20/10/2026", TERCEROS, 12000)]))
    _p(db, "1 salidas, ok")
    assert [(t["motivo"], t["pasivos"], t["ingresos"]) for t in _txns(db)] == [
        ("Salidas", -12000.0, 0.0)]


def test_n_no_no_carga_esa_fila(db):
    _mandar(db, _extracto([("20/10/2026", COMPRA.format("X"), -1000),
                           ("21/10/2026", COMPRA.format("Y"), -2000)]))
    r = _p(db, "1 no, 2 compras, ok")
    assert r.resultado == "lote" and [t["pasivos"] for t in _txns(db)] == [2000.0]


# ---------------------------------------------------------------- emparejar sin duplicar

def test_un_gasto_ya_cargado_no_se_vuelve_a_cargar_y_manda_el_banco(db):
    """El caso real: Auto $50.000,01 el sábado, el banco lo asienta el martes."""
    _cargar(db, date(2026, 10, 24), "Auto", pasivos=50000.01)
    r = _mandar(db, _extracto([("27/10/2026", PROPIA, -50000)]))
    assert "Coinciden 1" in r.texto
    assert "= Auto $50.000,01 (24/10) → lo corrijo a $50.000" in r.texto
    _p(db, "ok")
    assert [(t["motivo"], t["pasivos"]) for t in _txns(db)] == [("Auto", 50000.0)]


def test_fuera_de_la_ventana_no_se_empareja(db):
    _cargar(db, date(2026, 10, 20), "Auto", pasivos=50000)    # 7 días antes: no
    r = _mandar(db, _extracto([("27/10/2026", PROPIA, -50000)]))
    assert "Coinciden" not in r.texto and "¿categoría?" in r.texto


def test_gana_la_fecha_mas_cercana(db):
    lejos = _cargar(db, date(2026, 10, 22), "Salidas", pasivos=8000)
    cerca = _cargar(db, date(2026, 10, 25), "Salidas", pasivos=8000)
    _mandar(db, _extracto([("26/10/2026", COMPRA.format("BAR INVENTADO"), -8000)]))
    _p(db, "ok")
    emp = _q(db, "SELECT transaccion_id FROM emparejamientos WHERE rol = 'mismo'")
    assert emp == [(cerca,)] and lejos != cerca


def test_un_empate_se_pregunta(db):
    a = _cargar(db, date(2026, 10, 24), "Salidas", pasivos=8000)
    b = _cargar(db, date(2026, 10, 28), "Compras", pasivos=8000)
    r = _mandar(db, _extracto([("26/10/2026", COMPRA.format("BAR INVENTADO"), -8000)]))
    assert f"puede ser #{a} Salidas $8.000 (24/10) o #{b} Compras $8.000 (28/10)" in r.texto
    r = _p(db, f"1 es {b}, ok")
    assert r.resultado == "lote"
    assert _q(db, "SELECT transaccion_id FROM emparejamientos WHERE rol = 'mismo'") == [(b,)]
    assert len(_txns(db)) == 2                   # no cargó otro


def test_rechazar_un_emparejamiento_lo_pasa_a_faltar(db):
    _cargar(db, date(2026, 10, 24), "Auto", pasivos=50000.01)
    _mandar(db, _extracto([("27/10/2026", PROPIA, -50000)]))
    r = _p(db, "1 no")                          # el corregido es el 1 de "Revisá"
    assert "→ ¿categoría?" in r.texto


def test_reimportar_no_duplica(db):
    _cargar(db, date(2026, 10, 24), "Auto", pasivos=50000)
    datos = _extracto([("20/10/2026", COMPRA.format("X"), -1000), ("27/10/2026", PROPIA, -50000)])
    _mandar(db, datos)
    _p(db, "1 compras, ok")
    antes = _txns(db)
    r = _mandar(db, datos)
    assert r.resultado == "rechazado" and "Ya tenía todo este extracto" in r.texto
    assert _txns(db) == antes


def test_un_extracto_que_no_empalma_se_rechaza(db):
    _mandar(db, _extracto([("20/10/2026", COMPRA.format("X"), -1000)]))
    _p(db, "1 compras, ok")
    salteado = armar_extracto([("05/11/2026", COMPRA.format("Y"), -2000)], saldo_inicial="1,00")
    r = _mandar(db, salteado)
    assert r.resultado == "rechazado" and "no empalma" in r.texto and "desde el 21/10" in r.texto


def test_el_extracto_siguiente_empalma(db):
    _mandar(db, _extracto([("20/10/2026", COMPRA.format("X"), -1000)]))
    _p(db, "1 compras, ok")
    # El siguiente arranca donde terminó el anterior (con una fila repetida, como pasa).
    siguiente = armar_extracto([("20/10/2026", COMPRA.format("X"), -1000),
                                ("03/11/2026", COMPRA.format("Y"), -2000)],
                               saldo_inicial="153163,01")
    r = _mandar(db, siguiente)
    assert "empalma con lo que ya tenía" in r.texto and "1 movimientos nuevos" in r.texto


# ---------------------------------------------------------------- la regla del corte

def test_la_regla_del_corte(db):
    """Un gasto cargado antes del ajuste que el banco asienta después del corte:
    ya estaba en el ajuste, así que se descuenta de él."""
    _cargar(db, date(2026, 10, 16), "Compras", pasivos=40000, creado_en="2026-10-16 20:00:00")
    saldo_antes = _saldo_app(db)
    r = _mandar(db, _extracto([("19/10/2026", COMPRA.format("SUPER INVENTADO"), -40000)]))
    assert "ya estaba en el ajuste inicial: lo descuento del ajuste" in r.texto
    _p(db, "ok")
    reversion = _q(db, "SELECT motivo, fecha, ingresos FROM transacciones "
                       "WHERE comentario LIKE 'Regla del corte%'")
    assert reversion == [("Ajuste Reconciliación", "2026-10-19", -40000.0)]
    assert _saldo_app(db) == round(saldo_antes - 40000, 2)       # bajó con el banco
    t = totales_mes(db, user_id=UID, hoy=date(2026, 10, 31))
    assert t.gastos == 40000.0                                    # el gasto, una sola vez


def test_un_gasto_cargado_despues_del_ajuste_no_tiene_regla_del_corte(db):
    _cargar(db, date(2026, 10, 18), "Compras", pasivos=40000, creado_en="2026-10-18 22:00:00")
    r = _mandar(db, _extracto([("19/10/2026", COMPRA.format("SUPER INVENTADO"), -40000)]))
    assert "ajuste inicial" not in r.texto


def test_sin_ajuste_inicial_no_adivina(db):
    db.execute("DELETE FROM transacciones WHERE motivo = 'Ajuste Reconciliación'")
    _cargar(db, date(2026, 10, 16), "Compras", pasivos=40000)
    r = _mandar(db, _extracto([("19/10/2026", COMPRA.format("SUPER INVENTADO"), -40000)]))
    assert r.resultado == "rechazado" and "no encuentro el ajuste inicial" in r.texto


# ---------------------------------------------------------------- devoluciones y bruto

def test_las_devoluciones_de_un_gasto_con_cuenta_no_se_cargan(db):
    """150000-25000*5: se cargan $25.000 y las cinco transferencias son devoluciones."""
    r = _p(db, "20/10, 150000-25000*5, compras", cuando=datetime(2026, 10, 20, 12, tzinfo=ZONA))
    assert r.resultado == "cargado"
    r = _mandar(db, _extracto([("21/10/2026", TERCEROS, 25000)] * 5))
    assert r.texto.count("devolución de Compras $25.000 (20/10): no se carga") == 5
    _p(db, "ok")
    assert [(t["motivo"], t["pasivos"]) for t in _txns(db)] == [("Compras", 25000.0)]


def test_una_sexta_transferencia_ya_no_es_devolucion(db):
    _p(db, "20/10, 150000-25000*5, compras", cuando=datetime(2026, 10, 20, 12, tzinfo=ZONA))
    r = _mandar(db, _extracto([("21/10/2026", TERCEROS, 25000)] * 6))
    assert r.texto.count("devolución de Compras") == 5 and "¿categoría?" in r.texto


def test_el_bruto_se_empareja_con_la_fila_del_banco(db):
    _p(db, "20/10, 60000/3, salidas", cuando=datetime(2026, 10, 20, 12, tzinfo=ZONA))
    r = _mandar(db, _extracto([("21/10/2026", COMPRA.format("PARRILLA INVENTADA"), -60000)]))
    assert "(por lo que pagaste en el momento)" in r.texto
    _p(db, "ok")
    assert [(t["motivo"], t["pasivos"]) for t in _txns(db)] == [("Salidas", 20000.0)]


# ---------------------------------------------------------------- lo que sobra

def test_lo_que_sobra_es_efectivo_salvo_que_digas_tarjeta(db):
    efectivo = _cargar(db, date(2026, 10, 25), "Salidas", pasivos=8000)
    tarjeta = _cargar(db, date(2026, 10, 26), "Compras", pasivos=9000)
    cola = _cargar(db, date(2026, 11, 14), "Salidas", pasivos=500)       # últimos 5 días
    r = _mandar(db, _extracto([("15/11/2026", COMPRA.format("X"), -1000)]))
    assert "Sobran" in r.texto
    assert "Salidas $8.000 (25/10) → efectivo" in r.texto
    assert "1 gasto(s) de los últimos días esperan al próximo extracto" in r.texto
    n_tarjeta = next(l for l in r.texto.splitlines() if "Compras $9.000" in l).split(".")[0]
    _p(db, f"1 compras, {n_tarjeta} tarjeta, ok")
    roles = dict(_q(db, "SELECT transaccion_id, rol FROM emparejamientos "
                        "WHERE banco_fila_id IS NULL"))
    assert roles == {efectivo: "efectivo", tarjeta: "tarjeta"} and cola not in roles


def test_un_pago_tarjeta_cargado_a_mano_no_es_efectivo(db):
    _cargar(db, date(2026, 10, 25), "Pago tarjeta", pasivos=80000)
    r = _mandar(db, _extracto([("15/11/2026", COMPRA.format("X"), -1000)]))
    assert "Pago tarjeta $80.000 (25/10) → sin decidir" in r.texto


def test_venta_divisa_y_su_gasto_no_sobran(db):
    _cargar(db, date(2026, 10, 25), "Venta divisa", ingresos=56600)
    _cargar(db, date(2026, 10, 25), "Viajes", pasivos=56600)
    r = _mandar(db, _extracto([("15/11/2026", COMPRA.format("X"), -1000)]))
    assert "Sobran" not in r.texto


def test_un_efectivo_que_aparece_en_el_banco_deja_de_ser_efectivo(db):
    gasto = _cargar(db, date(2026, 10, 25), "Salidas", pasivos=8000)
    _mandar(db, _extracto([("15/11/2026", COMPRA.format("X"), -1000)]))
    _p(db, "1 compras, ok")                         # el de Salidas quedó como efectivo
    siguiente = armar_extracto([("15/11/2026", COMPRA.format("X"), -1000),
                                ("16/11/2026", COMPRA.format("BAR"), -8000)],
                               saldo_inicial="153163,01")
    # Fuera de la ventana (25/10 vs 16/11) no se empareja: queda como efectivo.
    assert "Coinciden" not in _mandar(db, siguiente).texto
    _p(db, "cancelar")
    db.execute("UPDATE transacciones SET fecha = '2026-11-14' WHERE id = ?", (gasto,))
    r = _mandar(db, siguiente)
    assert "Coinciden 1" in r.texto
    _p(db, "ok")
    assert _q(db, "SELECT rol, era_efectivo FROM emparejamientos WHERE transaccion_id = ?",
              gasto) == [("mismo", 1)]


# ---------------------------------------------------------------- cada gasto una sola vez

def test_cada_gasto_una_sola_vez(db):
    """El escenario mezclado: gasto por WhatsApp y su fila, devoluciones contra el
    bruto, la regla del corte y un reimporte. Ningún gasto queda dos veces."""
    _cargar(db, date(2026, 10, 16), "Compras", pasivos=40000, creado_en="2026-10-16 20:00:00")
    _cargar(db, date(2026, 10, 24), "Auto", pasivos=50000)
    _p(db, "25/10, 150000-25000*5, salidas", cuando=datetime(2026, 10, 25, 12, tzinfo=ZONA))
    datos = _extracto([
        ("19/10/2026", COMPRA.format("SUPER INVENTADO"), -40000),     # regla del corte
        ("26/10/2026", COMPRA.format("PARRILLA INVENTADA"), -150000),  # el bruto
        ("26/10/2026", PROPIA, -50000),                                # el Auto
        ("27/10/2026", TERCEROS, 25000), ("27/10/2026", TERCEROS, 25000),
        ("28/10/2026", COMPRA.format("FERRETERIA INVENTADA"), -7000),  # nuevo
    ])
    _mandar(db, datos)
    assert _p(db, "1 compras, ok").resultado == "lote"
    assert _mandar(db, datos).resultado == "rechazado"                # reimporte: nada
    gastos = sorted((t["motivo"], t["pasivos"]) for t in _txns(db) if t["pasivos"] > 0)
    assert gastos == [("Auto", 50000.0), ("Compras", 7000.0), ("Compras", 40000.0),
                      ("Salidas", 25000.0)]


# ---------------------------------------------------------------- deshacer

def test_deshacer_un_extracto_vuelve_todo_atras(db):
    auto = _cargar(db, date(2026, 10, 24), "Auto", pasivos=50000.01)
    _mandar(db, _extracto([("20/10/2026", COMPRA.format("X"), -1000),
                           ("27/10/2026", PROPIA, -50000)]))
    _p(db, "1 compras, ok")
    r = _p(db, "deshacer", cuando=AHORA + timedelta(minutes=5))
    assert r.resultado == "deshecho" and "volví a como estaban 1" in r.texto
    assert [(t["id"], t["pasivos"]) for t in _txns(db)] == [(auto, 50000.01)]
    for tabla in ("banco_filas", "emparejamientos", "reglas_comercio", "saldos_declarados"):
        assert db.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] == 0, tabla
    # Y se puede volver a importar.
    assert _mandar(db, _extracto([("20/10/2026", COMPRA.format("X"), -1000)])).resultado == \
        "pendiente"
