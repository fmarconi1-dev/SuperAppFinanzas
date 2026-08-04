"""Ajustes de tenencia: lo que el broker no informa.

Los tres casos que dispararon este módulo son **datos reales** de la cartera de
Franco, y los números esperados salen de su Excel:

* **BYMA** — compró 5 a $481 y 4 a $410 (9 unidades, $4.061,15) y vendió 18 por
  $4.053,23. La cantidad se duplicó y el precio cayó a la mitad: un split que
  el export no informa. Con el ajuste, la operación cierra en −$7,92.
* **TXAR** — vendió 300 el 10/7/2025 por $186.751,31 sin ninguna compra
  registrada: las tenía desde antes de que arrancara el historial.
* **GGALX** — vendió 100 cupones por $1.494,01. Llegaron gratis por tener GGAL,
  así que el resultado es la venta entera.

El test que más importa es
:func:`test_saldo_inicial_no_infla_el_patrimonio`: verifica que cargar un costo
no rompa la identidad contable del método del patrimonio (trampa #1).
"""

from __future__ import annotations

from datetime import date

import pytest

from core.db import connect, init_db
from places.inversiones.cartera import ajustes as aj
from places.inversiones.cartera.ledger import (
    Evento, eventos_desde_db, recorrer,
)
from places.inversiones.cartera.posiciones import (
    capital_aportado, flujos_de_capital, posiciones_desde_db,
)

UID = 1


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    init_db(ruta)
    c = connect(ruta)
    c.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) "
        "VALUES (1, 'franco', 'Franco')"
    )
    c.commit()
    yield c
    c.close()


def _mov(conn, fecha, categoria, ticker, cantidad, monto, moneda="ARS", tc=None):
    conn.execute(
        "INSERT INTO cartera_movimientos "
        "(user_id, fecha_concertacion, categoria, descripcion, monto, cantidad, "
        " precio, moneda, ticker_base, es_instrumento, es_espejo, hash_dedupe) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 0, ?)",
        (UID, fecha, categoria, ticker, monto, cantidad, moneda, ticker,
         1 if categoria not in ("DEPOSITO", "RETIRO") else 0,
         f"{fecha}|{categoria}|{ticker}|{monto}|{cantidad}"),
    )
    conn.commit()


def _led(conn):
    return recorrer(eventos_desde_db(conn, UID))


# ---------------------------------------------------------------------------
# Caso BYMA: el split
# ---------------------------------------------------------------------------

def _cargar_byma(conn):
    _mov(conn, "2025-03-06", "COMPRA", "BYMA", 5, -2414.60)
    _mov(conn, "2025-05-16", "COMPRA", "BYMA", 4, -1646.55)
    _mov(conn, "2025-10-27", "VENTA", "BYMA", -18, 4053.23)


def test_sin_ajuste_la_venta_queda_descubierta(conn):
    """El estado previo: se venden 18 con 9 registradas."""
    _cargar_byma(conn)
    led = _led(conn)
    assert any("BYMA" in a and "18" in a for a in led.advertencias)


def test_el_split_cierra_la_venta_completa(conn):
    """Con el split cargado no queda excedente sin costo."""
    _cargar_byma(conn)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT", cantidad=9.0))
    conn.commit()

    led = _led(conn)
    assert not [a for a in led.advertencias if a.startswith("BYMA")]
    r = led.por_ticker("BYMA")[0]
    assert not r.descubierta
    assert r.cantidad == pytest.approx(18.0)


def test_el_split_da_el_resultado_del_excel(conn):
    """−$7,92: casi empate, que es lo que muestra el broker."""
    _cargar_byma(conn)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT", cantidad=9.0))
    conn.commit()

    r = _led(conn).por_ticker("BYMA")[0]
    assert r.resultado_ars == pytest.approx(4053.23 - 4061.15, abs=0.01)


def test_el_split_parte_el_ppc_al_medio(conn):
    """El costo total no cambia: se reparte en el doble de unidades."""
    _mov(conn, "2025-03-06", "COMPRA", "BYMA", 5, -2414.60)
    _mov(conn, "2025-05-16", "COMPRA", "BYMA", 4, -1646.55)
    antes = recorrer(eventos_desde_db(conn, UID)).estados["BYMA"].ppc_ars

    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT", cantidad=9.0))
    conn.commit()
    despues = _led(conn).estados["BYMA"].ppc_ars

    assert despues == pytest.approx(antes / 2)


