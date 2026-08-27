# tests/

<!-- huella: feb2186c897b -->

Resumen: La suite completa (~360 tests) en carpeta plana: unidad + regresión + gates de reconciliación contra el Excel-oráculo. Es el gate del repo: nada se cierra sin verde.

## Buscar acá si

- el gate de reconciliación contra el Excel → `test_cartera_recon.py` (necesita `CARTERA_XLSX`; sin él se saltea con mensaje claro, por eso "3 skipped" es normal)
- tests que escanean el código fuente: `test_nombres_definidos.py` (AST de names), `test_transacciones_formulario.py` (ramas del form), `test_env_example_sin_secretos.py`
- los CSV oráculo de Finanzas → `_oraculos.py` (`DIARIO_CSV`/`MENSUAL_CSV`)
- convención de nombres: `test_cartera_*` → cartera · `test_market_data_*` → core/market_data · `test_backup_*`/`test_db_*`/`test_workspaces_*` → core · el resto → Finanzas
- los premortem-tests (`test_premortem3/5.py`): regresiones de los riesgos del premortem

## Trampas

- Correr con el **Python 3.11 del `.venv`** (misma versión que el Dockerfile); con 3.14 la suite ni colecta.
- `_oraculos.py` lee los CSV de la raíz: no los muevas sin tocar los env vars.

## Estado

- **Funciona:** ~360 en verde en CI (recon local con Excel).

## Proximo paso

—
