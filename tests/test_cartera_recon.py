"""Reconciliación: posiciones de la app == `Resumen Cartera` del Excel.

Gate del módulo (regla dura: portar matemática del Excel exige reconciliar
fila-a-fila). Parte del crudo del Excel, lo procesa con NUESTRO parser +
lógica de posiciones, y exige que cada ticker calce con la cantidad actual
que calcula la planilla.

Depende del Excel real (no versionado). Se SALTEA elegantemente si:
  * no se encuentra el archivo (ruta por `CARTERA_XLSX` o candidatos default), o
  * el Excel todavía no fue recalculado (sin valores cacheados en Resumen):
    abrilo una vez en Excel/LibreOffice para que calcule y reintentá.

Así corre localmente (donde Franco tiene el archivo) y no rompe CI.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from places.inversiones.cartera.ingest import instrumentos_desde_config
from places.inversiones.cartera.parser import parse_archivo_excel
from places.inversiones.cartera.posiciones import posiciones


def _ruta_excel() -> Path | None:
    env = os.environ.get("CARTERA_XLSX")
    candidatos = [Path(env)] if env else []
    candidatos += [
        Path.home() / "OneDrive/Desktop/Finanzas Personales/Cartera personal/Inversiones.xlsx",
        Path.home() / "Desktop/Finanzas Personales/Cartera personal/Inversiones.xlsx",
    ]
    for c in candidatos:
        if c.exists():
            return c
    return None


def _resumen_cacheado(ruta: Path) -> dict[str, float]:
    """ticker → cantidad actual (col G) desde los valores cacheados del Excel."""
    import openpyxl
    wb = openpyxl.load_workbook(ruta, data_only=True)
    try:
        rc = wb["Resumen Cartera"]
        out = {}
        for r in range(4, 80):
            t = rc.cell(r, 1).value
            g = rc.cell(r, 7).value
            if t and isinstance(g, (int, float)):
                out[str(t)] = float(g)
        return out
    finally:
        wb.close()


def _costos_usd_excel(ruta: Path) -> tuple[dict[str, float], float | None]:
    """ticker → Costo Total USD (col H) + el MEP único que usa el Excel."""
    import openpyxl
    wb = openpyxl.load_workbook(ruta, data_only=True)
    try:
        rc = wb["Resumen Cartera"]
        mep = wb["Apoyo"]["G15"].value
        out = {}
        for r in range(4, 80):
            t = rc.cell(r, 1).value
            h = rc.cell(r, 8).value
            if t and isinstance(h, (int, float)):
                out[str(t)] = float(h)
        return out, (float(mep) if isinstance(mep, (int, float)) else None)
    finally:
        wb.close()


#: Tickers cuyo costo divergirá SIEMPRE del Excel, a propósito: su saldo
#: inicial sintético está denominado en **USD** (lo delatan sus precios y que
#: las 3 compras suman exacto el depósito que las cubre), pero el export no
#: trae columna Moneda en esas filas y el Excel las computa como ARS,
#: subvaluando el costo inicial ~1.500 veces. La app lo corrige.
_DIVERGEN_POR_SALDO_INICIAL = {"AE38", "GGAL", "BITCOIN"}


@pytest.fixture(scope="module")
def excel() -> Path:
    ruta = _ruta_excel()
    if ruta is None:
        pytest.skip("Excel de cartera no disponible (definí CARTERA_XLSX). Recon local.")
    return ruta


def test_posiciones_reconcilian_con_resumen_cartera(excel):
    esperado = _resumen_cacheado(excel)
    if not esperado:
        pytest.skip(
            "El Excel no tiene valores cacheados de Resumen Cartera. Abrilo una "
            "vez en Excel/LibreOffice para que recalcule y reintentá el recon."
        )
    instrumentos = instrumentos_desde_config(excel)
    movimientos = parse_archivo_excel(
        excel, hoja="Movimientos Crudo", instrumentos=instrumentos
    )
    # IMPORTANTE: `posiciones()` se llama SIN instrumentos a propósito.
    # Así se compara el mismo plano que calcula el Excel: cantidades brutas
    # (compradas − vendidas). El cierre de posiciones vencidas —que la app
    # aplica cuando Config marca el instrumento como inactivo— es una capa
    # propia y deliberada por encima del Excel: la planilla deja las letras
    # amortizadas con cantidad residual. Pasar `instrumentos` acá haría fallar
    # el recon por esa mejora, no por un error.
    pos = posiciones(movimientos)

    difs = []
    for ticker, cant_excel in esperado.items():
        nuestra = pos[ticker].cant_actual if ticker in pos else 0.0
        if abs(nuestra - cant_excel) > 1e-6:
            difs.append((ticker, nuestra, cant_excel))

    assert not difs, (
        "Posiciones de la app que NO reconcilian con Resumen Cartera "
        f"(ticker, app, excel): {difs}"
    )


def test_costos_usd_reconcilian_modo_mep_actual(excel):
    """Gate del paso 5: los COSTOS en dólares calzan con el Excel cuando se
    usa su misma metodología — un **único MEP actual** para convertir todo
    (ADR-0003). La vista de la app usa el TC histórico por operación, que es
    más fiel; este test verifica que el motor reproduce también el modo Excel.

    Fórmula replicada (col K de `Movimientos Procesado`, sumada en col H de
    `Resumen Cartera`)::

        monto_usd = monto            si la moneda es USD
                    monto / MEP      si es ARS
    """
    esperado, mep = _costos_usd_excel(excel)
    if not esperado or not mep:
        pytest.skip(
            "El Excel no tiene valores cacheados. Abrilo una vez para que "
            "recalcule y reintentá el recon."
        )

    instrumentos = instrumentos_desde_config(excel)
    movimientos = parse_archivo_excel(
        excel, hoja="Movimientos Crudo", instrumentos=instrumentos
    )

    # Costo por ticker con la metodología del Excel (MEP único).
    nuestro: dict[str, float] = {}
    for m in movimientos:
        if m.categoria != "COMPRA" or not m.es_instrumento or m.es_espejo:
            continue
        monto_usd = -m.monto if m.moneda == "USD" else -m.monto / mep
        nuestro[m.ticker_base] = nuestro.get(m.ticker_base, 0.0) + monto_usd

    difs = []
    for ticker, costo_excel in esperado.items():
        if abs(costo_excel) < 0.01:
            continue
        if ticker in _DIVERGEN_POR_SALDO_INICIAL:
            continue
        propio = nuestro.get(ticker, 0.0)
        # tolerancia de 1 centavo por dólar (redondeos del Excel)
        if abs(propio - costo_excel) > max(0.5, abs(costo_excel) * 0.001):
            difs.append((ticker, round(propio, 2), round(costo_excel, 2)))

    assert not difs, (
        "Costos USD que NO reconcilian con el Excel en modo MEP actual "
        f"(ticker, app, excel): {difs}"
    )


def test_saldos_iniciales_divergen_del_excel_a_proposito(excel):
    """El contrario del anterior: documenta y CONGELA la divergencia conocida.

    Los saldos iniciales sintéticos están en USD y el Excel los toma como ARS,
    así que su costo en la planilla es ~1.500 veces menor. Si algún día el
    Excel se corrige, este test falla y avisa que hay que quitar la excepción.
    """
    esperado, mep = _costos_usd_excel(excel)
    if not esperado or not mep:
        pytest.skip("El Excel no tiene valores cacheados.")
    # AE38: el saldo inicial son US$5.850,10; el Excel lo computa como
    # 5.850,10 pesos → ~US$3,85.
    costo_ae38 = esperado.get("AE38")
    if costo_ae38 is None:
        pytest.skip("AE38 no está en el Resumen del Excel.")
    assert costo_ae38 < 100, (
        "El Excel ya no subvalúa el saldo inicial de AE38 "
        f"(costo USD = {costo_ae38}): revisar si sigue haciendo falta la "
        "excepción de _DIVERGEN_POR_SALDO_INICIAL."
    )
