# MAPA — SuperAppFinanzas

<!-- GENERADO por indexar.py. No editar: los cambios se pierden. -->
<!-- La prosa vive en las BITACORA.md de cada carpeta. -->
<!-- 2026-10-16 12:18 UTC · 79 archivos · 14,096 LOC -->

## Como usar este archivo

Es el unico archivo del proyecto que hace falta leer para empezar. Para ubicar algo concreto: `python3 .mapa/buscar.py "<termino>"` devuelve archivo y linea sin abrir nada. Recien despues abrir los archivos que salgan, y solo esos.

Rama `main` — ultimo commit: 2026-10-15 d0533db docs: Fase B â€” mudanza de los briefings desde CallMeBot · **hay cambios sin commitear**

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
| configurar el webhook en el panel de Meta (verify token, `hub.challenge`) → `servidor.py` + `docs/WHATSAPP-CANAL.md` | `core\api/` |
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
| un mensaje de WhatsApp que no se cargó, se cargó mal o pidió confirmación → `comandos.py` (parser de montos y fechas, "¿quisiste decir?", `resumen`, `deshacer`) | `places\finanzas\core/` |
| Previsión vs Realidad por mes → `budget.py` | `places\finanzas\core/` |
| categorías, "sin categorizar", mapping Motivo → Grupo/Subcategoría → `categorizer.py`, `categorias.py` | `places\finanzas\core/` |
| importar `Diario.csv` / `Mensual.csv` (`ingest.py`, `parsers.py`; env `DIARIO_CSV`/`MENSUAL_CSV`) — por consola: `.venv\Scripts\python.exe -m places.finanzas.core.ingest --force` | `places\finanzas\core/` |
| un gasto que entró como $0, o una advertencia de "importe ilegible" al importar → `parsers.parse_currency_estricto` + `ingest._importe` | `places\finanzas\core/` |
| alta/edición/borrado de gastos y el backup automático que disparan → `transactions.py` | `places\finanzas\core/` |
| exportar todo a Excel → `export.py` | `places\finanzas\core/` |
| "$ mal formateado", separador de miles, un NaN visible en pantalla → `_format.py` | `places\finanzas\helpers/` |
| HTML que se muestra como texto crudo → `_html.render_html` | `places\finanzas\helpers/` |
| el tour guiado para usuarios nuevos → `_tour.py` | `places\finanzas\helpers/` |
| Dashboard, gráficos, editor de Fondo USD → `dashboard.py` | `places\finanzas\views/` |
| alta rápida vs. detallada de gastos, "Firmar como" → `transacciones.py` | `places\finanzas\views/` |
| Libro Diario → `diario.py` · Previsión vs Realidad → `mensual.py` | `places\finanzas\views/` |
| editor de categorías y sección "Espacio compartido" → `configuracion.py` | `places\finanzas\views/` |
| pantalla de bienvenida → `onboarding.py` | `places\finanzas\views/` |
| backup remoto diario, restaurar, "¿este backup sirve de verdad?" → `backup_remoto.ps1`, `restaurar_backup.ps1`, `verificar_backup.py`, `estado_backup.ps1`, `programar_backup.ps1` | `scripts/` |
| resetear la contraseña de un usuario → `setup_password.py` | `scripts/` |
| reindexar el mapa del repo → `indexar.py` (ver `/MAPA.md`) | `scripts/` |
| "¿Meta deja mandar texto sin tarjeta?" → `probar_whatsapp_texto.py` (prueba única de costo cero, ADR-0008; manda un texto libre y traduce el código de error de Meta) | `scripts/` |
| "el backup no corre solo", "la sesión de fly venció", token de Fly → `guardar_token_fly.ps1`, `_fly_comun.ps1` (`Use-TokenFly`) | `scripts/` |
| un archivo "BACKUP SUPERAPP - FALLO.txt" apareció en el Escritorio → lo deja `backup_remoto.ps1` al fallar; `estado_backup.ps1` dice por qué | `scripts/` |
| tests que escanean el código fuente: `test_nombres_definidos.py` (AST de names), `test_transacciones_formulario.py` (ramas del form), `test_env_example_sin_secretos.py` | `tests/` |
| los CSV oráculo de Finanzas → `_oraculos.py` (`DIARIO_CSV`/`MENSUAL_CSV`) | `tests/` |
| convención de nombres: `test_backup_*`/`test_db_*`/`test_workspaces_*` → core · el resto → Finanzas | `tests/` |
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
| `tests/` | La suite completa (468 tests al 15/10/2026, con la Fase A) en carpeta plana: unidad + regresión + oráculos contra los CSV de Franco. Es el gate del repo: nada se cierra sin verde. | 25 | 4,436 | **vencida** |
| `places\finanzas\core/` | Lógica de negocio de Finanzas, pura y sin Streamlit: transacciones, categorización, KPIs, presupuesto, libro diario, import de CSV y export a Excel. | 11 | 2,485 | ok |
| `places\finanzas\views/` | Las 5 pestañas de Finanzas + onboarding, en Streamlit puro; la lógica de negocio vive en `../core/`. | 7 | 1,860 | ok |
| `core/` | Núcleo compartido: SQLite (schema + migraciones M1–M17 + reparaciones únicas + backups), workspaces del grupo familiar (D2) y su UI. Auth, theme y la API HTTP (`api/`, Fase A) viven en subcarpetas propias. | 5 | 1,649 | ok |
| `scripts/` | Operación y mantenimiento: backups remotos (PowerShell + verificación), reset de contraseñas y el indexador del mapa. | 6 | 1,301 | ok |
| `core\theme/` | Design system "Cosmic Slate": CSS inyectado en Streamlit, paleta semántica + template Plotly unificado, ajustes responsive y logo. | 5 | 637 | ok |
| `core\api/` | API HTTP stdlib de la SuperApp (Fase A, ADR-0008): servidor con el webhook de WhatsApp firmado por Meta, dedupe y cola de trabajo, más el canal de Meta (único módulo que le habla). | 3 | 592 | ok |
| `core\auth/` | Autenticación compartida: usuarios con bcrypt, pantalla de login/signup y tokens de sesión firmados. (Los contextvars de usuario/workspace viven en `core/context.py`.) | 4 | 422 | ok |
| `./` | Raíz del monorepo: entry point (`app.py`: login único + navegación entre lugares), deploy (Dockerfile/fly.toml) y toda la gobernanza (ESTADO, ROADMAP, MEJORAS, guías). | 5 | 281 | ok |
| `places\finanzas\helpers/` | Utilidades de las vistas: formateo es-AR de montos, inyección de HTML y el tour guiado de bienvenida. | 4 | 278 | ok |
| `.github\workflows/` | CI: `tests.yml` corre la suite pytest en cada push (el gate de recon se saltea sin el Excel, así CI no depende de datos personales). | 1 | 82 | ok |
| `places\finanzas/` | Lugar A — Finanzas Personales (ex Mis-Finanzas-App / Radar Financiero): home con onboarding y las 5 pestañas. La lógica vive en `core/` local, las pantallas en `views/`. | 2 | 71 | ok |
| `places/` | _sin describir_ | 1 | 2 | — |
| `integraciones\google-apps-script/` | Puente Google ↔ SuperApp en Apps Script: reenvía el briefing de Gmail a la API (con links acortados) y atiende el webhook que crea/lista eventos de Calendar y tareas de Tasks. | 0 | 0 | **vencida** |

