# MAPA — SuperAppFinanzas

<!-- GENERADO por indexar.py. No editar: los cambios se pierden. -->
<!-- La prosa vive en las BITACORA.md de cada carpeta. -->
<!-- 2026-10-19 17:28 UTC · 96 archivos · 18,062 LOC -->

## Como usar este archivo

Es el unico archivo del proyecto que hace falta leer para empezar. Para ubicar algo concreto: `python3 .mapa/buscar.py "<termino>"` devuelve archivo y linea sin abrir nada. Recien despues abrir los archivos que salgan, y solo esos.

Rama `main` — ultimo commit: 2026-10-19 4c45601 feat: recibir documentos y fotos por WhatsApp · **hay cambios sin commitear**

## Donde buscar que

| Si la consulta es sobre... | Ir a |
|---|---|
| el arranque de la app, la navegación entre lugares o la restauración de sesión → `app.py` | `./` |
| deploy, Docker, Fly.io → `Dockerfile`, `fly.toml`, `docker-entrypoint.sh`, `docs/DEPLOY.md` y `docs/RUNBOOK.md` | `./` |
| el arranque de la API de WhatsApp o nginx en el contenedor → `api.py`, `deploy/nginx.conf`, `docker-entrypoint.sh` (código en `core/api/`) | `./` |
| cómo se trabaja en este repo → `GUIA-DE-TRABAJO.md`, `claude.md`, `/MAPA.md` | `./` |
| qué se hizo y qué sigue → `ESTADO.md` (foto), este archivo (crónica), `EN-HUMANO.md` (en llano) | `./` |
| un aviso de Streamlit en `fly logs` que parece error, o la config del servidor → `.streamlit/config.toml` | `./` |
| CI rojo en GitHub → `tests.yml` | `.github\workflows/` |
| por qué el batch del scoring ya no está acá → scoring retirado (5/8/2026) | `.github\workflows/` |
| la base de datos: schema, una migración nueva (SIEMPRE aditiva), "database is locked", backups y retención (`BACKUP_RETENTION`, `DB_PATH`) | `core/` |
| el webhook de WhatsApp, la API HTTP o nginx → **`core/api/`** (y `api.py`, `deploy/nginx.conf` en la raíz) | `core/` |
| grupo familiar / espacios compartidos: crear, unirse, código de invitación, resolver el workspace activo | `core/` |
| el badge Personal/Familiar o el switcher del sidebar se comportan raro | `core/` |
| un import circular entre core y core/auth → **cortado** el 27/8/2026 con `context.py` | `core/` |
| quién es el usuario o el workspace activo, desde lógica sin Streamlit → `context.py` | `core/` |
| "reinicié la app y se deshizo lo que cambié" (una categoría reclasificada, una subcategoría vaciada) → reparaciones únicas de `db.py` (`_NIVEL_REPARACIONES`, `PRAGMA user_version`) | `core/` |
| tolerar una base sin cierta migración → `es_tabla_faltante()` en `db.py` (y nada más ancho) | `core/` |
| el bot no contesta, contesta dos veces o un mensaje "se perdió" → `servidor.py` (firma, remitente, dedupe por wamid, cola, `resultado` en `whatsapp_mensajes`) | `core\api/` |
| Meta rechaza un envío o aparece un código 131xxx en `fly logs` → `whatsapp_meta.py` (`CanalNoDisponible` con el código; ante un 131030 prueba sin el 9 y con el 9, y si ninguno sirve dice que el número del panel va con el 9) | `core\api/` |
| un briefing de Gemini que no llegó, llegó dos veces o llegó tarde → `servidor.py` (`_post_briefing`, `encolar_saliente`, `entregar_pendientes`; la tabla `whatsapp_salientes`) | `core\api/` |
| `evento:` / `tarea:` / `agenda` no llegan a Google, o Google contesta raro → `google.py` (`ClienteAgenda`: el 302 de Apps Script, `ok: false` → `AgendaRechazo`, página de login → `AgendaNoDisponible`) | `core\api/` |
| configurar el webhook en el panel de Meta (verify token, `hub.challenge`) → `servidor.py` + `docs/WHATSAPP-CANAL.md` | `core\api/` |
| un archivo (extracto, resumen, foto) que no llegó, no se bajó o se contestó "no sé leer ese archivo" → `whatsapp_meta.descargar_archivo` (dos pasos: id → URL → contenido; `ArchivoNoDisponible`), `archivos.tipo_de_contenido` (por los primeros bytes) y `servidor._bajar` | `core\api/` |
| qué variables de entorno hacen falta → `ConfigWhatsApp.desde_entorno` (y `.env.example`) | `core\api/` |
| la interpretación del texto (montos, categorías, `resumen`, `deshacer`) → **no es acá**: `places/finanzas/core/comandos.py` | `core\api/` |
| login, signup, contraseñas, código de registro (`SIGNUP_CODE`) | `core\auth/` |
| "me pide loguearme en cada refresh" → tokens firmados en la URL (`session_tokens.py`, `SESSION_SECRET`) | `core\auth/` |
| necesitás saber quién es el usuario o workspace actual desde lógica sin Streamlit → **no es acá**: `core/context.py` (las fachadas `current_user.py`/`current_workspace.py` se borraron el 22/9/2026) | `core\auth/` |
| el botón de logout | `core\auth/` |
| estética, colores, tipografía, dark mode, "se ve poco profesional" | `core\theme/` |
| "se ve mal en el celular" → `_responsive.py` | `core\theme/` |
| un gráfico Plotly con colores fuera de paleta → `_theme.py` | `core\theme/` |
| KPI cards, tokens de diseño, flash sin estilos (FOUC) | `core\theme/` |
| el logo → `_logo.py` | `core\theme/` |
| el briefing matutino no llegó o llegó dos veces → `reenviarBriefingAWhatsApp` (etiqueta `WA-Enviado`, solo si la API devolvió `ok: true`) | `integraciones\google-apps-script/` |
| links del briefing sin acortar → `acortarUrls` (TinyURL vía `fetchAll`; si falla, deja el original) | `integraciones\google-apps-script/` |
| el contrato SuperApp → Google (acciones, campos, errores) → `README.md` de esta carpeta | `integraciones\google-apps-script/` |
| eventos con la hora corrida → zona horaria en `appsscript.json` | `integraciones\google-apps-script/` |
| un evento o tarea duplicado por reintento → `id_solicitud` + `CacheService` (6 h) | `integraciones\google-apps-script/` |
| el onboarding aparece cuando no debería (se evalúa SIEMPRE contra el espacio personal) | `places\finanzas/` |
| el orden de las pestañas o una pestaña entera caída → `home.py` | `places\finanzas/` |
| el badge grande del modo familiar | `places\finanzas/` |
| números del dashboard que no cierran → `metrics.py` | `places\finanzas\core/` |
| un briefing de Gemini que llega distinto de como lo mandó Gemini → `briefing.py` (no le suma nada: los dos tipos salen tal cual) | `places\finanzas\core/` |
| `evento:` / `tarea:` / `agenda`: fechas y horas de agenda, formato de la semana → `agenda.py` (puro). Cómo se rutean y qué se contesta si Google falla → `comandos._comando_agenda` | `places\finanzas\core/` |
| un mensaje de WhatsApp que no se cargó, se cargó mal o pidió confirmación → `comandos.py` (parser de montos y fechas, "¿quisiste decir?", `resumen`, `deshacer`) | `places\finanzas\core/` |
| Previsión vs Realidad por mes → `budget.py` | `places\finanzas\core/` |
| categorías, "sin categorizar", mapping Motivo → Grupo/Subcategoría → `categorizer.py`, `categorias.py` | `places\finanzas\core/` |
| importar `Diario.csv` / `Mensual.csv` (`ingest.py`, `parsers.py`; env `DIARIO_CSV`/`MENSUAL_CSV`) — por consola: `.venv\Scripts\python.exe -m places.finanzas.core.ingest --force` | `places\finanzas\core/` |
| un gasto que entró como $0, o una advertencia de "importe ilegible" al importar → `parsers.parse_currency_estricto` + `ingest._importe` | `places\finanzas\core/` |
| alta/edición/borrado de gastos y el backup automático que disparan → `transactions.py` (`insertar_sin_backup` para escribir dentro de una transacción) | `places\finanzas\core/` |
| varios gastos en un mensaje, la propuesta numerada, `ok`/correcciones, o un `deshacer` que borra varios juntos → `comandos.py` (`_proponer_varios`, `_leer_respuesta_lote`, `_responder_lote`) + `lotes.py` (aplicar todo o nada y deshacer) | `places\finanzas\core/` |
| el bruto de un gasto con cuenta (`150000-25000*5` → $150.000) → `comandos.bruto_de_cuenta` y la tabla `gasto_cuentas` | `places\finanzas\core/` |
| exportar todo a Excel → `export.py` | `places\finanzas\core/` |
| "$ mal formateado", separador de miles, un NaN visible en pantalla → `_format.py` | `places\finanzas\helpers/` |
| HTML que se muestra como texto crudo → `_html.render_html` | `places\finanzas\helpers/` |
| el tour guiado para usuarios nuevos → `_tour.py` | `places\finanzas\helpers/` |
| Dashboard, gráficos, editor de Fondo USD → `dashboard.py` | `places\finanzas\views/` |
| alta rápida vs. detallada de gastos, "Firmar como" → `transacciones.py` | `places\finanzas\views/` |
| Libro Diario → `diario.py` · Previsión vs Realidad → `mensual.py` | `places\finanzas\views/` |
| editor de categorías y sección "Espacio compartido" → `configuracion.py` | `places\finanzas\views/` |
| pantalla de bienvenida → `onboarding.py` | `places\finanzas\views/` |
| la pantalla de Inicio no abre, se ve mal o muestra un número raro → `home.py` | `places\inicio/` |
| un KPI del Inicio no coincide con `resumen` por WhatsApp → **no debería poder**: los dos usan `comandos.totales_mes`; ver `core/resumen.py` y el test `test_los_kpis_del_inicio_son_los_de_resumen` | `places\inicio/` |
| la semana o las tareas no aparecen, aparecen viejas o un tilde no completa → `home.py` (`_render_agenda`, caché `_semana` de 5 min, callback `_completar`) y `core/semana.py` (agrupar por día, ordenar tareas) | `places\inicio/` |
| la variación contra el mes anterior parece mal → `core/resumen.py` (`resumen_del_mes`: compara contra el **mismo período**, del 1 al día de hoy) | `places\inicio/` |
| el saldo grande del Inicio no coincide con el del Dashboard → `resumen.py` (`saldo_cuenta`, que es `metrics.saldo_cuenta_corriente`) | `places\inicio\core/` |
| gastos, ingresos o movimientos del mes no coinciden con `resumen` por WhatsApp → `resumen.py` (`resumen_del_mes` usa `comandos.totales_mes`, la misma función del bot) | `places\inicio\core/` |
| la variación contra el mes anterior da rara, o la flecha apunta al revés → `resumen.py` (`variacion`, `formatear_variacion`, `mes_anterior`) | `places\inicio\core/` |
| "Buen día / Buenas tardes" o la fecha larga en castellano → `resumen.py` (`saludo`, `fecha_larga`) | `places\inicio\core/` |
| el renglón "mensajes en cola" del estado del Secretario → `resumen.py` (`mensajes_en_cola`, tabla `whatsapp_salientes`) | `places\inicio\core/` |
| un evento aparece en el día equivocado, o falta uno que sigue en curso → `semana.py` (`dias_de_la_semana`) | `places\inicio\core/` |
| el orden de las tareas (vencidas, con fecha, sin fecha) → `semana.py` (`tareas_ordenadas`) | `places\inicio\core/` |
| backup remoto diario, restaurar, "¿este backup sirve de verdad?" → `backup_remoto.ps1`, `restaurar_backup.ps1`, `verificar_backup.py`, `estado_backup.ps1`, `programar_backup.ps1` | `scripts/` |
| resetear la contraseña de un usuario → `setup_password.py` | `scripts/` |
| reindexar el mapa del repo → `indexar.py` (ver `/MAPA.md`) | `scripts/` |
| el ícono de la pestaña del navegador (el moño) → `generar_favicon.py` (dibuja `assets/favicon.png` con Pillow; correr si cambia `assets/logo.svg`) | `scripts/` |
| "¿Meta deja mandar texto sin tarjeta?" → `probar_whatsapp_texto.py` (prueba única de costo cero, ADR-0008; manda un texto libre y traduce el código de error de Meta) | `scripts/` |
| "el backup no corre solo", "la sesión de fly venció", token de Fly → `guardar_token_fly.ps1`, `_fly_comun.ps1` (`Use-TokenFly`) | `scripts/` |
| un archivo "BACKUP SUPERAPP - FALLO.txt" apareció en el Escritorio → lo deja `backup_remoto.ps1` al fallar; `estado_backup.ps1` dice por qué | `scripts/` |
| tests que escanean el código fuente: `test_nombres_definidos.py` (AST de names), `test_transacciones_formulario.py` (ramas del form), `test_env_example_sin_secretos.py` | `tests/` |
| los CSV oráculo de Finanzas → `_oraculos.py` (`DIARIO_CSV`/`MENSUAL_CSV`) | `tests/` |
| convención de nombres: `test_backup_*`/`test_db_*`/`test_workspaces_*` → core · el resto → Finanzas | `tests/` |
| agenda en el Inicio (Fase C) → `test_inicio_agenda.py` (semana por día, tareas, y AppTest con cliente falso: completar bien, rechazo de Google, agenda caída, sin configurar) | `tests/` |
| Inicio y marca (Fase C) → `test_inicio.py` (variación contra el mismo período, KPIs = `resumen`, AppTest del Inicio y de la app entera, "Radar Financiero" fuera de la interfaz) | `tests/` |
| agenda por WhatsApp (Fase B) → `test_agenda_whatsapp.py` (intérprete, comandos con cliente falso, y el cliente real contra un **Apps Script de mentira** que redirige con 302 como Google) | `tests/` |
| briefings de Gemini y cola de salida (Fase B) → `test_api_briefing.py` (servidor real; ventana abierta/cerrada/vencida, entrega al escribir, dedupe por id, Meta que rechaza, auth) | `tests/` |
| varios gastos en un mensaje, lotes y bruto (Fase D, paso 2) → `test_lotes_whatsapp.py` (propuesta, correcciones, todo o nada, un backup por lote, deshacer del lote y su orden contra un gasto suelto, filas editadas desde la app) + `test_varios_gastos_ok_y_deshacer_de_punta_a_punta` en `test_api_whatsapp.py` (por el servidor real) | `tests/` |
| archivos por WhatsApp (Fase D, paso 3) → `test_archivos_whatsapp.py` (webhook, tipo por contenido, la descarga en dos pasos contra un **Meta de mentira** local, topes de tamaño) + los tests de archivos al final de `test_api_whatsapp.py` (servidor real, `descargar` falso por `entorno["estado"]`; verifica que no quede nada en disco) | `tests/` |
| el test de costo cero (que no aparezca la palabra de las plantillas) recorre **todo** `core/api/` y `places/finanzas/core/` desde el 19/10/2026: un módulo nuevo del canal queda vigilado solo | `tests/` |
| WhatsApp (Fase A): `test_comandos_whatsapp.py` (parser y comandos, base sintética) · `test_api_whatsapp.py` (canal de Meta + **servidor HTTP real** en un puerto libre, webhooks firmados, envío falso) · `test_deploy_api.py` (nginx/Dockerfile/entrypoint como texto: no hay Docker local) | `tests/` |
| los premortem-tests (`test_premortem3/5.py`): regresiones de los riesgos del premortem | `tests/` |
| "¿la pantalla abre?" → `test_smoke_pantallas.py` (`AppTest`, base sintética) | `tests/` |
| una función anidada que lee algo que todavía no existe → `test_closures_definidos.py` | `tests/` |
| migraciones que re-corren al reiniciar → `test_db_reparaciones_unicas.py` · el mapa leyendo carpetas ignoradas → `test_indexar.py` · importes ilegibles y el CLI del ingest → `test_importes_ilegibles.py` | `tests/` |
| login, contraseñas, rate-limit, alta de cuentas → `test_auth.py` | `tests/` |
| los scripts de backup (estructura: token, `< NUL`, aviso en el Escritorio) → `test_scripts_backup.py` | `tests/` |
| cobertura: `.venv\Scripts\python.exe -m pytest --cov=core --cov=places` (`coverage` instalado en el venv el 22/9/2026, fuera del lock; 78% total) | `tests/` |

