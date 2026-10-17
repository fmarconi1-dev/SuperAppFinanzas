# tests/

<!-- huella: dd4f4e0604b6 -->

Resumen: La suite completa (601 tests al 17/10/2026, con la Fase C en curso) en carpeta plana: unidad + regresión + oráculos contra los CSV de Franco. Es el gate del repo: nada se cierra sin verde.

## Buscar acá si

- tests que escanean el código fuente: `test_nombres_definidos.py` (AST de names), `test_transacciones_formulario.py` (ramas del form), `test_env_example_sin_secretos.py`
- los CSV oráculo de Finanzas → `_oraculos.py` (`DIARIO_CSV`/`MENSUAL_CSV`)
- convención de nombres: `test_backup_*`/`test_db_*`/`test_workspaces_*` → core · el resto → Finanzas
- Inicio y marca (Fase C) → `test_inicio.py` (variación contra el mismo período, KPIs = `resumen`, AppTest del Inicio y de la app entera, "Radar Financiero" fuera de la interfaz)
- agenda por WhatsApp (Fase B) → `test_agenda_whatsapp.py` (intérprete, comandos con cliente falso, y el cliente real contra un **Apps Script de mentira** que redirige con 302 como Google)
- briefings de Gemini y cola de salida (Fase B) → `test_api_briefing.py` (servidor real; ventana abierta/cerrada/vencida, entrega al escribir, dedupe por id, Meta que rechaza, auth)
- WhatsApp (Fase A): `test_comandos_whatsapp.py` (parser y comandos, base sintética) · `test_api_whatsapp.py` (canal de Meta + **servidor HTTP real** en un puerto libre, webhooks firmados, envío falso) · `test_deploy_api.py` (nginx/Dockerfile/entrypoint como texto: no hay Docker local)
- los premortem-tests (`test_premortem3/5.py`): regresiones de los riesgos del premortem
- "¿la pantalla abre?" → `test_smoke_pantallas.py` (`AppTest`, base sintética)
- una función anidada que lee algo que todavía no existe → `test_closures_definidos.py`
- migraciones que re-corren al reiniciar → `test_db_reparaciones_unicas.py` · el mapa leyendo carpetas ignoradas → `test_indexar.py` · importes ilegibles y el CLI del ingest → `test_importes_ilegibles.py`
- login, contraseñas, rate-limit, alta de cuentas → `test_auth.py`
- los scripts de backup (estructura: token, `< NUL`, aviso en el Escritorio) → `test_scripts_backup.py`
- cobertura: `.venv\Scripts\python.exe -m pytest --cov=core --cov=places` (`coverage` instalado en el venv el 22/9/2026, fuera del lock; 78% total)

## Trampas

- Correr con el **Python 3.11 del `.venv`** (misma versión que el Dockerfile); con 3.14 la suite ni colecta.
- `_oraculos.py` lee los CSV de la raíz: no los muevas sin tocar los env vars.
- En CI los 3 tests-oráculo salen `skipped`; **en la máquina de Franco tiene que dar 0 skipped** antes de un deploy. Si el número de skipped cambia, miralo aunque todo esté verde.
- ⚠️ **Un test que escanea código tiene que exigir encontrar algo** (trampa 41). `test_db_concurrencia` miraba solo `view.py` después del split y pasaba siempre sin revisar nada; desde el 14/10/2026 revisa todo `places/`.
- **Simulá una fuente caída con la excepción real** (`OSError`, `urllib.error.HTTPError`), no con `RuntimeError`: los módulos ya no tragan cualquier excepción.
- En Windows, un servidor que responde **sin leer el cuerpo** del POST hace que el cliente reciba `ConnectionResetError` en vez del código (pasó con el 503 de la API, 15/10/2026): el servidor lee el cuerpo antes de cualquier rechazo.
- `AppTest.from_function` corre la función como un **script aparte**: no ve variables del test. Pasar datos por `session_state`.
- `AppTest` corre en este mismo proceso: el `st.cache_data` se comparte entre tests (limpiarlo en el fixture).

## Estado

- **17/10/2026:** 601 passed, 0 skipped (Fase C, pasos 1–2). Antes en el día, 568 (agenda por WhatsApp).
- **16/10/2026:** 515 passed, 0 skipped (con las cuentas en el monto); antes, 493 (Fase B, pasos 1–2: cola de salida y `/api/briefing`).
- **15/10/2026:** 468 passed, 0 skipped (Fase A: +109 tests de WhatsApp, API y contenedor).
- **Antes:** 359 passed, 0 skipped en local (14/10/2026, tras retirar Inversiones — se fueron ~550 tests de cartera y market_data); en CI salen skipped los oráculos de los CSV.

## Proximo paso

—
