"""Comandos de WhatsApp (Fase A, ADR-0008): parser, categorías y comandos.

`comandos.py` es puro: se prueba con una base sintética, sin red y sin
servidor. Los casos de monto son los que el plan marca como trampa:
`parse_currency_estricto` borra todos los puntos (``1.5`` → 15), así que acá
hay un parser propio y estricto.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

import core.db as core_db
from core.context import set_current_workspace_id
from core.db import connect, init_db
from places.finanzas.core import comandos
from places.finanzas.core.comandos import (
    EntradaInvalida,
    ZONA,
    normalizar,
    parsear_fecha,
    parsear_gasto,
    parsear_monto,
    pesos,
    procesar,
    resolver_categoria,
)
from places.finanzas.core.transactions import insert_transaction

UID = 1
HOY = date(2026, 10, 15)
AHORA = datetime(2026, 10, 15, 12, 0, tzinfo=ZONA)


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
    # Categorías existentes, con grupo, como en la base real.
    for motivo, grupo in [("Supermercado", "Gasto Variable"), ("Nafta", "Gasto Variable"),
                          ("Sueldo", "Ingreso"), ("Compra Divisa", "Inversion"),
                          ("Café", "Gasto Variable")]:
        insert_transaction(conn, fecha=date(2026, 9, 1), motivo=motivo, pasivos=1,
                           user_id=UID)
        conn.execute("UPDATE categorias SET grupo = ? WHERE motivo = ?", (grupo, motivo))
    conn.execute("DELETE FROM transacciones")
    yield conn
    set_current_workspace_id(None)
    conn.close()


def _registrar(conn, wamid, r, cuando=AHORA):
    """Lo que hace el servidor después de `procesar`: dejar rastro del mensaje."""
    conn.execute(
        "INSERT INTO whatsapp_mensajes (wamid, recibido_en, remitente, texto, transaccion_id, "
        "resultado) VALUES (?, ?, '541100000000', '', ?, ?)",
        (wamid, cuando.isoformat(), r.transaccion_id, r.resultado),
    )


def _txns(conn):
    return [dict(r) for r in conn.execute(
        "SELECT fecha, pasivos, ingresos, motivo, comentario FROM transacciones ORDER BY id")]


# ---------------------------------------------------------------- montos

@pytest.mark.parametrize("crudo, esperado", [
    ("2500", 2500.0),
    ("25.000", 25000.0),
    ("1.250.000", 1250000.0),
    ("2500,50", 2500.5),
    ("25.000,5", 25000.5),
    ("$25.000", 25000.0),
    ("$ 2500", 2500.0),
    ("25k", 25000.0),
    ("2,5k", 2500.0),
    ("ARS 1500", 1500.0),
])
def test_montos_validos(crudo, esperado):
    assert parsear_monto(crudo) == esperado


@pytest.mark.parametrize("crudo", ["2500.50", "1.5", "12.50"])
def test_punto_con_uno_o_dos_digitos_es_ambiguo_y_no_se_adivina(crudo):
    with pytest.raises(EntradaInvalida, match="No sé si"):
        parsear_monto(crudo)


@pytest.mark.parametrize("crudo", ["", "abc", "25.00.0", "1,2,3", "0", "0,00", "25.0000"])
def test_montos_invalidos(crudo):
    with pytest.raises(EntradaInvalida):
        parsear_monto(crudo)


# ---------------------------------------------------------------- fechas

@pytest.mark.parametrize("crudo, esperado", [
    ("hoy", HOY),
    ("ayer", date(2026, 10, 14)),
    ("13/10", date(2026, 10, 13)),
    ("13/10/2026", date(2026, 10, 13)),
    ("13/10/26", date(2026, 10, 13)),
    ("2026-10-01", date(2026, 10, 1)),
])
def test_fechas(crudo, esperado):
    assert parsear_fecha(crudo, HOY) == esperado


def test_sin_anio_y_lejos_en_el_futuro_es_del_anio_pasado():
    assert parsear_fecha("28/12", date(2027, 1, 2)) == date(2026, 12, 28)


def test_sin_anio_y_apenas_en_el_futuro_es_un_error_de_tipeo():
    """`20/10` el 15/10 no es del año pasado: pasarlo a 2025 lo escondería del resumen."""
    with pytest.raises(EntradaInvalida, match="futuro"):
        parsear_fecha("20/10", HOY)


def test_la_confirmacion_muestra_el_anio_si_no_es_el_actual(db):
    r = procesar(db, "28/12, 100, nafta", user_id=UID, ahora=datetime(2027, 1, 2, 12, tzinfo=ZONA))
    assert "(28/12/2026)" in r.texto


def test_fecha_futura_explicita_se_rechaza():
    with pytest.raises(EntradaInvalida, match="futuro"):
        parsear_fecha("20/10/2026", HOY)


def test_fecha_imposible():
    with pytest.raises(EntradaInvalida, match="no existe"):
        parsear_fecha("31/02", HOY)


# ---------------------------------------------------------------- mensaje

def test_gasto_minimo():
    g = parsear_gasto("2500, super", HOY)
    assert (g.fecha, g.monto, g.es_ingreso, g.categoria, g.comentario) == (
        HOY, 2500.0, False, "super", None)


def test_gasto_completo_con_fecha_y_comentario():
    g = parsear_gasto("13/10, 18.000, nafta, YPF ruta 2", HOY)
    assert (g.fecha, g.monto, g.categoria, g.comentario) == (
        date(2026, 10, 13), 18000.0, "nafta", "YPF ruta 2")


def test_separadores_mezclados_y_ayer():
    g = parsear_gasto("ayer; 4500 | farmacia", HOY)
    assert (g.fecha, g.monto, g.categoria) == (date(2026, 10, 14), 4500.0, "farmacia")


def test_coma_decimal_no_se_confunde_con_separador():
    g = parsear_gasto("2500,50, super", HOY)
    assert (g.monto, g.categoria) == (2500.5, "super")


def test_espacio_entre_monto_y_categoria():
    g = parsear_gasto("+350000 sueldo octubre", HOY)
    assert (g.monto, g.es_ingreso, g.categoria) == (350000.0, True, "sueldo octubre")


@pytest.mark.parametrize("texto", ["hola", "super 2500", "2500", "13/10, 2500"])
def test_mensajes_que_no_son_carga(texto):
    with pytest.raises(EntradaInvalida):
        parsear_gasto(texto, HOY)


# ---------------------------------------------------------------- categorías

EXISTENTES = ["Supermercado", "Nafta", "Café", "Compra Divisa"]


def test_categoria_exacta_sin_mayusculas_ni_acentos():
    assert resolver_categoria("CAFE", EXISTENTES) == ("exacta", "Café")
    assert resolver_categoria("compra  divisa", EXISTENTES) == ("exacta", "Compra Divisa")


def test_prefijo_unico_se_propone():
    assert resolver_categoria("super", EXISTENTES) == ("parecida", "Supermercado")


def test_error_de_tipeo_se_propone():
    assert resolver_categoria("supermercdo", EXISTENTES) == ("parecida", "Supermercado")


def test_sin_parecido_es_nueva():
    assert resolver_categoria("regalo tía", EXISTENTES) == ("nueva", None)


def test_normalizar():
    assert normalizar("  Café   Martínez ") == "cafe martinez"


def test_pesos():
    assert pesos(2500) == "$2.500"
    assert pesos(2500.5) == "$2.500,50"
    assert pesos(1234567) == "$1.234.567"


# ---------------------------------------------------------------- procesar

def test_categoria_exacta_carga_directo(db):
    r = procesar(db, "2500, nafta", user_id=UID, ahora=AHORA)
    assert r.resultado == "cargado" and r.transaccion_id
    assert "✅ Cargado" in r.texto and "$2.500 en Nafta (15/10)" in r.texto
    assert _txns(db) == [{"fecha": "2026-10-15", "pasivos": 2500.0, "ingresos": 0.0,
                          "motivo": "Nafta", "comentario": None}]


def test_ingreso_con_mas(db):
    r = procesar(db, "+350.000, sueldo", user_id=UID, ahora=AHORA)
    assert r.resultado == "cargado"
    assert _txns(db)[0]["ingresos"] == 350000.0 and _txns(db)[0]["pasivos"] == 0.0


def test_parecida_pregunta_y_si_carga_con_el_nombre_canonico(db):
    r = procesar(db, "2500, super", user_id=UID, ahora=AHORA)
    assert r.resultado == "pendiente" and "Supermercado" in r.texto
    assert _txns(db) == []
    r = procesar(db, "Sí", user_id=UID, ahora=AHORA + timedelta(minutes=1))
    assert r.resultado == "cargado"
    assert _txns(db)[0]["motivo"] == "Supermercado"


def test_parecida_y_no_no_carga_nada(db):
    procesar(db, "2500, super", user_id=UID, ahora=AHORA)
    r = procesar(db, "no", user_id=UID, ahora=AHORA)
    assert r.resultado == "rechazado" and _txns(db) == []


def test_nueva_pregunta_y_si_la_crea(db):
    r = procesar(db, "8000, regalo tía, cumple", user_id=UID, ahora=AHORA)
    assert r.resultado == "pendiente" and "Regalo tía" in r.texto and "no existe" in r.texto
    r = procesar(db, "si", user_id=UID, ahora=AHORA)
    assert r.resultado == "cargado"
    assert _txns(db)[0]["motivo"] == "Regalo tía"
    assert _txns(db)[0]["comentario"] == "cumple"


def test_pendiente_vence_a_los_10_minutos(db):
    procesar(db, "2500, super", user_id=UID, ahora=AHORA)
    r = procesar(db, "si", user_id=UID, ahora=AHORA + timedelta(minutes=11))
    assert r.resultado == "rechazado" and "nada pendiente" in r.texto
    assert _txns(db) == []


def test_otro_mensaje_descarta_el_pendiente(db):
    procesar(db, "2500, super", user_id=UID, ahora=AHORA)
    r = procesar(db, "100, nafta", user_id=UID, ahora=AHORA)
    assert r.resultado == "cargado"
    assert procesar(db, "si", user_id=UID, ahora=AHORA).resultado == "rechazado"
    assert [t["motivo"] for t in _txns(db)] == ["Nafta"]


def test_monto_ambiguo_no_escribe(db):
    r = procesar(db, "2500.50, nafta", user_id=UID, ahora=AHORA)
    assert r.resultado == "rechazado" and "No sé si" in r.texto
    assert _txns(db) == []


def test_basura_explica_el_formato(db):
    r = procesar(db, "hola qué tal", user_id=UID, ahora=AHORA)
    assert r.resultado == "rechazado" and "ayuda" in r.texto


def test_ayuda(db):
    r = procesar(db, "Ayuda", user_id=UID, ahora=AHORA)
    assert r.resultado == "consulta" and "Cómo cargar" in r.texto


def test_deshacer_borra_lo_ultimo_cargado_por_whatsapp(db):
    r1 = procesar(db, "100, nafta", user_id=UID, ahora=AHORA)
    _registrar(db, "w1", r1, AHORA)
    r2 = procesar(db, "200, café", user_id=UID, ahora=AHORA)
    _registrar(db, "w2", r2, AHORA + timedelta(minutes=1))
    r = procesar(db, "deshacer", user_id=UID, ahora=AHORA + timedelta(minutes=2))
    assert r.resultado == "deshecho" and "$200 en Café" in r.texto
    assert [t["motivo"] for t in _txns(db)] == ["Nafta"]
    # El segundo deshacer va por la anterior.
    r = procesar(db, "deshacer", user_id=UID, ahora=AHORA + timedelta(minutes=3))
    assert r.resultado == "deshecho" and _txns(db) == []


def test_deshacer_no_toca_lo_cargado_desde_la_app(db):
    insert_transaction(db, fecha=HOY, motivo="Nafta", pasivos=999, user_id=UID)
    r = procesar(db, "deshacer", user_id=UID, ahora=AHORA)
    assert r.resultado == "rechazado"
    assert len(_txns(db)) == 1


def test_deshacer_solo_ultimas_24h(db):
    r1 = procesar(db, "100, nafta", user_id=UID, ahora=AHORA)
    _registrar(db, "w1", r1, AHORA - timedelta(hours=25))
    r = procesar(db, "deshacer", user_id=UID, ahora=AHORA)
    assert r.resultado == "rechazado" and len(_txns(db)) == 1


def test_resumen_usa_la_formula_del_dashboard(db):
    insert_transaction(db, fecha=HOY, motivo="Supermercado", pasivos=10000, user_id=UID)
    insert_transaction(db, fecha=HOY, motivo="Nafta", pasivos=5000, user_id=UID)
    insert_transaction(db, fecha=HOY, motivo="Sueldo", ingresos=300000, user_id=UID)
    # La Compra Divisa es ahorro: el dashboard no la cuenta como gasto.
    insert_transaction(db, fecha=HOY, motivo="Compra Divisa", pasivos=100000, user_id=UID)
    # Una categoría nueva queda "Sin categorizar": va en su propio renglón.
    insert_transaction(db, fecha=HOY, motivo="Regalo", pasivos=7000, user_id=UID)
    # Otro mes: no entra.
    insert_transaction(db, fecha=date(2026, 9, 30), motivo="Nafta", pasivos=1, user_id=UID)

    r = procesar(db, "resumen", user_id=UID, ahora=AHORA)
    assert r.resultado == "consulta"
    assert "Gastos: $15.000" in r.texto
    assert "Ingresos: $300.000" in r.texto
    assert "Movimientos: 5" in r.texto
    assert "Sin categorizar: $7.000" in r.texto
    assert "Últimos movimientos" in r.texto


def test_resumen_sin_movimientos(db):
    assert "Todavía no hay movimientos" in comandos.resumen_mes(db, user_id=UID, hoy=HOY)


def test_hoy_es_buenos_aires_no_utc(db):
    # 23:30 del 15 en Buenos Aires = 02:30 del 16 en UTC.
    tarde = datetime(2026, 10, 15, 23, 30, tzinfo=ZONA)
    procesar(db, "100, nafta", user_id=UID, ahora=tarde.astimezone(timezone.utc))
    assert _txns(db)[0]["fecha"] == "2026-10-15"



# ---------------------------------------------------------------- cuentas (16/10/2026)

@pytest.mark.parametrize("texto, monto, cuenta", [
    ("100-50, compras", 50.0, "100-50"),
    ("100 - 50, compras", 50.0, "100-50"),
    ("100+50, compras", 150.0, "100+50"),
    ("3x2.500, super", 7500.0, "3x2.500"),
    ("3 × 2500 super", 7500.0, "3×2500"),
    ("12.000/3, nafta", 4000.0, "12.000/3"),
    ("1000+500*2, nafta", 2000.0, "1000+500*2"),     # × antes que +
    ("$100-$50 compras", 50.0, "$100-$50"),
])
def test_el_monto_puede_ser_una_cuenta(texto, monto, cuenta):
    g = parsear_gasto(texto, HOY)
    assert (g.monto, g.cuenta) == (monto, cuenta)
    assert g.categoria in {"compras", "super", "nafta"}


def test_un_monto_sin_cuenta_no_tiene_cuenta():
    assert parsear_gasto("2500,50, super", HOY).cuenta is None


def test_mas_adelante_sigue_siendo_ingreso():
    g = parsear_gasto("+100+50, sueldo", HOY)
    assert (g.monto, g.es_ingreso) == (150.0, True)


@pytest.mark.parametrize("texto, motivo", [
    ("100-150, compras", "mayor que cero"),
    ("100-100, compras", "mayor que cero"),
    ("100/0, compras", "divide por cero"),
    ("1.5*2, compras", "No sé si"),            # cada número sigue las reglas de siempre
])
def test_cuentas_que_no_se_cargan(texto, motivo):
    with pytest.raises(EntradaInvalida, match=motivo):
        parsear_gasto(texto, HOY)


@pytest.mark.parametrize("texto", ["100 - , compras", "100, 50", "100, -50"])
def test_lo_que_no_es_categoria_se_rechaza(texto):
    """Antes "100 - 50, compras" tomaba $100 y la categoría "- 50"."""
    with pytest.raises(EntradaInvalida):
        parsear_gasto(texto, HOY)


def test_dia_barra_mes_es_fecha_solo_si_despues_viene_un_monto():
    assert parsear_gasto("12/3, 500, compras", HOY).fecha == date(2026, 3, 12)
    g = parsear_gasto("12/3, compras", HOY)
    assert (g.fecha, g.monto, g.cuenta) == (HOY, 4.0, "12/3")


def test_una_x_seguida_de_letras_no_es_multiplicar():
    assert parsear_gasto("100, xbox", HOY).categoria == "xbox"


def test_la_confirmacion_muestra_la_cuenta(db):
    r = procesar(db, "100-50, nafta", user_id=UID, ahora=AHORA)
    assert r.resultado == "cargado" and "$50 en Nafta (15/10) · 100-50" in r.texto
    assert _txns(db)[0]["pasivos"] == 50.0


def test_la_cuenta_sobrevive_a_la_pregunta_de_categoria(db):
    r = procesar(db, "3x2.500, super", user_id=UID, ahora=AHORA)
    assert r.resultado == "pendiente" and "$7.500 = 3x2.500" in r.texto
    r = procesar(db, "si", user_id=UID, ahora=AHORA)
    assert r.resultado == "cargado" and "· 3x2.500" in r.texto
    assert _txns(db)[0]["pasivos"] == 7500.0


def test_la_ayuda_explica_las_cuentas(db):
    assert "Cuentas: 100-50" in procesar(db, "ayuda", user_id=UID, ahora=AHORA).texto


def test_resumen_de_un_mes_sin_movimientos_no_se_rompe(db):
    """Hay movimientos en la base, pero no este mes (el 1° antes de cargar nada).
    Hasta el 17/10/2026 esto tiraba KeyError: 'pasivos'."""
    insert_transaction(db, fecha=date(2026, 9, 30), motivo="Nafta", pasivos=500, user_id=UID)
    texto = comandos.resumen_mes(db, user_id=UID, hoy=HOY)
    assert "Gastos: $0" in texto and "Movimientos: 0" in texto