## Carpetas

| Carpeta | Que es | Arch. | LOC | Bitacora |
|---|---|---:|---:|---|
| `tests/` | La suite completa (711 tests al 19/10/2026, Fase D en curso) en carpeta plana: unidad + regresión + oráculos contra los CSV de Franco. Es el gate del repo: nada se cierra sin verde. | 31 | 6,239 | ok |
| `places\finanzas\core/` | Lógica de negocio de Finanzas, pura y sin Streamlit: transacciones, categorización, KPIs, presupuesto, libro diario, import de CSV y export a Excel. | 14 | 3,408 | ok |
| `places\finanzas\views/` | Las 5 pestañas de Finanzas + onboarding, en Streamlit puro; la lógica de negocio vive en `../core/`. | 7 | 1,860 | ok |
| `core/` | Núcleo compartido: SQLite (schema + migraciones M1–M20 + reparaciones únicas + backups), workspaces del grupo familiar (D2) y su UI. Auth, theme y la API HTTP (`api/`, Fase A) viven en subcarpetas propias. | 5 | 1,734 | ok |
| `scripts/` | Operación y mantenimiento: backups remotos (PowerShell + verificación), reset de contraseñas y el indexador del mapa. | 7 | 1,357 | ok |
| `core\api/` | API HTTP stdlib de la SuperApp (Fase A, ADR-0008): servidor con el webhook de WhatsApp firmado por Meta, dedupe y cola de trabajo, más el canal de Meta (único módulo que le habla). | 5 | 1,100 | ok |
| `core\theme/` | Design system "Cosmic Slate": CSS inyectado en Streamlit, paleta semántica + template Plotly unificado, ajustes responsive y logo. | 5 | 710 | ok |
| `core\auth/` | Autenticación compartida: usuarios con bcrypt, pantalla de login/signup y tokens de sesión firmados. (Los contextvars de usuario/workspace viven en `core/context.py`.) | 4 | 422 | ok |
| `./` | Raíz del monorepo: entry point (`app.py`: login único + navegación entre lugares), deploy (Dockerfile/fly.toml) y toda la gobernanza (ESTADO, ROADMAP, MEJORAS, guías). | 5 | 311 | ok |
| `places\finanzas\helpers/` | Utilidades de las vistas: formateo es-AR de montos, inyección de HTML y el tour guiado de bienvenida. | 4 | 278 | ok |
| `places\inicio/` | Lugar Inicio — la pantalla principal de Secretario (Fase C, ADR-0008): saludo, **saldo de la cuenta** en grande, gastos/ingresos/movimientos del mes contra el mismo período del anterior, la semana y las tareas de Google (con tilde para completarlas), últimos movimientos y estado del Secretario. | 2 | 255 | ok |
| `places\inicio\core/` | La lógica del Inicio, **pura y sin Streamlit**: los números del mes y el saldo (`resumen.py`) y la semana y las tareas de Google, listas para mostrar (`semana.py`). La pantalla está en `../home.py`. | 3 | 231 | ok |
| `.github\workflows/` | CI: `tests.yml` corre la suite pytest en cada push (el gate de recon se saltea sin el Excel, así CI no depende de datos personales). | 1 | 82 | ok |
| `places\finanzas/` | Lugar A — Finanzas Personales (ex Mis-Finanzas-App / Radar Financiero): home con onboarding y las 5 pestañas. La lógica vive en `core/` local, las pantallas en `views/`. | 2 | 73 | **vencida** |
| `places/` | _sin describir_ | 1 | 2 | — |
| `integraciones\google-apps-script/` | Puente Google ↔ SuperApp en Apps Script: reenvía el briefing de Gmail a la API (con links acortados) y atiende el webhook que crea/lista eventos de Calendar y tareas de Tasks. | 0 | 0 | **vencida** |

