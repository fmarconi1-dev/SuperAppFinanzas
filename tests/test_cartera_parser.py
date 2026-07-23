"""Tests del parser del broker (Fase 3a — Cartera nativa).

Cubre ambos formatos del export, las 12 categorías, la inferencia de moneda
(la columna del archivo NO es confiable), bonos que cotizan cada 100 nominales,
saldos iniciales sintéticos, el espejo de dividendos/renta (formato viejo Y
nuevo) y el hash de dedupe. Los datos están calcados de patrones reales de
`Inversiones.xlsx` (hoja Movimientos Crudo).

Columnas del export:
  viejo: Operación | Concertación | Liquidación | Descripción | Monto |
         Cantidad | Precio | Moneda
  nuevo: (sin Operación) Concertación | Liquidación | Descripción | Monto |
         Cantidad | Precio | Moneda
"""

from __future__ import annotations

import datetime as _dt
from datetime import date

import pytest

from places.inversiones.cartera.parser import (
    CATEGORIAS,
    MAPA_OPERACION,
    Instrumento,
    parse_archivo_csv,
    parse_filas,
)

HDR = [
    "Operación", "Concertación", "Liquidación", "Descripción",
    "Monto", "Cantidad", "Precio", "Moneda",
]


@pytest.fixture
def instrumentos():
    """Mapping ticker→Instrumento (equivalente a Config!G:N), calcado del Excel."""
    I = Instrumento
    insts = [
        I("SPY", "SPYD", "Cedears", "ARS"),
        I("TSM", "TSMD", "Cedears", "ARS"),
        I("NVDA", "NVDAD", "Cedears", "ARS"),
        I("GOOGL", "GOGLD", "Cedears", "ARS"),   # variante USD es GOGLD
        I("GGAL", "GGALD", "Acciones", "ARS"),
        I("AE38", "AE38D", "Bonos", "USD/100"),  # bono hard-dollar
        I("TTJ26", "TTJ26D", "Bonos", "ARS/100"),
        I("RUCDO", "RUCDD", "ONs", "USD/100"),
        I("BITCOIN", "BITCOIN", "Cripto", "USD"),
    ]
    return {i.ticker: i for i in insts}


def _uno(filas, instrumentos):
    """Parsea `filas` y exige que salga exactamente un Movimiento."""
    movs = parse_filas(filas, instrumentos)
    assert len(movs) == 1, f"esperaba 1 movimiento, salieron {len(movs)}"
    return movs[0]


# ---------------------------------------------------------------------------
# Detección de formato
# ---------------------------------------------------------------------------

def test_detecta_formato_viejo(instrumentos):
    fila = ["Compra", "2026-01-10", "2026-01-12", "GGAL | Grupo", -1000, 10, 100, "ARS"]
    m = _uno([fila], instrumentos)
    assert m.formato == "viejo"
    assert m.operacion_original == "Compra"


def test_detecta_formato_nuevo(instrumentos):
    fila = ["2026-05-20", "2026-05-21", "NBIS | CEDEAR NEBIUS GROUP", -219192.79, 20, 10920, "ARS"]
    m = _uno([fila], instrumentos)
    assert m.formato == "nuevo"
    assert m.operacion_original is None


def test_formato_nuevo_con_datetime(instrumentos):
    fila = [_dt.datetime(2026, 6, 24), _dt.datetime(2026, 6, 25),
            "NBIS | CEDEAR NEBIUS GROUP", -73867.17, 5, 14720, "ARS"]
    m = _uno([fila], instrumentos)
    assert m.formato == "nuevo"
    assert m.categoria == "COMPRA"


def test_ignora_encabezado_y_filas_vacias(instrumentos):
    filas = [
        HDR,
        [None] * 8,
        ["", "", "", "", "", "", "", ""],
        ["Compra", "2026-01-10", "2026-01-12", "GGAL | Grupo", -1000, 10, 100, "ARS"],
    ]
    assert len(parse_filas(filas, instrumentos)) == 1


# ---------------------------------------------------------------------------
# Categorías — formato viejo (mapeo Config!A5:B16)
# ---------------------------------------------------------------------------

def test_mapa_operacion_cubre_las_12_categorias():
    assert len(CATEGORIAS) == 12
    assert set(MAPA_OPERACION.values()) == set(CATEGORIAS)


