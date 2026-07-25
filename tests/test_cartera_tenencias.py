"""Tests del import de Tenencias del broker (Fase 3a).

El export de movimientos no alcanza para reconstruir la cartera: los pagarés
no traen cantidad y los ajustes de ratio de CEDEAR no generan movimiento. Esta
foto del custodio completa esas posiciones y habilita la reconciliación.
"""

from __future__ import annotations

from datetime import date

import pytest

from core import db as core_db
from core.db import connect, init_db
from places.inversiones.cartera.posiciones import Posicion
from places.inversiones.cartera.tenencias import (
    comparar_con_movimientos,
    guardar_foto,
    parse_filas_tenencias,
    ultima_foto,
)


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


# Estructura real del export de inviu (bloques por tipo de activo).
FILAS = [
    [None],
    ["Fecha de solicitud:", "23/07/2026 20:06:13", None, None, "Comitente:", "806156"],
    ["Fecha de valuación:", "24/07/2026"],
    ["TC USD MEP:", 1519.725],
    ["TC USD CCL:", 1585.63],
    [None],
    ["Tenencias en Portfolio"],
    [None],
    ["Tipo de Activo: Moneda"],
    ["Ticker", "Nombre", "Cantidad", "Garantía", "Disponibles", "Moneda",
     "Precio actual", "Monto $", "Equivalente U$S", "Costo (PPC)"],
    ["ARS", "Pesos", None, 0.0, 26068.54, "ARS", 1.0, None, None, 0.0],
    ["USD", "Dólar", None, 0.0, 54.51, "ARS", 1519.725, None, None, 0.0],
    [None],
    ["Tipo de Activo: Bonos"],
    ["Ticker", "Nombre", "Cantidad", "Garantía", "Disponibles", "Moneda",
     "Precio actual", "Monto $", "Equivalente U$S", "Costo (PPC)"],
    ["AE38", "Bono USD 2038", None, 0.0, 3604.0, "ARS", 1262.6, None, None, 586.65],
    [None],
    ["Tipo de Activo: Cheques, Pagaré, Factura"],
    ["Ticker", "Nombre", "Cantidad", "Garantía", "Disponibles", "Moneda",
     "Precio actual", "Monto $", "Equivalente U$S", "Costo (PPC)"],
    ["#UMV060770008", "#UMV060770008", None, 0.0, 5500.0, "ARS", 1480.86,
     None, None, 0.0],
]


def test_parsea_cabecera_y_tipos_de_cambio():
    foto = parse_filas_tenencias(FILAS)
    assert foto.fecha_valuacion == date(2026, 7, 24)
    assert foto.mep == pytest.approx(1519.725)
    assert foto.ccl == pytest.approx(1585.63)


def test_separa_efectivo_de_posiciones():
    foto = parse_filas_tenencias(FILAS)
    assert foto.efectivo_ars == pytest.approx(26068.54)
    assert foto.efectivo_usd == pytest.approx(54.51)
    assert {p.ticker for p in foto.posiciones} == {"AE38", "#UMV060770008"}


def test_lee_el_pagare_que_los_movimientos_no_pueden_derivar():
    """El caso que motivó este módulo: 'Compra cheque' no trae cantidad."""
    foto = parse_filas_tenencias(FILAS)
    pagare = next(p for p in foto.posiciones if p.ticker == "#UMV060770008")
    assert pagare.cantidad == 5500.0
    assert pagare.precio == pytest.approx(1480.86)
    assert pagare.tipo_activo == "Cheques, Pagaré, Factura"
    assert pagare.valor == pytest.approx(8144730.0)


def test_totales_incluyen_efectivo():
    foto = parse_filas_tenencias(FILAS)
    esperado = 3604 * 1262.6 + 5500 * 1480.86 + 26068.54 + 54.51 * 1519.725
    assert foto.total_ars() == pytest.approx(esperado)
    assert foto.total_usd() == pytest.approx(esperado / 1519.725)


def test_guardar_y_recuperar_foto(db):
    foto = parse_filas_tenencias(FILAS)
    assert guardar_foto(db, foto, user_id=1) == 2
    leida = ultima_foto(db, user_id=1)
    assert leida is not None
    assert leida.fecha_valuacion == date(2026, 7, 24)
    assert leida.cantidades == {"AE38": 3604.0, "#UMV060770008": 5500.0}
    assert leida.efectivo_usd == pytest.approx(54.51)


def test_reimportar_la_misma_fecha_no_duplica(db):
    foto = parse_filas_tenencias(FILAS)
    guardar_foto(db, foto, user_id=1)
    guardar_foto(db, foto, user_id=1)
    n = db.execute(
        "SELECT COUNT(*) c FROM cartera_tenencia WHERE user_id = 1"
    ).fetchone()["c"]
    assert n == 2


def test_reconciliacion_detecta_diferencias():
    foto = parse_filas_tenencias(FILAS)
    posiciones = {
        "AE38": Posicion("AE38", cant_comprada=3604.0),      # coincide
        "SPY": Posicion("SPY", cant_comprada=35.0),          # el broker no lo trae
    }
    difs = {d["ticker"]: d for d in comparar_con_movimientos(foto, posiciones)}
    assert "AE38" not in difs                                # sin diferencia
    assert difs["#UMV060770008"]["diferencia"] == 5500.0     # solo en el broker
    assert difs["SPY"]["diferencia"] == -35.0                # solo en movimientos


def test_la_cantidad_del_broker_manda_sobre_los_movimientos():
    p = Posicion("SPY", cant_comprada=35.0)
    assert p.cant_actual == 35.0
    p.cant_broker = 105.0          # ajuste de ratio: el broker sabe la verdad
    assert p.cant_actual == 105.0


def test_sin_dato_del_broker_se_usa_lo_derivado():
    """El Bitcoin no está en el broker: su posición sale de los movimientos."""
    p = Posicion("BITCOIN", cant_comprada=0.003)
    assert p.cant_broker is None
    assert p.cant_actual == pytest.approx(0.003)