## Puntos de entrada

- `api.py`
- `app.py`
- `places\finanzas\core\ingest.py`
- `scripts\buscar.py`
- `scripts\generar_favicon.py`
- `scripts\indexar.py`
- `scripts\probar_whatsapp_texto.py`
- `scripts\setup_password.py`
- `scripts\verificar_backup.py`

## Archivos centrales

Ordenados por cuantos otros archivos dependen de ellos. Tocar uno de arriba tiene mas radio de impacto.

| Archivo | LOC | Lo usan | Simbolos |
|---|---:|---:|---|
| `core\db.py` | 1262 | 39 | `_migrate`, `es_tabla_faltante`, `get_db_path`, `connect` |
| `core\context.py` | 105 | 20 | `set_current_user_id`, `get_current_user_id`, `require_current_user_id`, `set_current_workspace_id` |
| `core\workspaces.py` | 261 | 15 | `_hash_code`, `_uid`, `get_personal_workspace_id`, `ensure_personal_workspace` |
| `places\finanzas\core\metrics.py` | 359 | 14 | `_uid`, `anios_con_datos`, `filtrar_anio`, `load_transactions` |
| `core\__init__.py` | 5 | 13 | — |
| `places\finanzas\core\transactions.py` | 265 | 12 | `_uid`, `_es_familiar`, `_asegurar_motivo`, `insert_transaction` |
| `places\finanzas\helpers\_html.py` | 22 | 7 | `render_html` |
| `places\finanzas\core\__init__.py` | 5 | 7 | — |
| `places\finanzas\core\comandos.py` | 927 | 6 | `Respuesta`, `Gasto`, `EntradaInvalida`, `ahora_ar` |
| `places\finanzas\core\ingest.py` | 381 | 6 | `ImportResult`, `_importe`, `_read_csv_rows`, `import_diario` |
| `places\finanzas\helpers\_tour.py` | 198 | 6 | `_user_id`, `is_tour_active`, `start_tour`, `finish_tour` |
| `places\finanzas\core\parsers.py` | 247 | 5 | `parse_currency`, `parse_currency_estricto`, `parse_date`, `normalize_motivo` |