@pytest.mark.parametrize("operacion,categoria", [
    ("Compra", "COMPRA"),
    ("Venta", "VENTA"),
    ("Ingreso dividendo", "DIVIDENDO"),
    ("Renta", "RENTA"),
    ("Amortización", "AMORTIZACION"),
    ("Retención impositiva", "RETENCION"),
    ("Caución colocadora", "CAUCION_COL"),
    ("Depósito", "DEPOSITO"),
    ("Retiro", "RETIRO"),
    ("Remuneración", "REMUNERACION"),
    ("Otros", "OTROS"),
])
def test_categorias_formato_viejo(instrumentos, operacion, categoria):
    fila = [operacion, "2026-01-10", "2026-01-10", "GGAL | Grupo", 100, None, 0, "ARS"]
    assert _uno([fila], instrumentos).categoria == categoria


def test_vencimiento_de_caucion_es_caucion_vto(instrumentos):
    fila = ["Vencimiento", "2026-01-10", "2026-01-11", "CC | Caución colocadora", 187300, None, None, "ARS"]
    assert _uno([fila], instrumentos).categoria == "CAUCION_VTO"


def test_vencimiento_no_caucion_cae_en_amortizacion(instrumentos):
    fila = ["Vencimiento", "2026-01-10", "2026-01-11", "AE38 | Bono USD 2038", 1000, None, None, "ARS"]
    assert _uno([fila], instrumentos).categoria == "AMORTIZACION"


def test_operacion_desconocida_cae_en_otros_con_advertencia(instrumentos):
    fila = ["Bonificación rara", "2026-01-10", "2026-01-10", "algo", 100, None, 0, "ARS"]
    m = _uno([fila], instrumentos)
    assert m.categoria == "OTROS"
    assert any("desconocida" in a.lower() for a in m.advertencias)


# ---------------------------------------------------------------------------
# Categorías — formato nuevo (inferencia por signo/descripción)
# ---------------------------------------------------------------------------

def test_infiere_compra_nuevo(instrumentos):
    fila = ["2026-05-20", "2026-05-21", "NBIS | CEDEAR NEBIUS", -219192.79, 20, 10920, "ARS"]
    assert _uno([fila], instrumentos).categoria == "COMPRA"


def test_infiere_venta_nuevo(instrumentos):
    fila = ["2026-05-19", "2026-05-20", "GOOGL | Google Inc.", 247348.85, -25, 9930, "ARS"]
    assert _uno([fila], instrumentos).categoria == "VENTA"


def test_infiere_caucion_col_y_vto_nuevo(instrumentos):
    col = ["2026-06-24", "2026-06-24", "CC | Caución colocadora del 24/06", -374009, None, 0, "ARS"]
    vto = ["2026-06-24", "2026-06-25", "CC | Caución colocadora", 374193, None, 0, "ARS"]
    assert _uno([col], instrumentos).categoria == "CAUCION_COL"
    assert _uno([vto], instrumentos).categoria == "CAUCION_VTO"


def test_infiere_remuneracion_deposito_retiro_nuevo(instrumentos):
    rem = ["2026-01-09", "2026-01-09", "Rendimiento diario sobre $187.183,35", 147.46, None, None, "ARS"]
    dep = ["2026-01-09", "2026-01-09", "Recibo de Cobro / 40006", 50000, None, None, "ARS"]
    ret = ["2026-01-09", "2026-01-09", "Comprobante de pago / 123", -50000, None, None, "ARS"]
    assert _uno([rem], instrumentos).categoria == "REMUNERACION"
    assert _uno([dep], instrumentos).categoria == "DEPOSITO"
    assert _uno([ret], instrumentos).categoria == "RETIRO"


def test_infiere_dividendo_y_renta_sin_cantidad_nuevo(instrumentos):
    div = ["2026-06-29", "2026-06-29", "NVDAD | NVIDIA", 0.2, None, 0, "USD"]
    renta = ["2026-01-09", "2026-01-09", "AE38D | Bono USD 2038", 236.31, None, None, "ARS"]
    assert _uno([div], instrumentos).categoria == "DIVIDENDO"
    assert _uno([renta], instrumentos).categoria == "RENTA"


# ---------------------------------------------------------------------------
# Inferencia de moneda (la columna del archivo no se confía)
# ---------------------------------------------------------------------------

def test_moneda_cedear_base_es_ars_y_variante_usd(instrumentos):
    base = _uno([["Ingreso dividendo", "2026-04-30", "2026-04-30", "SPY | SPDR", -264.13, None, 0, "ARS"]], instrumentos)
    dvar = _uno([["Ingreso dividendo", "2026-04-30", "2026-04-30", "SPYD | SPDR", 3.75, None, 0, "ARS"]], instrumentos)
    assert base.moneda == "ARS"
    assert dvar.moneda == "USD"                       # inferida, aunque el archivo diga ARS
    assert any("difiere" in a for a in dvar.advertencias)