def test_el_split_no_aporta_capital(conn):
    """No entró plata: no puede figurar como depósito."""
    _cargar_byma(conn)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT", cantidad=9.0))
    conn.commit()
    assert capital_aportado(conn, UID).depositos_ars == pytest.approx(0.0)


def test_el_split_no_cambia_la_fecha_de_compra(conn):
    """Un split no te hace dueño más tarde: el plazo de tenencia se mide
    desde la compra original."""
    _mov(conn, "2025-03-06", "COMPRA", "BYMA", 5, -2414.60)
    antes = recorrer(eventos_desde_db(conn, UID)).estados["BYMA"].fecha_compra_prom

    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT", cantidad=5.0))
    conn.commit()
    assert _led(conn).estados["BYMA"].fecha_compra_prom == antes


# ---------------------------------------------------------------------------
# Caso TXAR: el saldo inicial — y la identidad contable
# ---------------------------------------------------------------------------

COSTO_TXAR = 233_439.14        # despejado de un rendimiento recordado de −20%


def _cargar_txar(conn):
    _mov(conn, "2025-07-10", "VENTA", "TXAR", -300, 186_751.31)


def test_saldo_inicial_da_el_rendimiento_recordado(conn):
    _cargar_txar(conn)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2024, 12, 5), ticker="TXAR", tipo="SALDO_INICIAL",
        cantidad=300.0, costo_ars=COSTO_TXAR, estimado=True))
    conn.commit()

    r = _led(conn).por_ticker("TXAR")[0]
    assert not r.descubierta
    assert r.rendimiento_pct == pytest.approx(-20.0, abs=0.1)


def test_saldo_inicial_no_infla_el_patrimonio(conn):
    """**El test que justifica el depósito sintético.**

    El método del patrimonio es `resultado = tenencia + efectivo − aportes`.
    Vender un papel que ya tenías mete su precio entero en el efectivo. Si
    ese capital no figura como aportado, los $186.751 aparecen como ganancia.

    Se contrasta contra una identidad independiente: el resultado por
    patrimonio tiene que dar lo mismo que el realizado del ledger.
    """
    _cargar_txar(conn)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2024, 12, 5), ticker="TXAR", tipo="SALDO_INICIAL",
        cantidad=300.0, costo_ars=COSTO_TXAR, estimado=True))
    conn.commit()

    cap = capital_aportado(conn, UID)
    efectivo = 186_751.31          # lo que dejó la venta
    tenencia = 0.0                 # se vendió todo
    por_patrimonio = (tenencia + efectivo) - cap.depositos_ars

    por_ledger = _led(conn).realizado_ars
    assert por_patrimonio == pytest.approx(por_ledger, abs=0.01)
    assert por_patrimonio == pytest.approx(-46_687.83, abs=0.5)


def test_sin_el_aporte_el_patrimonio_mentiria(conn):
    """Contraprueba: el mismo cálculo sin depósito sintético da +$186.751 de
    ganancia inventada. Documenta *por qué* existe `aporte_sintetico`."""
    _cargar_txar(conn)
    conn.commit()
    cap = capital_aportado(conn, UID)
    assert (0.0 + 186_751.31) - cap.depositos_ars == pytest.approx(186_751.31)


def test_el_saldo_inicial_entra_a_la_tir_con_su_fecha(conn):
    """Un aporte de diciembre no puede computarse como de julio."""
    _cargar_txar(conn)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2024, 12, 5), ticker="TXAR", tipo="SALDO_INICIAL",
        cantidad=300.0, costo_ars=COSTO_TXAR, estimado=True))
    conn.commit()

    flujos = flujos_de_capital(conn, UID)
    assert (date(2024, 12, 5), -COSTO_TXAR) == (flujos[0][0], pytest.approx(flujos[0][1]))


