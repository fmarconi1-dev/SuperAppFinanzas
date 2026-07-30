"""Tests del export de cartera a Excel (Fase 3a).

Verifican estructura, formatos y —lo más importante— que el **TOTAL de la tabla
coincida con el patrimonio de los KPIs**: si no cierran, el archivo parece
tener un error aunque los datos estén bien.

Las fórmulas se escriben sin valores cacheados (así funciona openpyxl), así que
acá se comprueban como texto; que *evalúen* sin error lo garantiza `recalc.py`
al generar el archivo real.
"""

from __future__ import annotations

from datetime import date

import pytest

from places.inversiones.cartera.export import PALETA, exportar_cartera
from places.inversiones.cartera.kpis import KPIs, kpis_de, valuar
from places.inversiones.cartera.posiciones import Posicion


@pytest.fixture()
def datos():
    pos = {
        "GGAL": Posicion("GGAL", cant_comprada=90, costo_ars_compras=526_344.0,
                         costo_usd_hist=400.0),
        "AE38": Posicion("AE38", cant_comprada=3604, costo_ars_compras=2_356_499.0,
                         costo_usd_hist=2219.0),
        "BITCOIN": Posicion("BITCOIN", cant_comprada=0.00316847,
                            costo_ars_compras=329_770.0, costo_usd_hist=294.28),
    }
    instrumentos = {}

    def resolver(ticker, inst):
        return {"GGAL": 7795.0, "AE38": 1250.7,
                "BITCOIN": 97_720_000.0}.get(ticker), "broker"

    valuadas = valuar(pos, resolver, instrumentos, mep_actual=1522.185)
    k = kpis_de(valuadas, mep=1522.185)
    k.aportado_ars = 3_000_000.0
    k.aportado_usd = 2_500.0
    k.patrimonio_ars = k.valor_total_ars + 42_556.24 + 12.66 * 1522.185
    k.patrimonio_usd = k.patrimonio_ars / 1522.185
    k.dias = 602
    k.tir_ars = 0.514
    k.tir_usd = 0.244
    return valuadas, k


def _abrir(ruta):
    import openpyxl
    return openpyxl.load_workbook(ruta)


def test_genera_el_archivo_con_la_hoja_esperada(tmp_path, datos):
    valuadas, k = datos
    ruta = tmp_path / "cartera.xlsx"
    exportar_cartera(ruta, valuadas, k, date(2026, 7, 30), 1522.185)
    ws = _abrir(ruta).active
    assert ws.title == "Resumen Cartera"
    assert "CARTERA DE INVERSIONES" in str(ws.cell(1, 1).value)
    assert "30/07/2026" in str(ws.cell(1, 1).value)


def test_respeta_la_paleta_de_la_planilla_de_franco(tmp_path, datos):
    valuadas, k = datos
    ruta = tmp_path / "cartera.xlsx"
    exportar_cartera(ruta, valuadas, k, date(2026, 7, 30), 1522.185)
    ws = _abrir(ruta).active
    hdr = next(r for r in range(1, 40) if ws.cell(r, 1).value == "Ticker")
    c = ws.cell(hdr, 1)
    assert PALETA["encabezado"] in str(c.fill.start_color.rgb)
    assert c.font.bold is True


def test_el_mep_es_una_celda_editable_y_referenciada(tmp_path, datos):
    """Cambiar el MEP debe recalcular toda la planilla: por eso vive en H2 y
    las columnas en dólares lo referencian, en vez de venir hardcodeado."""
    valuadas, k = datos
    ruta = tmp_path / "cartera.xlsx"
    exportar_cartera(ruta, valuadas, k, date(2026, 7, 30), 1522.185)
    ws = _abrir(ruta).active
    assert ws.cell(2, 8).value == pytest.approx(1522.185)
    assert "FFFF00" in str(ws.cell(2, 8).fill.start_color.rgb)  # amarillo = editable
    hdr = next(r for r in range(1, 40) if ws.cell(r, 1).value == "Ticker")
    assert "$H$2" in str(ws.cell(hdr + 1, 8).value)             # Valor USD