def test_moneda_bono_hard_dollar_base_es_ars_con_advertencia(instrumentos):
    # AE38 (base) se opera en pesos aunque el archivo lo marque USD.
    m = _uno([["Compra", "2026-01-10", "2026-01-12", "AE38 | Bono USD 2038", -1000000, 1000, 95.0, "USD"]], instrumentos)
    assert m.moneda == "ARS"
    assert m.advertencias


def test_moneda_bitcoin_es_usd(instrumentos):
    m = _uno([["Compra", "2024-12-05", "2024-12-05", "BITCOIN | Bitcoin", -294.28, 0.003, 98094.78, None]], instrumentos)
    assert m.moneda == "USD"


def test_moneda_desconocida_declara_usd_pero_magnitud_es_ars(instrumentos):
    m = _uno([["Compra", "2026-01-10", "2026-01-12", "XXXX | Desconocido", -500000, 10, 50000, "USD"]], instrumentos)
    assert m.moneda == "ARS"
    assert m.advertencias


# ---------------------------------------------------------------------------
# Precio normalizado (bonos /100) y es_instrumento
# ---------------------------------------------------------------------------

def test_precio_normalizado_de_bono(instrumentos):
    m = _uno([["Compra", "2026-01-10", "2026-01-12", "AE38 | Bono", -1000000, 1000, 95.0, "ARS"]], instrumentos)
    assert m.precio == 95.0
    assert m.precio_normalizado == pytest.approx(0.95)


def test_precio_de_cedear_no_se_normaliza(instrumentos):
    m = _uno([["Compra", "2026-01-10", "2026-01-12", "GGAL | Grupo", -1000, 10, 100, "ARS"]], instrumentos)
    assert m.precio_normalizado is None


def test_es_instrumento(instrumentos):
    compra = _uno([["Compra", "2026-01-10", "2026-01-12", "GGAL | Grupo", -1000, 10, 100, "ARS"]], instrumentos)
    caucion = _uno([["Caución colocadora", "2026-01-10", "2026-01-10", "CC | Caución", -1000, None, None, "ARS"]], instrumentos)
    deposito = _uno([["Depósito", "2026-01-10", "2026-01-10", "Recibo de Cobro", 1000, None, None, "ARS"]], instrumentos)
    assert compra.es_instrumento is True
    assert caucion.es_instrumento is False
    assert deposito.es_instrumento is False


# ---------------------------------------------------------------------------
# Saldos iniciales sintéticos (regla del LEEME: NO eliminar)
# ---------------------------------------------------------------------------

def test_saldo_inicial_con_parentesis(instrumentos):
    m = _uno([["Compra", "2024-12-05", "2024-12-05", "AE38D | Bono USD 2038 (Saldo inicial)", -5850.1, 9500, 0.6158, None]], instrumentos)
    assert m.es_saldo_inicial is True


def test_saldo_inicial_sintetico_sin_parentesis(instrumentos):
    # El bug arreglado: el texto arranca con "Saldo inicial" (sin '(').
    m = _uno([["Depósito", "2024-12-05", "2024-12-05", "Saldo inicial sintetico (cubre AE38 + BITCOIN iniciales)", 6593.38, None, 0, None]], instrumentos)
    assert m.es_saldo_inicial is True
    assert m.categoria == "DEPOSITO"


# ---------------------------------------------------------------------------
# Espejo de dividendos/renta (solo cuenta la línea USD)
# ---------------------------------------------------------------------------

def test_espejo_dividendo_formato_viejo(instrumentos):
    filas = [
        ["Ingreso dividendo", "2026-04-30", "2026-04-30", "SPYD | SPDR", 3.75, None, 0, "ARS"],
        ["Ingreso dividendo", "2026-04-30", "2026-04-30", "SPY | SPDR", -264.13, None, 0, "ARS"],
    ]
    d = {m.ticker_crudo: m for m in parse_filas(filas, instrumentos)}
    assert d["SPY"].es_espejo is True       # base ARS negativa → espejo
    assert d["SPYD"].es_espejo is False     # variante USD → se conserva


