# tests/

<!-- huella: 4b24113e68be -->

Resumen: La suite completa (909 tests al 27/9/2026) en carpeta plana: unidad + regresión + gates de reconciliación contra el Excel-oráculo. Es el gate del repo: nada se cierra sin verde.

## Buscar acá si

- el gate de reconciliación contra el Excel → `test_cartera_recon.py` (necesita `CARTERA_XLSX`; sin él se saltea con mensaje claro, por eso "3 skipped" es normal)
- tests que escanean el código fuente: `test_nombres_definidos.py` (AST de names), `test_transacciones_formulario.py` (ramas del form), `test_env_example_sin_secretos.py`
- los CSV oráculo de Finanzas → `_oraculos.py` (`DIARIO_CSV`/`MENSUAL_CSV`)
- convención de nombres: `test_cartera_*` → cartera · `test_market_data_*` → core/market_data · `test_backup_*`/`test_db_*`/`test_workspaces_*` → core · el resto → Finanzas
- los premortem-tests (`test_premortem3/5.py`): regresiones de los riesgos del premortem
- "¿la pantalla abre?" → `test_smoke_pantallas.py` (`AppTest`, base sintética, red cortada)
- una función anidada que lee algo que todavía no existe → `test_closures_definidos.py`
- migraciones que re-corren al reiniciar → `test_db_reparaciones_unicas.py` · el mapa leyendo carpetas ignoradas → `test_indexar.py` · importes ilegibles y el CLI del ingest → `test_importes_ilegibles.py`
- login, contraseñas, rate-limit, alta de cuentas → `test_auth.py`
- los scripts de backup (estructura: token, `< NUL`, aviso en el Escritorio) → `test_scripts_backup.py`
- cobertura: `.venv\Scripts\python.exe -m pytest --cov=core --cov=places` (`coverage` instalado en el venv el 22/9/2026, fuera del lock; 78% total)

## Trampas

- Correr con el **Python 3.11 del `.venv`** (misma versión que el Dockerfile); con 3.14 la suite ni colecta.
- `_oraculos.py` lee los CSV de la raíz: no los muevas sin tocar los env vars.
- En CI los 3 tests-oráculo salen `skipped`; **en la máquina de Franco tiene que dar 0 skipped** antes de un deploy. Si el número de skipped cambia, miralo aunque todo esté verde.
- ⚠️ **Un test que escanea código tiene que exigir encontrar algo** (trampa 41). `test_db_concurrencia` miraba solo `view.py` después del split y pasaba siempre sin revisar nada.
- **Simulá una fuente caída con la excepción real** (`OSError`, `urllib.error.HTTPError`), no con `RuntimeError`: los módulos ya no tragan cualquier excepción.
- `AppTest` corre en este mismo proceso: el `st.cache_data` se comparte entre tests (limpiarlo en el fixture) y los `_fetch_http` se cortan con `monkeypatch` para que no haya red.

## Estado

- **Funciona:** 909 passed, 0 skipped en local (27/9/2026); en CI, 906 + 3 skipped (los oráculos).

## Proximo paso

—
