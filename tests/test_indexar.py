"""El indexador del mapa no puede leer lo que el `.gitignore` excluye.

**Por qué existe.** Hasta el 22/9/2026, en Windows, `ignorado()` comparaba la
ruta (con `\\`) contra los patrones del `.gitignore` (con `/`) y nunca
coincidían las carpetas. El `MAPA.md` —que se commitea— listaba `Borrar/` como
carpeta del proyecto y extraía "fuentes externas" de los `.db-shm` de los
backups de producción en `backups-remotos/`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_RUTA = Path(__file__).resolve().parents[1] / "scripts" / "indexar.py"
_spec = importlib.util.spec_from_file_location("indexar", _RUTA)
indexar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(indexar)

PATS = indexar.cargar_gitignore(_RUTA.parents[1])


@pytest.mark.parametrize("rel", [
    r"backups-remotos\superapp-20260826-233323.db-shm",
    "backups-remotos/superapp-20260826-233323.db-shm",
    r"backups-remotos\backup.log",
    r"Borrar\scoring-retirado-1786650535\view.py",
    r"data\finanzas.db-wal",
    r"data\backups\finanzas-20260901.db",
    ".env",
])
def test_lo_ignorado_por_git_no_se_indexa(rel):
    assert indexar.ignorado(rel, PATS)


@pytest.mark.parametrize("rel", [
    r"places\inversiones\cartera\view.py",
    r"core\db.py",
    "ESTADO.md",
])
def test_el_codigo_si_se_indexa(rel):
    assert not indexar.ignorado(rel, PATS)
