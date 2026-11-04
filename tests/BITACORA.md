# tests/

<!-- huella: 567cd7e34adc -->

Resumen: La suite completa (862 tests al 20/10/2026, Fase D completa en código) en carpeta plana: unidad + regresión + oráculos contra los CSV de Franco. Es el gate del repo: nada se cierra sin verde.

## Buscar acá si

- tests que escanean el código fuente: `test_nombres_definidos.py` (AST de names), `test_transacciones_formulario.py` (ramas del form), `test_env_example_sin_secretos.py`
- los CSV oráculo de Finanzas → `_oraculos.py` (`DIARIO_CSV`/`MENSUAL_CSV`)
- convención de nombres: `test_backup_*`/`test_db_*`/`test_workspaces_*` → core · el resto → Finanzas
- agenda en el Inicio (Fase C) → `test_inicio_agenda.py` (semana por día, tareas, y AppTest con cliente falso: completar bien, rechazo de Google, agenda caída, sin configurar)
- Inicio y marca (Fase C) → `test_inicio.py` (variación contra el mismo período, KPIs = `resumen`, AppTest del Inicio y de la app entera, "Radar Financiero" fuera de la interfaz)
- agenda por WhatsApp (Fase B) → `test_agenda_whatsapp.py` (intérprete, comandos con cliente falso, y el cliente real contra un **Apps Script de mentira** que redirige con 302 como Google)
- briefings de Gemini y cola de salida (Fase B) → `test_api_briefing.py` (servidor real; ventana abierta/cerrada/vencida, entrega al escribir, dedupe por id, Meta que rechaza, auth)
- varios gastos en un mensaje, lotes y bruto (Fase D, paso 2) → `test_lotes_whatsapp.py` (propuesta, correcciones, todo o nada, un backup por lote, deshacer del lote y su orden contra un gasto suelto, filas editadas desde la app) + `test_varios_gastos_ok_y_deshacer_de_punta_a_punta` en `test_api_whatsapp.py` (por el servidor real)
- el extracto de Galicia (Fase D, paso 4) → `test_extracto_galicia.py` (`armar_extracto` arma un Excel sintético como el del banco; lo reusan otros tests) y `test_conciliacion.py` (punto de partida, lo que falta, emparejar, empates, regla del corte, devoluciones contra el bruto, sobrantes, deshacer, y `test_cada_gasto_una_sola_vez`). Los tests contra el archivo real de Franco miran solo cantidades
- fotos con Gemini (Fase D, paso 6) → `test_fotos.py` (un `LectorFalso` en lugar de Gemini para la propuesta; el cliente real contra un Gemini de mentira local)
- resúmenes de tarjeta (Fase D, paso 5) → `test_resumen_tarjeta.py` (el lector sobre **palabras armadas a mano**, con la clase `Hoja`; contra los 9 PDF reales: que cierren y los tres ejemplos del diseño), `test_tarjetas.py` (el desarmado; reemplaza el lector por un `Resumen` armado a mano) y `test_cotizaciones.py` (un ArgentinaDatos de mentira)
- saldos y ajuste, y el "¿es el mismo?" (Fase D, paso 4b) → `test_saldos.py`, `test_ya_vino_del_banco.py` (reusan el fixture `db` de `test_conciliacion.py`)
- archivos por WhatsApp (Fase D, paso 3) → `test_archivos_whatsapp.py` (webhook, tipo por contenido, la descarga en dos pasos contra un **Meta de mentira** local, topes de tamaño) + los tests de archivos al final de `test_api_whatsapp.py` (servidor real, `descargar` falso por `entorno["estado"]`; verifica que no quede nada en disco)
- balances de la semana (ADR-0011, paso 2) → `test_balances_fuentes.py` (un Nasdaq y una Wikipedia de mentira locales) y `test_balances.py` (`FuentesFalsas`: la lista, el S&P una vez por mes, la respuesta, la convivencia con un lote, y `POST /api/balances` contra el servidor real)
- el test de costo cero (que no aparezca la palabra de las plantillas) recorre **todo** `core/api/` y `places/finanzas/core/` desde el 19/10/2026: un módulo nuevo del canal queda vigilado solo
- WhatsApp (Fase A): `test_comandos_whatsapp.py` (parser y comandos, base sintética) · `test_api_whatsapp.py` (canal de Meta + **servidor HTTP real** en un puerto libre, webhooks firmados, envío falso) · `test_deploy_api.py` (nginx/Dockerfile/entrypoint como texto: no hay Docker local)
- los premortem-tests (`test_premortem3/5.py`): regresiones de los riesgos del premortem
- "cambié la clasificación de un motivo y el Dashboard y el Diario no coinciden" o "un KPI tarda" → `test_consultas_rapidas.py` (21/10/2026): `grupos_efectivos` igual a `efective_grupo` fila por fila (regla dual de Inversiones incluida), plan de M25 y el Diario con ventana vacía
- "un gasto del bot no aparece en la app hasta recargar" o "la app muestra un número viejo" → `test_cache_versionada.py` (21/10/2026): otro proceso escribe y el Inicio, el Dashboard y el Diario lo muestran en el click siguiente; el vigía no frena los checkpoints
- "la API o el Inicio volvieron a arrancar lentos" → `test_arranque_liviano.py` (21/10/2026): en un **proceso nuevo**, la API arranca sin pandas ni openpyxl y Finanzas no importa sus vistas hasta abrir la pestaña
- "¿la pantalla abre?" → `test_smoke_pantallas.py` (`AppTest`, base sintética). Desde el 21/10/2026 abre cada pestaña de Finanzas por separado (corre solo la abierta), toca los controles de los dos fragmentos del Dashboard y verifica que el Excel diferido exporte el workspace activo desde otro hilo
- una función anidada que lee algo que todavía no existe → `test_closures_definidos.py`
- migraciones que re-corren al reiniciar → `test_db_reparaciones_unicas.py` · el mapa leyendo carpetas ignoradas → `test_indexar.py` · importes ilegibles y el CLI del ingest → `test_importes_ilegibles.py`
- login, contraseñas, rate-limit, alta de cuentas → `test_auth.py`
- los scripts de backup (estructura: token, `< NUL`, aviso en el Escritorio) → `test_scripts_backup.py`
- cobertura: `.venv\Scripts\python.exe -m pytest --cov=core --cov=places` (`coverage` instalado en el venv el 22/9/2026, fuera del lock; 78% total)

