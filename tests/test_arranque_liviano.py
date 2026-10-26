"""Arranque liviano: lo pesado se importa recién cuando hace falta.

**Por qué existe (21/10/2026, frente 2 de rendimiento).** Fly apaga la máquina
cuando no hay tráfico (`min_machines_running = 0`): después de un rato, el
primer mensaje de WhatsApp y la primera visita pagan el arranque entero de
Python. La API tardaba 1,1 s en importarse, casi todo pandas (por `metrics`) y
openpyxl (por `extracto_galicia`), que cargar un gasto no usa. Y el Inicio
traía las cinco vistas de Finanzas, con Plotly Express y el export a Excel,
aunque nadie abriera Finanzas.

Cada chequeo corre en un **proceso nuevo**: en el de pytest ya está todo
importado.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _modulos_tras_importar(modulo: str) -> set[str]:
    codigo = f"import json, sys; import {modulo}; print(json.dumps(sorted(sys.modules)))"
    salida = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True,
                            text=True, timeout=120, check=True).stdout
    return set(json.loads(salida.strip().splitlines()[-1]))


def test_la_api_arranca_sin_pandas_ni_openpyxl():
    cargados = _modulos_tras_importar("api")
    assert "pandas" not in cargados
    assert "openpyxl" not in cargados


def test_finanzas_no_importa_sus_vistas_hasta_abrir_la_pestana():
    cargados = _modulos_tras_importar("places.finanzas.home")
    vistas = {m for m in cargados if m.startswith("places.finanzas.views.")}
    assert vistas == {"places.finanzas.views.onboarding"}
    assert "plotly.express" not in cargados
    assert "openpyxl" not in cargados