## Puntos de entrada

- `api.py`
- `app.py`
- `places\finanzas\core\ingest.py`
- `scripts\buscar.py`
- `scripts\indexar.py`
- `scripts\probar_whatsapp_texto.py`
- `scripts\setup_password.py`
- `scripts\verificar_backup.py`

## Archivos centrales

Ordenados por cuantos otros archivos dependen de ellos. Tocar uno de arriba tiene mas radio de impacto.

| Archivo | LOC | Lo usan | Simbolos |
|---|---:|---:|---|
| `core\db.py` | 1177 | 31 | `_migrate`, `es_tabla_faltante`, `get_db_path`, `connect` |
| `core\context.py` | 105 | 15 | `set_current_user_id`, `get_current_user_id`, `require_current_user_id`, `set_current_workspace_id` |
| `core\workspaces.py` | 261 | 14 | `_hash_code`, `_uid`, `get_personal_workspace_id`, `ensure_personal_workspace` |
| `places\finanzas\core\metrics.py` | 359 | 12 | `_uid`, `anios_con_datos`, `filtrar_anio`, `load_transactions` |
| `core\__init__.py` | 5 | 11 | — |
| `places\finanzas\core\transactions.py` | 243 | 7 | `_uid`, `_es_familiar`, `_asegurar_motivo`, `insert_transaction` |
| `places\finanzas\helpers\_tour.py` | 198 | 6 | `_user_id`, `is_tour_active`, `start_tour`, `finish_tour` |
| `places\finanzas\core\parsers.py` | 247 | 5 | `parse_currency`, `parse_currency_estricto`, `parse_date`, `normalize_motivo` |
| `places\finanzas\core\categorizer.py` | 136 | 5 | `categoria_de`, `efective_grupo`, `motivos_sin_categorizar` |
| `places\finanzas\helpers\_format.py` | 57 | 5 | `_is_nan`, `fmt_ars`, `fmt_ars_corto`, `fmt_usd` |
| `places\finanzas\helpers\_html.py` | 22 | 5 | `render_html` |
| `places\finanzas\core\ingest.py` | 381 | 4 | `ImportResult`, `_importe`, `_read_csv_rows`, `import_diario` |

