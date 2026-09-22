"""Vencimientos: leerlos de la descripción sin inventar precisión.

Las descripciones son **reales**, salen de la hoja `Config` del Excel de
Franco. El caso que más importa es el de `TZX28` (*"Bono Tesoro Vto. 2028"*):
se sabe el año y nada más, y fabricar un "31/12/2028" para poder contar días
sería inventar un dato que después nadie puede distinguir de uno bueno.
"""

from __future__ import annotations

from datetime import date

import pytest

from core.db import connect, init_db
from places.inversiones.cartera import vencimientos as v

HOY = date(2026, 8, 5)


class _Inst:
    def __init__(self, descripcion, categoria_activo="Bonos"):
        self.descripcion = descripcion
        self.categoria_activo = categoria_activo


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    ruta = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(ruta))
    init_db(ruta)
    c = connect(ruta)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Parseo — las formas reales que aparecen en Config
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto,esperada", [
    ("Bono Tesoro Nacional Vto. 30/11/2029", date(2029, 11, 30)),
    ("Bono Nacion Tasa Dual Vto 30/06/2026", date(2026, 6, 30)),   # sin punto
    ("Letra Tesoro Vto. 17/04/2026", date(2026, 4, 17)),
    ("ON MSU Energy Vto. 05/12/2030", date(2030, 12, 5)),
    ("Bono Tesoro CER Vto. 14/02/2025", date(2025, 2, 14)),
    ("Letra Tesoro Vto. 31/07/2026", date(2026, 7, 31)),
])
def test_lee_la_fecha_completa(texto, esperada):
    fecha, precision = v.parse_vencimiento(texto)
    assert fecha == esperada
    assert precision == "dia"


def test_acepta_el_ano_de_dos_digitos():
    assert v.parse_vencimiento("Letra Vto. 30/06/26")[0] == date(2026, 6, 30)


def test_solo_el_ano_no_se_convierte_en_una_fecha_exacta():
    """`TZX28` dice *"Vto. 2028"*. Se guarda el 31/12 como ancla ordenable,
    pero la precisión queda marcada para que nadie muestre ese día."""
    fecha, precision = v.parse_vencimiento("Bono Tesoro Vto. 2028")
    assert precision == "anio"
    assert fecha.year == 2028


def test_el_ano_en_el_nombre_no_es_un_vencimiento():
    """`"Bono USD 2038"` (AE38) tiene el año en el **nombre**, no como
    vencimiento. Tomarlo sería afirmar algo que la descripción no dice."""
    assert v.parse_vencimiento("Bono USD 2038") == (None, "sin_dato")
    assert v.parse_vencimiento("Bono USD 2029") == (None, "sin_dato")


def test_sin_descripcion_no_hay_dato():
    assert v.parse_vencimiento(None) == (None, "sin_dato")
    assert v.parse_vencimiento("") == (None, "sin_dato")
    assert v.parse_vencimiento("Grupo Financiero Galicia") == (None, "sin_dato")


def test_una_fecha_imposible_no_se_adivina():
    """31/02 es un dato malo. Corregir a 28/02 sería inventar."""
    assert v.parse_vencimiento("Letra Vto. 31/02/2026") == (None, "sin_dato")


# ---------------------------------------------------------------------------
# La etiqueta nunca miente sobre lo que sabe
# ---------------------------------------------------------------------------

def test_la_etiqueta_del_ano_no_muestra_un_dia():
    ven = v.Vencimiento("TZX28", date(2028, 12, 31), "anio")
    assert ven.etiqueta == "2028"
    assert not ven.es_exacto


def test_la_etiqueta_de_la_fecha_exacta_muestra_el_dia():
    assert v.Vencimiento("AN29", date(2029, 11, 30), "dia").etiqueta == "30/11/2029"


def test_sin_fecha_la_etiqueta_es_sd():
    assert v.Vencimiento("#UMV", None, "sin_dato").etiqueta == "s/d"


def test_no_se_cuentan_dias_contra_un_ano_redondeado():
    """Contar días hasta un 31/12 fabricado daría una precisión falsa."""
    assert v.Vencimiento("TZX28", date(2028, 12, 31), "anio").dias_restantes(HOY) is None