def test_los_flujos_quedan_ordenados_por_fecha(conn):
    """Los ajustes se agregan al final de la consulta: si no se reordenara,
    la TIR recibiría los flujos desordenados."""
    _mov(conn, "2025-06-01", "DEPOSITO", "CC", 0, 100_000.0)
    _mov(conn, "2026-01-01", "DEPOSITO", "CC", 0, 50_000.0)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2024, 12, 5), ticker="TXAR", tipo="SALDO_INICIAL",
        cantidad=300.0, costo_ars=COSTO_TXAR))
    conn.commit()

    fechas = [f for f, _, _ in flujos_de_capital(conn, UID)]
    assert fechas == sorted(fechas)


# ---------------------------------------------------------------------------
# Caso GGALX: el cupón gratis
# ---------------------------------------------------------------------------

def test_cupon_gratis_es_ganancia_integra(conn):
    _mov(conn, "2025-01-28", "VENTA", "GGALX", -100, 1494.01)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2024, 12, 5), ticker="GGALX", tipo="CANJE", cantidad=100.0,
        nota="Cupones recibidos por tenencia de GGAL"))
    conn.commit()

    r = _led(conn).por_ticker("GGALX")[0]
    assert not r.descubierta
    assert r.resultado_ars == pytest.approx(1494.01)
    assert capital_aportado(conn, UID).depositos_ars == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Las dos vías de cálculo no pueden divergir
# ---------------------------------------------------------------------------

def test_la_cantidad_coincide_entre_ledger_y_posiciones(conn):
    """`posiciones_desde_db` y el ledger son dos caminos al mismo número. Si
    los ajustes alimentaran solo uno, la tabla y la reconciliación se
    contradirían."""
    _mov(conn, "2025-03-06", "COMPRA", "BYMA", 5, -2414.60)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT", cantidad=5.0))
    conn.commit()

    pos = posiciones_desde_db(conn, UID)["BYMA"]
    assert pos.cant_actual == pytest.approx(10.0)
    assert pos.cant_actual == pytest.approx(_led(conn).estados["BYMA"].cantidad)


# ---------------------------------------------------------------------------
# Persistencia y guardas
# ---------------------------------------------------------------------------

def test_cargar_el_mismo_ajuste_dos_veces_no_duplica(conn):
    """Misma disciplina que el `hash_dedupe` de los movimientos."""
    a = aj.Ajuste(fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT",
                  cantidad=9.0)
    assert aj.agregar(conn, UID, a) is not None
    assert aj.agregar(conn, UID, a) is None
    conn.commit()
    assert len(aj.listar(conn, UID)) == 1


def test_no_se_acepta_un_tipo_inventado(conn):
    with pytest.raises(ValueError):
        aj.agregar(conn, UID, aj.Ajuste(
            fecha=date(2025, 9, 1), ticker="BYMA", tipo="MAGIA", cantidad=1))


def test_no_se_acepta_un_ajuste_vacio(conn):
    """Sin unidades ni costo no ajusta nada: es ruido en la auditoría."""
    with pytest.raises(ValueError):
        aj.agregar(conn, UID, aj.Ajuste(
            fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT"))


def test_el_ticker_se_normaliza_en_mayusculas(conn):
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker=" byma ", tipo="SPLIT", cantidad=9.0))
    conn.commit()
    assert aj.listar(conn, UID)[0].ticker == "BYMA"


def test_eliminar_saca_el_ajuste_y_su_efecto(conn):
    _cargar_byma(conn)
    ident = aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT", cantidad=9.0))
    conn.commit()
    assert not [a for a in _led(conn).advertencias if a.startswith("BYMA")]

    assert aj.eliminar(conn, UID, ident) is True
    conn.commit()
    assert [a for a in _led(conn).advertencias if a.startswith("BYMA")]


def test_los_ajustes_son_por_usuario(conn):
    conn.execute("INSERT INTO usuarios (id, username, fullname) "
                 "VALUES (2, 'otro', 'Otro')")
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker="BYMA", tipo="SPLIT", cantidad=9.0))
    conn.commit()
    assert len(aj.listar(conn, 2)) == 0


def test_listar_filtra_por_ticker(conn):
    aj.agregar(conn, UID, aj.Ajuste(fecha=date(2025, 9, 1), ticker="BYMA",
                                    tipo="SPLIT", cantidad=9.0))
    aj.agregar(conn, UID, aj.Ajuste(fecha=date(2025, 9, 1), ticker="TXAR",
                                    tipo="SPLIT", cantidad=9.0))
    conn.commit()
    assert [a.ticker for a in aj.listar(conn, UID, "TXAR")] == ["TXAR"]