## Flujo interno

- `tests/` → `core/` (29)
- `tests/` → `places\finanzas\core/` (18)
- `places\finanzas\core/` → `core/` (17)
- `places\finanzas\views/` → `places\finanzas\helpers/` (13)
- `places\finanzas\views/` → `places\finanzas\core/` (12)
- `places\finanzas\views/` → `core/` (8)
- `./` → `core/` (4)
- `places\finanzas/` → `core/` (3)
- `places\finanzas\views/` → `core\theme/` (3)
- `tests/` → `core\auth/` (3)
- `./` → `core\theme/` (2)
- `./` → `core\auth/` (2)

## Se tocan juntos

Segun el historial de git. Si vas a cambiar uno, mira el otro.

- `EN-HUMANO.md` + `ESTADO.md` (34 commits)
- `BITACORA.md` + `ESTADO.md` (26 commits)
- `EN-HUMANO.md` + `places/inversiones/cartera/bitacora_de_trabajo.md` (26 commits)
- `BITACORA.md` + `EN-HUMANO.md` (24 commits)
- `ESTADO.md` + `places/inversiones/cartera/bitacora_de_trabajo.md` (23 commits)
- `places/inversiones/cartera/bitacora_de_trabajo.md` + `places/inversiones/cartera/view.py` (21 commits)
- `.mapa/mapa.json` + `MAPA.md` (19 commits)
- `EN-HUMANO.md` + `places/inversiones/cartera/view.py` (17 commits)
- `BITACORA.md` + `places/inversiones/cartera/bitacora_de_trabajo.md` (15 commits)
- `ESTADO.md` + `places/inversiones/cartera/view.py` (14 commits)

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
- `MENSUAL_CSV` — `places\finanzas\core\ingest.py`, `tests\_oraculos.py`
- `SESSION_SECRET` — `core\auth\session_tokens.py`
- `SIGNUP_CODE` — `core\auth\login.py`
- `SUPERAPP_DEFAULT_WORKSPACE` — `core\api\whatsapp_meta.py`
- `WHATSAPP_GRAPH_VERSION` — `core\api\whatsapp_meta.py`, `scripts\probar_whatsapp_texto.py`
- `WHATSAPP_TOKEN` — `scripts\probar_whatsapp_texto.py`

## Frescura

- Bitacoras vencidas: `integraciones\google-apps-script/`, `tests/`