def test_los_dias_restantes_se_cuentan_desde_hoy():
    ven = v.Vencimiento("S31L6", date(2026, 8, 15), "dia")
    assert ven.dias_restantes(HOY) == 10
    assert ven.proximo(HOY)
    assert not ven.vencido(HOY)


def test_reconoce_lo_ya_vencido():
    ven = v.Vencimiento("S15G5", date(2025, 8, 15), "dia")
    assert ven.vencido(HOY)
    assert not ven.proximo(HOY)


# ---------------------------------------------------------------------------
# Resolución: qué vence y qué ni siquiera aplica
# ---------------------------------------------------------------------------

def test_las_acciones_no_entran(conn):
    """A una acción no le **falta** el vencimiento: no tiene. Meterla como
    's/d' ensuciaría el cuadro igual que el sector de un bono (trampa #16)."""
    insts = {
        "GGAL": _Inst("Grupo Financiero Galicia", "Acciones"),
        "NVDA": _Inst("NVIDIA Corp", "Cedears"),
        "AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos"),
    }
    assert set(v.resolver(insts, conn)) == {"AN29"}


def test_los_pagares_entran_aunque_no_tengan_categoria(conn):
    """Se reconocen por el `#` del ticker, igual que en `analisis.py`."""
    insts = {"#UMV060770008": _Inst("Pagare MAV", "")}
    res = v.resolver(insts, conn)
    assert "#UMV060770008" in res
    assert res["#UMV060770008"].precision == "sin_dato"


def test_el_override_manual_le_gana_a_la_descripcion(conn):
    insts = {"AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos")}
    v.set_override(conn, "AN29", date(2030, 1, 15))
    conn.commit()

    ven = v.resolver(insts, conn)["AN29"]
    assert ven.fecha == date(2030, 1, 15)
    assert ven.fuente == "manual"
    assert ven.es_exacto


def test_quitar_el_override_devuelve_la_fecha_de_la_descripcion(conn):
    insts = {"AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos")}
    v.set_override(conn, "AN29", date(2030, 1, 15))
    conn.commit()
    assert v.quitar_override(conn, "AN29") is True
    conn.commit()
    assert v.resolver(insts, conn)["AN29"].fecha == date(2029, 11, 30)


def test_el_override_le_da_fecha_al_pagare(conn):
    """El caso que motivó los overrides: el pagaré no trae fecha en ningún
    lado y es justo el que vence primero."""
    insts = {"#UMV060770008": _Inst("Pagare MAV", "")}
    v.set_override(conn, "#UMV060770008", date(2027, 4, 6))
    conn.commit()
    ven = v.resolver(insts, conn)["#UMV060770008"]
    assert ven.dias_restantes(HOY) == 244


def test_sin_la_migracion_no_se_rompe(conn):
    """Los vencimientos son una mejora, no un requisito para ver la cartera."""
    conn.execute("DROP TABLE cartera_vencimientos")
    conn.commit()
    insts = {"AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos")}
    assert v.resolver(insts, conn)["AN29"].fecha == date(2029, 11, 30)


# ---------------------------------------------------------------------------
# La tabla para la vista
# ---------------------------------------------------------------------------

class _Pos:
    def __init__(self, cant=10, ars=100000.0, usd=65.0, cerrada=False):
        self.cant_actual = cant
        self.valor_ars_actual = ars
        self.valor_usd_actual = usd
        self.cerrada = cerrada


def _tres_bonos(conn):
    return v.resolver({
        "S31L6": _Inst("Letra Tesoro Vto. 31/07/2026", "Letras"),
        "S17A6": _Inst("Letra Tesoro Vto. 17/04/2027", "Letras"),
        "AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos"),
        "TZX28": _Inst("Bono Tesoro Vto. 2028", "Bonos"),
    }, conn)


def test_se_ordena_del_que_vence_antes_al_que_vence_despues(conn):
    filas = v.proximos(_tres_bonos(conn), hoy=HOY)
    assert [f["Ticker"] for f in filas] == ["S17A6", "TZX28", "AN29"]