def test_espejo_dividendo_formato_nuevo(instrumentos):
    # La regresión clave: en el formato nuevo la pata base se infiere RETENCION
    # y la USD DIVIDENDO; aun con categorías distintas debe aparear el espejo.
    filas = [
        ["2026-06-29", "2026-06-29", "NVDA | NVIDIA Corp", -1.27, None, 0, "ARS", None],
        ["2026-06-29", "2026-06-29", "NVDAD | NVIDIA Corp", 0.2, None, 0, "USD", "ARS"],
    ]
    d = {m.ticker_crudo: m for m in parse_filas(filas, instrumentos)}
    assert d["NVDA"].es_espejo is True
    assert d["NVDAD"].es_espejo is False
    assert d["NVDAD"].categoria == "DIVIDENDO"


def test_espejo_renta_bono_formato_nuevo(instrumentos):
    filas = [
        ["2026-01-09", "2026-01-09", "RUCDD | ON MSU Energy", 1.98, None, None, "USD"],
        ["2026-01-09", "2026-01-09", "RUCDO | ON MSU Energy", -10.17, None, None, "ARS"],
    ]
    d = {m.ticker_crudo: m for m in parse_filas(filas, instrumentos)}
    assert d["RUCDO"].es_espejo is True
    assert d["RUCDD"].es_espejo is False


def test_dividendo_ars_real_de_una_linea_no_es_espejo(instrumentos):
    # GGAL paga dividendo en pesos de una sola línea, sin contraparte USD.
    m = _uno([["Ingreso dividendo", "2026-05-08", "2026-05-08", "GGAL | Grupo", 7416.58, None, 0, "ARS"]], instrumentos)
    assert m.categoria == "DIVIDENDO"
    assert m.es_espejo is False


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

def test_parsea_fechas_datetime(instrumentos):
    fila = ["Compra", _dt.datetime(2026, 1, 10), _dt.datetime(2026, 1, 12), "GGAL | Grupo", -1000, 10, 100, "ARS"]
    m = _uno([fila], instrumentos)
    assert m.fecha_concertacion == date(2026, 1, 10)
    assert m.fecha_liquidacion == date(2026, 1, 12)


def test_parsea_fecha_serial_excel(instrumentos):
    # Serial de Excel para 2026-01-10 = 46032 (epoch 1899-12-30).
    serial = (date(2026, 1, 10) - date(1899, 12, 30)).days
    fila = ["Compra", serial, serial, "GGAL | Grupo", -1000, 10, 100, "ARS"]
    m = _uno([fila], instrumentos)
    assert m.fecha_concertacion == date(2026, 1, 10)


# ---------------------------------------------------------------------------
# Dedupe por hash
# ---------------------------------------------------------------------------

def test_dedupe_hash_distingue_duplicados_del_mismo_archivo(instrumentos):
    fila = ["Compra", "2026-01-10", "2026-01-12", "GGAL | Grupo", -1000, 10, 100, "ARS"]
    movs = parse_filas([fila, list(fila)], instrumentos)
    assert len(movs) == 2
    assert movs[0].hash_dedupe and movs[1].hash_dedupe
    assert movs[0].hash_dedupe != movs[1].hash_dedupe   # contador de ocurrencia


def test_dedupe_hash_es_determinista(instrumentos):
    fila = ["Compra", "2026-01-10", "2026-01-12", "GGAL | Grupo", -1000, 10, 100, "ARS"]
    a = parse_filas([fila], instrumentos)[0].hash_dedupe
    b = parse_filas([list(fila)], instrumentos)[0].hash_dedupe
    assert a == b


def test_dedupe_hash_difiere_por_monto(instrumentos):
    f1 = ["Compra", "2026-01-10", "2026-01-12", "GGAL | Grupo", -1000, 10, 100, "ARS"]
    f2 = ["Compra", "2026-01-10", "2026-01-12", "GGAL | Grupo", -2000, 10, 200, "ARS"]
    h1 = parse_filas([f1], instrumentos)[0].hash_dedupe
    h2 = parse_filas([f2], instrumentos)[0].hash_dedupe
    assert h1 != h2


# ---------------------------------------------------------------------------
# Loader CSV
# ---------------------------------------------------------------------------

def test_parse_archivo_csv(tmp_path, instrumentos):
    csv_texto = (
        "Operación,Concertación,Liquidación,Descripción,Monto,Cantidad,Precio,Moneda\n"
        "Compra,2026-01-10,2026-01-12,GGAL | Grupo,-1000,10,100,ARS\n"
    )
    ruta = tmp_path / "export.csv"
    ruta.write_text(csv_texto, encoding="utf-8")
    movs = parse_archivo_csv(str(ruta), instrumentos)
    assert len(movs) == 1
    assert movs[0].categoria == "COMPRA"
    assert movs[0].ticker_base == "GGAL"
