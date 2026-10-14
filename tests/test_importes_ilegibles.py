"""Un importe que no se puede leer no puede entrar como $0 en silencio.

**Por qué existe (22/9/2026).** `parse_currency` devolvía 0.0 ante un importe
ilegible y el comentario decía que "la capa de ingest registra el incidente"
— pero el ingest no registraba nada. Un ``1.5OO`` (con letra O) entraba como
un gasto de $0 sin rastro. En Cartera, además, ``1,234.56`` (formato de EE.UU.)
se leía como **1,23** sin error (trampa 6: sospechá de la cantidad).

Y de paso: el CLI del ingest (`python -m places.finanzas.core.ingest`) estaba
roto por un `sys.path` heredado; los tests no lo veían porque importaban el
`core` bueno antes.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from core import db as core_db
from places.finanzas.core.parsers import parse_currency, parse_currency_estricto

RAIZ = Path(__file__).resolve().parents[1]


# --- Finanzas --------------------------------------------------------------

@pytest.mark.parametrize("raw", ["1.5OO", "$ 1.500 ARS", "doce", "1,2,3x"])
def test_un_ilegible_es_none_y_no_cero(raw):
    assert parse_currency_estricto(raw) is None
    assert parse_currency(raw) == 0.0          # compat: no corrompe Caja


@pytest.mark.parametrize("raw,esperado", [
    ("$2.700.000,00", 2700000.0), (" $-   ", 0.0), ("", 0.0), (None, 0.0),
    ("-$32.520,00", -32520.0),
])
def test_lo_legible_no_cambia(raw, esperado):
    assert parse_currency_estricto(raw) == esperado


def test_el_ingest_avisa_el_importe_ilegible(tmp_path, monkeypatch):
    from places.finanzas.core.ingest import run_import

    monkeypatch.setenv("DB_PATH", str(tmp_path / "f.db"))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    diario = tmp_path / "Diario.csv"
    diario.write_text(
        "Fecha;Pasivos;Ingresos;Motivo;Caja\n"
        "1/1/2026;;;Caja;$1.000,00\n"
        "2/1/2026;$1.5OO,00;;Supermercado;\n"
        "3/1/2026;$200,00;;Salidas;\n",
        encoding="latin-1")
    mensual = tmp_path / "Mensual.csv"
    mensual.write_text("INGRESOS Y GASTOS;Ene\nSupermercado;$x\n", encoding="latin-1")

    r = run_import(diario, mensual, anio=2026)

    assert r.transacciones_insertadas == 2          # la fila no se pierde...
    assert any("fila 3" in a and "1.5OO" in a for a in r.advertencias)  # ...y se avisa
    assert any("Mensual" in a for a in r.advertencias)


def test_el_cli_del_ingest_arranca():
    """`python -m places.finanzas.core.ingest` es como se reimportan los CSV."""
    r = subprocess.run([sys.executable, "-m", "places.finanzas.core.ingest", "--help"],
                       cwd=RAIZ, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