def test_lo_ya_vencido_no_aparece_por_defecto(conn):
    """S31L6 venció el 31/7/2026 y hoy es 5/8: ya no te vence nada."""
    assert "S31L6" not in [f["Ticker"] for f in v.proximos(_tres_bonos(conn), hoy=HOY)]
    con_vencidos = v.proximos(_tres_bonos(conn), hoy=HOY, incluir_vencidos=True)
    assert "S31L6" in [f["Ticker"] for f in con_vencidos]


def test_lo_que_no_tiene_fecha_va_al_final(conn):
    """No se puede afirmar que vence tarde: solo que no se sabe. Mezclarlo
    con los ordenados sugeriría una precisión que no existe."""
    insts = {
        "#UMV": _Inst("Pagare MAV", ""),
        "AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos"),
    }
    filas = v.proximos(v.resolver(insts, conn), hoy=HOY)
    assert filas[-1]["Ticker"] == "#UMV"
    assert filas[-1]["Días"] is None


def test_solo_entra_lo_que_todavia_tenes(conn):
    """Un bono que ya vendiste no te vence."""
    vencs = _tres_bonos(conn)
    valuadas = {"AN29": _Pos(), "TZX28": _Pos(cant=0), "S17A6": _Pos(cerrada=True)}
    assert [f["Ticker"] for f in v.proximos(vencs, valuadas, HOY)] == ["AN29"]


def test_el_resumen_dice_cuanta_plata_vence_pronto(conn):
    insts = {
        "S17A6": _Inst("Letra Tesoro Vto. 17/09/2026", "Letras"),   # en 43 días
        "AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos"),
    }
    valuadas = {"S17A6": _Pos(ars=500_000.0, usd=327.0), "AN29": _Pos()}
    r = v.resumen(v.resolver(insts, conn), valuadas, HOY)

    assert r["n_proximos"] == 1
    assert r["ars_proximos"] == pytest.approx(500_000.0)
    assert r["proximo"]["Ticker"] == "S17A6"
    assert r["proximo"]["Días"] == 43


def test_el_resumen_lista_lo_que_falta_resolver(conn):
    insts = {"#UMV": _Inst("Pagare MAV", "")}
    r = v.resumen(v.resolver(insts, conn), {"#UMV": _Pos()}, HOY)
    assert r["sin_fecha"] == ["#UMV"]


# ---------------------------------------------------------------------------
# La forma REAL con la que llama la vista
# ---------------------------------------------------------------------------
#
# ⚠️ Bug en producción (5/8/2026):
#
#     AttributeError: 'list' object has no attribute 'get'
#
# `proximos()` hacía `valuadas.get(ticker)` asumiendo un diccionario, pero la
# vista maneja las posiciones valuadas como **lista**. El panel de vencimientos
# reventaba la pantalla entera de Cartera.
#
# Los tests de arriba no lo vieron **porque estaban escritos contra la
# suposición del módulo, no contra el llamador**. Pasar un dict inventado los
# hacía verdes mientras la app moría. De acá en adelante, todo test de una
# función que consume posiciones tiene que probar **la lista**, que es lo que
# llega de verdad.


def _lista(*posiciones):
    """Las posiciones tal como las pasa `view.py`: una lista, no un dict."""
    return list(posiciones)


class _PosT(_Pos):
    def __init__(self, ticker, **kw):
        super().__init__(**kw)
        self.ticker = ticker


def test_proximos_acepta_la_lista_que_manda_la_vista(conn):
    vencs = v.resolver({
        "AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos"),
        "S17A6": _Inst("Letra Tesoro Vto. 17/09/2026", "Letras"),
    }, conn)
    posiciones = _lista(_PosT("AN29"), _PosT("S17A6"))

    filas = v.proximos(vencs, posiciones, HOY)
    assert [f["Ticker"] for f in filas] == ["S17A6", "AN29"]