def test_el_flag_estimado_sobrevive_al_guardado(conn):
    """Si no se persistiera, en seis meses no habría forma de saber que ese
    costo salió de un recuerdo y no del resumen del broker."""
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2024, 12, 5), ticker="TXAR", tipo="SALDO_INICIAL",
        cantidad=300.0, costo_ars=COSTO_TXAR, estimado=True))
    conn.commit()
    assert aj.listar(conn, UID)[0].estimado is True


# ---------------------------------------------------------------------------
# El despeje del costo
# ---------------------------------------------------------------------------

def test_costo_desde_rendimiento_despeja_txar():
    """$186.751,31 vendido a −20% ⇒ costó $233.439,14."""
    assert aj.costo_desde_rendimiento(186_751.31, -20.0) == pytest.approx(
        233_439.14, abs=0.01)


def test_costo_desde_rendimiento_ida_y_vuelta():
    costo = aj.costo_desde_rendimiento(1000.0, 25.0)
    assert (1000.0 - costo) / costo * 100 == pytest.approx(25.0)


def test_costo_desde_rendimiento_rechaza_perdida_total():
    with pytest.raises(ValueError):
        aj.costo_desde_rendimiento(1000.0, -100.0)


# ---------------------------------------------------------------------------
# Orden dentro del mismo día
# ---------------------------------------------------------------------------

def test_el_ajuste_se_aplica_antes_que_la_venta_del_mismo_dia():
    """Un split fechado el día de la venta tiene que estar aplicado antes."""
    eventos = [
        Evento(date(2025, 1, 1), "COMPRA", "X", 10, -1000.0, "ARS", None),
        Evento(date(2025, 6, 1), "VENTA", "X", -20, 2000.0, "ARS", None),
        Evento(date(2025, 6, 1), "AJUSTE", "X", 10, 0.0, "ARS", None),
    ]
    r = recorrer(eventos).por_ticker("X")[0]
    assert not r.descubierta
    assert r.resultado_ars == pytest.approx(1000.0)


def test_un_ajuste_no_genera_operacion_cerrada():
    """Ajustar no es operar: no puede aparecer en la lista de trades."""
    eventos = [
        Evento(date(2025, 1, 1), "AJUSTE", "X", 10, -500.0, "ARS", None),
    ]
    led = recorrer(eventos)
    assert led.realizaciones == []
    assert led.estados["X"].cantidad == pytest.approx(10.0)
    assert led.estados["X"].costo_ars == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Un ticker mal escrito no falla: no hace nada, que es peor
# ---------------------------------------------------------------------------

def test_tickers_conocidos_sale_de_los_movimientos(conn):
    _cargar_byma(conn)
    assert aj.tickers_conocidos(conn, UID) == {"BYMA"}


def test_sugiere_el_ticker_contenido_en_el_texto():
    """El caso real del 4/8/2026: se cargó `CUPONES GGALX` en vez de `GGALX`.

    El ajuste se guardó sin chistar, no corrigió nada y el aviso original
    siguió apareciendo. La sugerencia tiene que poner `GGALX` primero.
    """
    assert aj.parecidos("CUPONES GGALX", {"GGAL", "GGALX", "BYMA"})[0] == "GGALX"


def test_sugiere_por_parecido_ante_un_typo():
    assert "BYMA" in aj.parecidos("BYMAA", {"BYMA", "TXAR", "GGAL"})


def test_un_ticker_conocido_no_genera_sugerencias():
    assert aj.parecidos("BYMA", {"BYMA", "TXAR"}) == []


def test_sin_ticker_no_sugiere_nada():
    assert aj.parecidos("", {"BYMA"}) == []


def test_el_ajuste_con_ticker_equivocado_no_corrige_nada(conn):
    """La prueba de que el aviso hacía falta: cargarlo mal deja todo igual."""
    _cargar_byma(conn)
    aj.agregar(conn, UID, aj.Ajuste(
        fecha=date(2025, 9, 1), ticker="SPLIT DE BYMA", tipo="SPLIT",
        cantidad=9.0))
    conn.commit()
    assert [a for a in _led(conn).advertencias if a.startswith("BYMA")]
