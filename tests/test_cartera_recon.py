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