def test_resumen_acepta_la_lista_que_manda_la_vista(conn):
    """Es la llamada exacta que rompía: `resumen(vencs, valuadas, hoy)`."""
    vencs = v.resolver(
        {"S17A6": _Inst("Letra Tesoro Vto. 17/09/2026", "Letras")}, conn)
    posiciones = _lista(_PosT("S17A6", ars=500_000.0, usd=327.0))

    r = v.resumen(vencs, posiciones, HOY)
    assert r["n_proximos"] == 1
    assert r["ars_proximos"] == pytest.approx(500_000.0)
    assert r["proximo"]["Ticker"] == "S17A6"


def test_la_lista_filtra_igual_que_el_diccionario(conn):
    """Un bono que ya vendiste no te vence, venga en lista o en dict."""
    vencs = v.resolver({
        "AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos"),
        "S17A6": _Inst("Letra Tesoro Vto. 17/09/2026", "Letras"),
    }, conn)
    vivos = _lista(_PosT("AN29"), _PosT("S17A6", cant=0))

    assert [f["Ticker"] for f in v.proximos(vencs, vivos, HOY)] == ["AN29"]


def test_una_lista_vacia_no_es_lo_mismo_que_no_pasar_nada(conn):
    """Sin posiciones vivas no vence nada; sin el dato, se muestran todas."""
    vencs = v.resolver(
        {"AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029", "Bonos")}, conn)
    assert v.proximos(vencs, [], HOY) == []
    assert len(v.proximos(vencs, None, HOY)) == 1


# ---------------------------------------------------------------------------
# El cronograma como segunda fuente (27/8/2026)
# ---------------------------------------------------------------------------
#
# El caso que motiva todo esto es el **AE38**: su descripción es
# `"Bono USD 2038"`, donde el 2038 es parte del *nombre* y no un vencimiento,
# así que el parser —bien— devuelve `sin_dato`. Pero desde M15 la app tiene
# guardado su cronograma de pagos, y la última fecha de ese cronograma **es**
# el vencimiento. El dato ya estaba en la base; nadie lo miraba.


class _Flujo:
    def __init__(self, fecha):
        self.fecha = fecha


class _Cron:
    def __init__(self, *fechas):
        self.flujos = [_Flujo(f) for f in fechas]


def _leer_fake(mapa):
    """Un `leer_cronograma` de mentira: ``{ticker: _Cron}``."""
    return lambda conn, ticker, nominales=None: mapa.get(ticker)


def test_vencimiento_de_cronograma_toma_el_ultimo_pago():
    leer = _leer_fake({"AE38": _Cron(date(2027, 7, 12), date(2038, 1, 9),
                                     date(2030, 1, 9))})
    assert v.vencimiento_de_cronograma(
        object(), "AE38", leer) == date(2038, 1, 9)


def test_sin_cronograma_no_opina():
    assert v.vencimiento_de_cronograma(object(), "XXXX", _leer_fake({})) is None


def test_cronograma_vacio_no_opina():
    leer = _leer_fake({"AE38": _Cron()})
    assert v.vencimiento_de_cronograma(object(), "AE38", leer) is None


def test_una_base_sin_m15_no_rompe_nada():
    """Sin la tabla de cronogramas, la fuente calla — no tumba la pantalla."""
    import sqlite3

    def sin_tabla(conn, ticker, nominales=None):
        raise sqlite3.OperationalError("no such table: cartera_cronogramas_meta")
    assert v.vencimiento_de_cronograma(object(), "AE38", sin_tabla) is None


def test_un_bug_al_leer_el_cronograma_si_se_ve():
    """Trampa 36 (22/9/2026): antes cualquier excepción —un bug incluido— se
    tragaba y el bono quedaba "sin fecha" sin que nada avisara."""
    def bug(conn, ticker, nominales=None):
        raise AttributeError("bug")
    with pytest.raises(AttributeError):
        v.vencimiento_de_cronograma(object(), "AE38", bug)