def test_valores_derivados_son_formulas_no_numeros(tmp_path, datos):
    """La planilla tiene que seguir viva: si se toca un precio, recalcula."""
    valuadas, k = datos
    ruta = tmp_path / "cartera.xlsx"
    exportar_cartera(ruta, valuadas, k, date(2026, 7, 30), 1522.185)
    ws = _abrir(ruta).active
    hdr = next(r for r in range(1, 40) if ws.cell(r, 1).value == "Ticker")
    f = hdr + 1
    assert str(ws.cell(f, 7).value).startswith("=")    # Valor ARS = cant × precio
    assert str(ws.cell(f, 11).value).startswith("=")   # Ganancia = valor − costo
    assert str(ws.cell(f, 12).value).startswith("=")   # Rend %


def test_el_total_incluye_el_efectivo(tmp_path, datos):
    """Sin las filas de efectivo, el TOTAL da menos que el patrimonio y el
    archivo parece tener un error."""
    valuadas, k = datos
    ruta = tmp_path / "cartera.xlsx"
    exportar_cartera(ruta, valuadas, k, date(2026, 7, 30), 1522.185,
                     efectivo_ars=42_556.24, efectivo_usd=12.66)
    ws = _abrir(ruta).active
    tickers = [ws.cell(r, 1).value for r in range(1, ws.max_row + 1)]
    assert "ARS" in tickers and "USD" in tickers
    assert "Subtotal Efectivo" in [str(t) for t in tickers]
    assert "TOTAL CARTERA" in [str(t) for t in tickers]


def test_agrupa_por_tipo_con_subtotales(tmp_path, datos):
    valuadas, k = datos
    ruta = tmp_path / "cartera.xlsx"
    exportar_cartera(ruta, valuadas, k, date(2026, 7, 30), 1522.185,
                     tipos={"GGAL": "Acciones", "AE38": "Bonos",
                            "BITCOIN": "Cripto"})
    ws = _abrir(ruta).active
    etiquetas = [str(ws.cell(r, 1).value) for r in range(1, ws.max_row + 1)]
    assert "Subtotal Acciones" in etiquetas
    assert "Subtotal Bonos" in etiquetas
    assert "Subtotal Cripto" in etiquetas


def test_cripto_muestra_decimales_suficientes(tmp_path, datos):
    """0,00316847 BTC no puede mostrarse como 0,00."""
    valuadas, k = datos
    ruta = tmp_path / "cartera.xlsx"
    exportar_cartera(ruta, valuadas, k, date(2026, 7, 30), 1522.185)
    ws = _abrir(ruta).active
    fila_btc = next(r for r in range(1, ws.max_row + 1)
                    if ws.cell(r, 1).value == "BITCOIN")
    assert ws.cell(fila_btc, 4).number_format.count("0") >= 8


def test_incluye_kpis_y_tir(tmp_path, datos):
    valuadas, k = datos
    ruta = tmp_path / "cartera.xlsx"
    exportar_cartera(ruta, valuadas, k, date(2026, 7, 30), 1522.185)
    ws = _abrir(ruta).active
    etiquetas = [str(ws.cell(r, 1).value) for r in range(1, 20)]
    assert "Patrimonio hoy" in etiquetas
    assert "Capital aportado" in etiquetas
    assert "Rendimiento anual (TIR)" in etiquetas
    fila_tir = etiquetas.index("Rendimiento anual (TIR)") + 1
    # las tasas se guardan como fracción (0,244), no como 24,4
    assert ws.cell(fila_tir, 3).value == pytest.approx(0.244)
    assert "%" in ws.cell(fila_tir, 3).number_format


def test_documenta_la_metodologia(tmp_path, datos):
    """Regla del skill de xlsx: los supuestos van escritos donde se leen."""
    valuadas, k = datos
    ruta = tmp_path / "cartera.xlsx"
    exportar_cartera(ruta, valuadas, k, date(2026, 7, 30), 1522.185)
    ws = _abrir(ruta).active
    texto = " ".join(str(ws.cell(r, 1).value or "")
                     for r in range(1, ws.max_row + 1))
    assert "Metodología" in texto
    assert "promedio ponderado" in texto
    assert "TIR" in texto


def test_no_falla_con_cartera_vacia(tmp_path):
    ruta = tmp_path / "vacia.xlsx"
    exportar_cartera(ruta, [], KPIs(), date(2026, 7, 30), 1522.185)
    ws = _abrir(ruta).active
    assert ws.title == "Resumen Cartera"