## Flujo interno

- `tests/` → `core/` (41)
- `tests/` → `places\finanzas\core/` (30)
- `places\finanzas\core/` → `core/` (20)
- `places\finanzas\views/` → `places\finanzas\helpers/` (13)
- `places\finanzas\views/` → `places\finanzas\core/` (12)
- `places\finanzas\views/` → `core/` (8)
- `tests/` → `core\api/` (8)
- `./` → `core/` (4)
- `places\inicio\core/` → `places\finanzas\core/` (4)
- `core\theme/` → `places\finanzas\helpers/` (3)
- `places\finanzas/` → `core/` (3)
- `places\finanzas\views/` → `core\theme/` (3)

## Se tocan juntos

Segun el historial de git. Si vas a cambiar uno, mira el otro.

- `EN-HUMANO.md` + `ESTADO.md` (39 commits)
- `.mapa/mapa.json` + `MAPA.md` (37 commits)
- `BITACORA.md` + `ESTADO.md` (26 commits)
- `EN-HUMANO.md` + `places/inversiones/cartera/bitacora_de_trabajo.md` (26 commits)
- `BITACORA.md` + `EN-HUMANO.md` (24 commits)
- `ESTADO.md` + `places/inversiones/cartera/bitacora_de_trabajo.md` (23 commits)
- `places/inversiones/cartera/bitacora_de_trabajo.md` + `places/inversiones/cartera/view.py` (21 commits)
- `.mapa/mapa.json` + `ESTADO.md` (20 commits)
- `ESTADO.md` + `MAPA.md` (20 commits)
- `ESTADO.md` + `ROADMAP.md` (17 commits)