def test_el_ae38_deja_de_quedar_sin_fecha(conn):
    """El caso real: sin cronograma es `s/d`; con cronograma, exacto."""
    instrumentos = {"AE38": _Inst("Bono USD 2038")}

    sin = v.resolver(instrumentos, conn, _leer_fake({}))
    assert sin["AE38"].fecha is None
    assert sin["AE38"].precision == "sin_dato"
    assert sin["AE38"].etiqueta == "s/d"

    con = v.resolver(instrumentos, conn,
                     _leer_fake({"AE38": _Cron(date(2038, 1, 9))}))
    assert con["AE38"].fecha == date(2038, 1, 9)
    assert con["AE38"].precision == "dia"
    assert con["AE38"].fuente == "cronograma"
    assert con["AE38"].etiqueta == "09/01/2038"


def test_el_cronograma_mejora_una_precision_de_solo_anio(conn):
    """`Vto. 2028` sabe el año; el cronograma sabe el día. Gana el día."""
    r = v.resolver({"TZX28": _Inst("Bono Tesoro Vto. 2028")}, conn,
                   _leer_fake({"TZX28": _Cron(date(2028, 6, 30))}))
    assert r["TZX28"].fecha == date(2028, 6, 30)
    assert r["TZX28"].precision == "dia"
    assert r["TZX28"].dias_restantes(HOY) is not None


def test_el_override_manual_le_gana_al_cronograma(conn):
    """La cascada no cambió de cabeza: lo que fija Franco manda."""
    v.set_override(conn, "AE38", date(2038, 12, 31))
    r = v.resolver({"AE38": _Inst("Bono USD 2038")}, conn,
                   _leer_fake({"AE38": _Cron(date(2038, 1, 9))}))
    assert r["AE38"].fecha == date(2038, 12, 31)
    assert r["AE38"].fuente == "manual"


def test_dos_fuentes_exactas_que_no_coinciden_no_se_tragan(conn):
    """Gana el cronograma, pero la fecha descartada queda visible."""
    r = v.resolver({"AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029")},
                   conn, _leer_fake({"AN29": _Cron(date(2029, 12, 2))}))
    assert r["AN29"].fecha == date(2029, 12, 2)
    assert r["AN29"].fuente == "cronograma"
    assert r["AN29"].discrepancia == date(2029, 11, 30)


def test_fuentes_que_coinciden_no_reportan_discrepancia(conn):
    r = v.resolver({"AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029")},
                   conn, _leer_fake({"AN29": _Cron(date(2029, 11, 30))}))
    assert r["AN29"].discrepancia is None
    assert r["AN29"].fecha == date(2029, 11, 30)


def test_resumen_reporta_las_discrepancias(conn):
    r = v.resolver({"AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029")},
                   conn, _leer_fake({"AN29": _Cron(date(2029, 12, 2))}))
    res = v.resumen(r, None, HOY)
    assert len(res["discrepancias"]) == 1
    assert res["discrepancias"][0]["Ticker"] == "AN29"
    assert res["discrepancias"][0]["descripcion"] == date(2029, 11, 30)


def test_la_tabla_dice_de_donde_salio_la_fecha(conn):
    r = v.resolver({"AE38": _Inst("Bono USD 2038")}, conn,
                   _leer_fake({"AE38": _Cron(date(2038, 1, 9))}))
    fila = v.proximos(r, None, HOY)[0]
    assert fila["Fuente"] == "cronograma"


def test_a_las_acciones_no_se_les_pide_cronograma(conn):
    """Una acción no vence: no puede ni siquiera consultarse."""
    pedidos = []

    def leer(conn_, ticker, nominales=None):
        pedidos.append(ticker)
        return None

    v.resolver({"GGAL": _Inst("Grupo Galicia", "Acciones"),
                "AE38": _Inst("Bono USD 2038", "Bonos")}, conn, leer)
    assert pedidos == ["AE38"]


def test_sin_conn_sigue_funcionando_con_la_descripcion():
    """La vista puede llamar sin base; la descripción alcanza."""
    r = v.resolver({"AN29": _Inst("Bono Tesoro Nacional Vto. 30/11/2029")})
    assert r["AN29"].fecha == date(2029, 11, 30)
    assert r["AN29"].fuente == "descripcion"
