"""Datos-oráculo: los archivos personales que la suite necesita y CI no tiene.

**Los tests-oráculo y por qué se saltean en CI.**

Algunos tests no verifican lógica contra casos sintéticos: verifican los
**números reales** de Franco contra una fuente de verdad externa. Son los más
valiosos del repo —son los que atajaron los errores de cálculo de la Fase 3a—
pero necesitan archivos que **por regla dura del proyecto nunca se versionan**:

* ``Diario.csv`` y ``Mensual.csv`` → `test_kpis.py`, `test_reconciliacion.py`.
  Contienen todos los gastos e ingresos personales.

En CI esos archivos no existen y no deben existir. La convención del repo,
establecida por el gate de reconciliación de la Fase 3a, es **saltearlos con
un motivo explícito**, no ocultarlos ni alimentarlos con datos falsos:

* con datos falsos el test *pasaría sin probar nada* — `test_kpis.py` compara
  contra importes exactos ($15.014.431 de ingreso anual, entre otros), así que
  un CSV inventado o lo hace fallar, o obliga a cambiar los valores esperados
  y ahí el test deja de proteger;
* con ``--ignore`` en el workflow desaparecen de la salida y nadie se entera
  de que existen.

Salteándolos, CI queda verde y **el conteo de `skipped` deja el rastro**: si
algún día aparecen 20 skips en vez de los esperados, es una señal.

⚠️ **Esto implica que los oráculos solo corren en la máquina de Franco.**
Antes de un deploy, la suite se corre local — ahí no se saltea ninguno.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Se respetan las mismas variables de entorno que usa `ingest.py`, así que
#: los CSV pueden vivir fuera del repo sin tocar código.
DIARIO_CSV = Path(os.environ.get("DIARIO_CSV", REPO_ROOT / "Diario.csv"))
MENSUAL_CSV = Path(os.environ.get("MENSUAL_CSV", REPO_ROOT / "Mensual.csv"))

_MOTIVO = (
    "Test-oráculo: necesita los CSV personales ({faltan}), que por regla dura "
    "del repo nunca se versionan. Corre en la máquina de Franco, no en CI. "
    "Si los tenés en otro lado, exportá DIARIO_CSV y MENSUAL_CSV."
)


def csv_personales_disponibles() -> bool:
    return DIARIO_CSV.exists() and MENSUAL_CSV.exists()


def saltear_si_faltan_csv() -> None:
    """Saltea el test en curso si no están los CSV personales."""
    faltan = [str(p) for p in (DIARIO_CSV, MENSUAL_CSV) if not p.exists()]
    if faltan:
        pytest.skip(_MOTIVO.format(faltan=", ".join(faltan)))