## Fuentes externas

- `superapp-finanzas.fly.dev` — `docs\DEPLOY.md`, `docs\RUNBOOK.md`, `docs\WHATSAPP-CANAL.md`
- `graph.facebook.com` — `core\api\whatsapp_meta.py`, `docs\PLAN-FASE-A.md`, `scripts\probar_whatsapp_texto.py`
- `api.doctacapital.com.ar` — `docs\CRONOGRAMAS-RENTA-FIJA.md`
- `docs.docta.com.ar` — `docs\CRONOGRAMAS-RENTA-FIJA.md`
- `app.docta.com.ar` — `docs\CRONOGRAMAS-RENTA-FIJA.md`
- `mcp.docta.com.ar` — `docs\CRONOGRAMAS-RENTA-FIJA.md`
- `query1.finance.yahoo.com` — `docs\PEDIDO-GEMINI-CIERRE.md`
- `data912.com` — `docs\PEDIDO-GEMINI-CIERRE.md`
- `api.argentinadatos.com` — `docs\PEDIDO-GEMINI-CIERRE.md`
- `x.com` — `docs\PUBLICAR-EN-TIENDAS.md`
- `developers.facebook.com` — `docs\WHATSAPP-CANAL.md`
- `help.datacrazy.io` — `docs\WHATSAPP-CANAL.md`

## Configuracion requerida

- `API_HOST` — `api.py`
- `API_PORT` — `api.py`
- `BACKUP_RETENTION` — `core\db.py`
- `DB_PATH` — `core\db.py`
- `DIARIO_CSV` — `places\finanzas\core\ingest.py`, `tests\_oraculos.py`
- `GOOGLE_WORKSPACE_SECRET` — `core\api\google.py`
- `GOOGLE_WORKSPACE_WEBHOOK_URL` — `core\api\google.py`
- `MENSUAL_CSV` — `places\finanzas\core\ingest.py`, `tests\_oraculos.py`
- `SESSION_SECRET` — `core\auth\session_tokens.py`
- `SIGNUP_CODE` — `core\auth\login.py`
- `SUPERAPP_API_TOKEN` — `core\api\servidor.py`
- `SUPERAPP_DEFAULT_WORKSPACE` — `core\api\whatsapp_meta.py`
- `WHATSAPP_GRAPH_VERSION` — `core\api\whatsapp_meta.py`, `scripts\probar_whatsapp_texto.py`
- `WHATSAPP_TOKEN` — `scripts\probar_whatsapp_texto.py`

## Frescura

- Bitacoras vencidas: `integraciones\google-apps-script/`, `places\finanzas/`