## Trampas

- **Un smoke test no puede depender del día del mes** (3/11/2026): el fixture de `test_smoke_pantallas.py` cargaba los gastos 10 días antes de hoy, y del 1 al 10 de cada mes el Dashboard (que abre en "Este mes") no dibujaba la dona: `KeyError: 'donut_agrupar_por'`. Ahora caen dentro del mes en curso.
- Correr con el **Python 3.11 del `.venv`** (misma versión que el Dockerfile); con 3.14 la suite ni colecta.
- `_oraculos.py` lee los CSV de la raíz: no los muevas sin tocar los env vars.
- En CI los 3 tests-oráculo salen `skipped`; **en la máquina de Franco tiene que dar 0 skipped** antes de un deploy. Si el número de skipped cambia, miralo aunque todo esté verde.
- ⚠️ **Un test que escanea código tiene que exigir encontrar algo** (trampa 41). `test_db_concurrencia` miraba solo `view.py` después del split y pasaba siempre sin revisar nada; desde el 14/10/2026 revisa todo `places/`.
- **Simulá una fuente caída con la excepción real** (`OSError`, `urllib.error.HTTPError`), no con `RuntimeError`: los módulos ya no tragan cualquier excepción.
- En Windows, un servidor que responde **sin leer el cuerpo** del POST hace que el cliente reciba `ConnectionResetError` en vez del código (pasó con el 503 de la API, 15/10/2026): el servidor lee el cuerpo antes de cualquier rechazo.
- `AppTest.from_function` corre la función como un **script aparte**: no ve variables del test. Pasar datos por `session_state`.
- `AppTest` corre en este mismo proceso: el `st.cache_data` se comparte entre tests (limpiarlo en el fixture).

## Estado

- **3/11/2026 (más tarde):** 1018 passed, 0 fallas. Nuevo `test_categorias_edicion.py` (el editor de categorías, de 35% a 100%), arreglado el smoke del dashboard, y `test_un_flyctl_roto_no_se_le_echa_al_token`.
- **3/11/2026:** 1000 passed, 1 falla ajena (`test_smoke_pantallas::test_los_controles_de_cada_grafico_del_dashboard_andan`, `KeyError: 'donut_agrupar_por'`, ya fallaba antes). Nuevos en `test_conciliacion.py`: la respuesta como lista numerada (`1. Compras` / `2. Ok`, un renglón por número).
- **21/10/2026 (más tarde a la noche):** 978 passed, 0 skipped (balances: "ya las tenías" desde el Calendar).
- **21/10/2026 (noche):** 974 passed, 0 skipped (balances, paso 4: el resumen del día y el diagnóstico desde Fly).
- **21/10/2026 (más tarde):** 952 passed, 0 skipped (balances, paso 3: agendado en Google y `deshacer`).
- **21/10/2026:** 935 passed, 0 skipped (balances de la semana, paso 2: la lista y la respuesta).
- **20/10/2026 (noche):** 862 passed, 0 skipped (Fase D, paso 6, con las guardas del ensayo del desarmado).
- **20/10/2026 (más tarde):** 837 passed, 0 skipped (Fase D, paso 5).
- **20/10/2026:** 794 passed, 0 skipped (Fase D, paso 4b).
- **19/10/2026 (noche):** 781 passed, 0 skipped (Fase D, paso 4a: lector del extracto y conciliación, con las mejoras del ensayo con datos reales).
- **19/10/2026 (más tarde):** 711 passed, 0 skipped (Fase D, paso 3: recibir archivos).
- **19/10/2026:** 677 passed, 0 skipped (Fase D, paso 2: lotes y bruto; el test de costo cero ahora recorre las carpetas enteras).
- **18/10/2026:** 618 passed, 0 skipped (Fase C: saldo de la cuenta en el Inicio y `test_el_icono_de_la_pestana_es_el_mono`).
- **17/10/2026:** 615 passed, 0 skipped (Fase C, pasos 1–5). Antes, 601 (pasos 1–2). Antes en el día, 568 (agenda por WhatsApp).
- **16/10/2026:** 515 passed, 0 skipped (con las cuentas en el monto); antes, 493 (Fase B, pasos 1–2: cola de salida y `/api/briefing`).
- **15/10/2026:** 468 passed, 0 skipped (Fase A: +109 tests de WhatsApp, API y contenedor).
- **Antes:** 359 passed, 0 skipped en local (14/10/2026, tras retirar Inversiones — se fueron ~550 tests de cartera y market_data); en CI salen skipped los oráculos de los CSV.

## Proximo paso

—
