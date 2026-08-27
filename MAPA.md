# MAPA — SuperAppFinanzas

<!-- GENERADO por indexar.py. No editar: los cambios se pierden. -->
<!-- La prosa vive en las BITACORA.md de cada carpeta. -->
<!-- 2026-08-27 02:37 UTC · 122 archivos · 25,612 LOC -->

## Como usar este archivo

Es el unico archivo del proyecto que hace falta leer para empezar. Para ubicar algo concreto: `python3 .mapa/buscar.py "<termino>"` devuelve archivo y linea sin abrir nada. Recien despues abrir los archivos que salgan, y solo esos.

Rama `main` — ultimo commit: 2026-08-26 91ddf38 aa · **hay cambios sin commitear**

## Donde buscar que

| Si la consulta es sobre... | Ir a |
|---|---|
| el arranque de la app, la navegación entre lugares o la restauración de sesión → `app.py` | `./` |
| deploy, Docker, Fly.io → `Dockerfile`, `fly.toml`, `docker-entrypoint.sh`, `docs/DEPLOY.md` y `docs/RUNBOOK.md` | `./` |
| cómo se trabaja en este repo → `GUIA-DE-TRABAJO.md`, `claude.md`, `/MAPA.md` | `./` |
| qué se hizo y qué sigue → `ESTADO.md` (foto), este archivo (crónica), `EN-HUMANO.md` (en llano) | `./` |
| CI rojo en GitHub → `tests.yml` | `.github\workflows/` |
| por qué el batch del scoring ya no está acá → scoring retirado (5/8/2026) | `.github\workflows/` |
| la base de datos: schema, una migración nueva (SIEMPRE aditiva), "database is locked", backups y retención (`BACKUP_RETENTION`, `DB_PATH`) | `core/` |
| grupo familiar / espacios compartidos: crear, unirse, código de invitación, resolver el workspace activo | `core/` |
| el badge Personal/Familiar o el switcher del sidebar se comportan raro | `core/` |
| un import circular entre core y core/auth → **cortado** el 27/8/2026 con `context.py` | `core/` |
| quién es el usuario o el workspace activo, desde lógica sin Streamlit → `context.py` | `core/` |
| login, signup, contraseñas, código de registro (`SIGNUP_CODE`) | `core\auth/` |
| "me pide loguearme en cada refresh" → tokens firmados en la URL (`session_tokens.py`, `SESSION_SECRET`) | `core\auth/` |
| necesitás saber quién es el usuario o workspace actual desde lógica sin Streamlit → contextvars (`current_user.py`, `current_workspace.py`) | `core\auth/` |
| el botón de logout | `core\auth/` |
| dólar MEP histórico o de hoy, el TC congelado por operación (`mep.py`) | `core\market_data/` |
| un precio falta o viene raro: bonos ×100, override, caché (`precios.py`) | `core\market_data/` |
| sector/industria de un ticker para el análisis de composición (`sectores.py`) | `core\market_data/` |
| cronogramas de pago, cupones, Docta (`cronogramas.py`, `DOCTA_CLIENT_ID/SECRET`) | `core\market_data/` |
| una fuente externa caída y qué fallback aplica | `core\market_data/` |
| la serie histórica de un índice para comparar contra la cartera (`indices.py`) | `core\market_data/` |
| estética, colores, tipografía, dark mode, "se ve poco profesional" | `core\theme/` |
| "se ve mal en el celular" → `_responsive.py` | `core\theme/` |
| un gráfico Plotly con colores fuera de paleta → `_theme.py` | `core\theme/` |
| KPI cards, tokens de diseño, flash sin estilos (FOUC) | `core\theme/` |
| el logo → `_logo.py` | `core\theme/` |
| el onboarding aparece cuando no debería (se evalúa SIEMPRE contra el espacio personal) | `places\finanzas/` |
| el orden de las pestañas o una pestaña entera caída → `home.py` | `places\finanzas/` |
| el badge grande del modo familiar | `places\finanzas/` |
| números del dashboard que no cierran → `metrics.py` | `places\finanzas\core/` |
| Previsión vs Realidad por mes → `budget.py` | `places\finanzas\core/` |
| categorías, "sin categorizar", mapping Motivo → Grupo/Subcategoría → `categorizer.py`, `categorias.py` | `places\finanzas\core/` |
| importar `Diario.csv` / `Mensual.csv` (`ingest.py`, `parsers.py`; env `DIARIO_CSV`/`MENSUAL_CSV`) | `places\finanzas\core/` |
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
| "¿dónde está el scoring?" → retirado por decisión de Franco (ADR-0002 marcado retirado; el código quedó en `Borrar/`). Los sectores ahora salen 100% de Yahoo. | `places\inversiones/` |
| las pestañas del lugar → `home.py` | `places\inversiones/` |
| Mercado en vivo → todavía no existe (Fase 5; fuentes candidatas en `docs/DATOS-MERCADO-ARG.md`) | `places\inversiones/` |
| números que no calzan con el broker o el Excel → `posiciones.py`, `tenencias.py` y el gate `tests/test_cartera_recon.py` | `places\inversiones\cartera/` |
| importar movimientos o tenencias, dedupe, formatos viejo/nuevo del export → `parser.py`, `tenencias.py`, `ingest.py` | `places\inversiones\cartera/` |
| rendimiento, TIR, resultado realizado → `ledger.py` (PPC móvil, ADR-0005), `kpis.py` | `places\inversiones\cartera/` |
| cauciones, cuenta remunerada, dividendos → `rendimientos.py` | `places\inversiones\cartera/` |
| vencimientos, cupones, TIR esperada y duration → `vencimientos.py`, `renta_fija.py` | `places\inversiones\cartera/` |
| composición por tipo de renta y sector → `analisis.py` | `places\inversiones\cartera/` |
| "¿me fue mejor o peor que el mercado?" → `benchmark.py` (money-weighted, con `core/market_data/indices.py`) | `places\inversiones\cartera/` |
| un ticker que el broker no informa o cantidades a corregir a mano → `ajustes.py` | `places\inversiones\cartera/` |
| la pantalla de Cartera, quién puede verla (`CARTERA_USER_IDS`), el orden de los paneles → `view.py` | `places\inversiones\cartera/` |
| un panel concreto (composición, benchmark, vencimientos, renta fija, caja, ajustes, upload) → `paneles/` | `places\inversiones\cartera/` |
| exportar la cartera a Excel → `export.py` | `places\inversiones\cartera/` |
| "Cómo está repartida" (tipo de renta, sector, industria, emisor, país) → `composicion.py` | `places\inversiones\cartera\paneles/` |
| "Contra el mercado" (benchmark money-weighted vs SPY/Merval) → `mercado.py` | `places\inversiones\cartera\paneles/` |
| "Qué se te vence" y el alta manual de una fecha → `vencimientos.py` | `places\inversiones\cartera\paneles/` |
| "Cuándo cobrás" (cronogramas, TIR esperada, duration) → `renta_fija.py` | `places\inversiones\cartera\paneles/` |
| "Operaciones cerradas" (resultado realizado) → `operaciones.py` | `places\inversiones\cartera\paneles/` |
| "La plata quieta" (cauciones, dividendos, cuenta remunerada) → `caja.py` | `places\inversiones\cartera\paneles/` |
| ajustes de tenencia: splits, ratios de CEDEAR, papeles pre-registro → `ajustes.py` | `places\inversiones\cartera\paneles/` |
| la subida del export del broker, el orden del import, el estado vacío → `importar.py` | `places\inversiones\cartera\paneles/` |
| un precio o el MEP que llega raro a un panel, la foto de posiciones → `_datos.py` | `places\inversiones\cartera\paneles/` |
| "$ mal formateado" o una KPI card → `_comun.py` | `places\inversiones\cartera\paneles/` |
| backup remoto diario, restaurar, "¿este backup sirve de verdad?" → `backup_remoto.ps1`, `restaurar_backup.ps1`, `verificar_backup.py`, `estado_backup.ps1`, `programar_backup.ps1` | `scripts/` |
| resetear la contraseña de un usuario → `setup_password.py` | `scripts/` |
| ¿Docta cubre los bonos de la cartera? → `verificar_docta.py` | `scripts/` |
| reindexar el mapa del repo → `indexar.py` (ver `/MAPA.md`) | `scripts/` |
| el gate de reconciliación contra el Excel → `test_cartera_recon.py` (necesita `CARTERA_XLSX`; sin él se saltea con mensaje claro, por eso "3 skipped" es normal) | `tests/` |
| tests que escanean el código fuente: `test_nombres_definidos.py` (AST de names), `test_transacciones_formulario.py` (ramas del form), `test_env_example_sin_secretos.py` | `tests/` |
| los CSV oráculo de Finanzas → `_oraculos.py` (`DIARIO_CSV`/`MENSUAL_CSV`) | `tests/` |
| convención de nombres: `test_cartera_*` → cartera · `test_market_data_*` → core/market_data · `test_backup_*`/`test_db_*`/`test_workspaces_*` → core · el resto → Finanzas | `tests/` |
| los premortem-tests (`test_premortem3/5.py`): regresiones de los riesgos del premortem | `tests/` |

## Carpetas

| Carpeta | Que es | Arch. | LOC | Bitacora |
|---|---|---:|---:|---|
| `tests/` | La suite completa (~360 tests) en carpeta plana: unidad + regresión + gates de reconciliación contra el Excel-oráculo. Es el gate del repo: nada se cierra sin verde. | 33 | 8,173 | **vencida** |
| `places\inversiones\cartera/` | Cartera nativa (B.1): parser de exports del broker (2 formatos), ledger cronológico con PPC móvil, posiciones, KPIs por método del patrimonio, renta fija y la vista con upload. | 15 | 5,639 | **vencida** |
| `places\finanzas\core/` | Lógica de negocio de Finanzas, pura y sin Streamlit: transacciones, categorización, KPIs, presupuesto, libro diario, import de CSV y export a Excel. | 10 | 2,006 | **vencida** |
| `places\finanzas\views/` | Las 5 pestañas de Finanzas + onboarding, en Streamlit puro; la lógica de negocio vive en `../core/`. | 7 | 1,860 | **vencida** |
| `core/` | Núcleo compartido: SQLite (schema + migraciones M1–M15 + backups), workspaces del grupo familiar (D2) y su UI. Auth y theme viven en subcarpetas propias. | 5 | 1,553 | **vencida** |
| `places\inversiones\cartera\paneles/` | Los paneles de la pantalla de Cartera, uno por archivo. Salieron de `view.py` en el split del 27/8/2026, que movió código sin cambiarlo. | 11 | 1,521 | **vencida** |
| `core\market_data/` | Datos de mercado para valuar la cartera: MEP histórico (argentinadatos), precios ARG (data912) y globales (yahoo), sectores por ticker y cronogramas de renta fija (Docta). | 6 | 1,387 | **vencida** |
| `scripts/` | Operación y mantenimiento: backups remotos (PowerShell + verificación), reset de contraseñas, chequeo de cobertura de Docta y el indexador del mapa. | 6 | 1,253 | **vencida** |
| `core\theme/` | Design system "Cosmic Slate": CSS inyectado en Streamlit, paleta semántica + template Plotly unificado, ajustes responsive y logo. | 5 | 680 | **vencida** |
| `core\auth/` | Autenticación compartida: usuarios con bcrypt, pantalla de login/signup, tokens de sesión firmados y los contextvars de usuario/workspace activos. | 6 | 462 | **vencida** |
| `Borrar\scoring-retirado-1786650535/` | _sin describir_ | 3 | 325 | — |
| `places\finanzas\helpers/` | Utilidades de las vistas: formateo es-AR de montos, inyección de HTML y el tour guiado de bienvenida. | 4 | 288 | **vencida** |
| `./` | Raíz del monorepo: entry point (`app.py`: login único + navegación entre lugares), deploy (Dockerfile/fly.toml) y toda la gobernanza (ESTADO, ROADMAP, MEJORAS, guías). | 4 | 221 | **vencida** |
| `.github\workflows/` | CI: `tests.yml` corre la suite pytest en cada push (el gate de recon se saltea sin el Excel, así CI no depende de datos personales). | 1 | 82 | ok |
| `places\finanzas/` | Lugar A — Finanzas Personales (ex Mis-Finanzas-App / Radar Financiero): home con onboarding y las 5 pestañas. La lógica vive en `core/` local, las pantallas en `views/`. | 2 | 71 | **vencida** |
| `Borrar/` | _sin describir_ | 1 | 52 | — |
| `places\inversiones/` | Lugar B — Inversiones: pestaña Cartera (en `cartera/`) y Mercado en vivo (placeholder de Fase 5). El scoring se retiró el 5/8/2026. | 2 | 37 | **vencida** |
| `places/` | _sin describir_ | 1 | 2 | — |

## Puntos de entrada

- `app.py`
- `places\finanzas\core\ingest.py`
- `scripts\buscar.py`
- `scripts\indexar.py`
- `scripts\setup_password.py`
- `scripts\verificar_backup.py`
- `scripts\verificar_docta.py`

## Archivos centrales

Ordenados por cuantos otros archivos dependen de ellos. Tocar uno de arriba tiene mas radio de impacto.

| Archivo | LOC | Lo usan | Simbolos |
|---|---:|---:|---|
| `core\db.py` | 1081 | 42 | `_migrate`, `get_db_path`, `connect`, `init_db` |
| `core\workspaces.py` | 261 | 13 | `_hash_code`, `_uid`, `get_personal_workspace_id`, `ensure_personal_workspace` |
| `core\context.py` | 105 | 12 | `set_current_user_id`, `get_current_user_id`, `require_current_user_id`, `set_current_workspace_id` |
| `core\__init__.py` | 5 | 12 | — |
| `places\inversiones\cartera\posiciones.py` | 471 | 11 | `Posicion`, `_acumular`, `posiciones`, `posiciones_desde_db` |
| `places\finanzas\core\metrics.py` | 363 | 11 | `_uid`, `anios_con_datos`, `filtrar_anio`, `load_transactions` |
| `places\inversiones\cartera\parser.py` | 638 | 10 | `Instrumento`, `Movimiento`, `_sin_tildes`, `_norm` |
| `places\inversiones\cartera\__init__.py` | 2 | 10 | — |
| `places\inversiones\cartera\paneles\_comun.py` | 45 | 9 | `_fmt`, `_kpi_card` |
| `core\market_data\__init__.py` | 47 | 8 | — |
| `places\inversiones\cartera\ingest.py` | 418 | 6 | `_filas_config`, `instrumentos_desde_config`, `cargar_instrumentos_en_db`, `_fecha` |
| `places\finanzas\helpers\_tour.py` | 198 | 6 | `_user_id`, `is_tour_active`, `start_tour`, `finish_tour` |

## Flujo interno

- `tests/` → `places\inversiones\cartera/` (31)
- `tests/` → `core/` (28)
- `places\finanzas\core/` → `core/` (17)
- `places\finanzas\views/` → `places\finanzas\helpers/` (13)
- `places\finanzas\views/` → `places\finanzas\core/` (12)
- `places\inversiones\cartera\paneles/` → `places\inversiones\cartera/` (12)
- `places\inversiones\cartera/` → `places\inversiones\cartera\paneles/` (10)
- `tests/` → `places\finanzas\core/` (10)
- `places\finanzas\views/` → `core/` (8)
- `places\inversiones\cartera\paneles/` → `core\market_data/` (8)
- `places\inversiones\cartera\paneles/` → `core/` (7)
- `places\inversiones\cartera/` → `core\market_data/` (6)

## Se tocan juntos

Segun el historial de git. Si vas a cambiar uno, mira el otro.

- `EN-HUMANO.md` + `ESTADO.md` (32 commits)
- `EN-HUMANO.md` + `places/inversiones/cartera/bitacora_de_trabajo.md` (26 commits)
- `BITACORA.md` + `ESTADO.md` (24 commits)
- `BITACORA.md` + `EN-HUMANO.md` (23 commits)
- `ESTADO.md` + `places/inversiones/cartera/bitacora_de_trabajo.md` (23 commits)
- `places/inversiones/cartera/bitacora_de_trabajo.md` + `places/inversiones/cartera/view.py` (21 commits)
- `EN-HUMANO.md` + `places/inversiones/cartera/view.py` (17 commits)
- `BITACORA.md` + `places/inversiones/cartera/bitacora_de_trabajo.md` (15 commits)
- `ESTADO.md` + `places/inversiones/cartera/view.py` (14 commits)
- `BITACORA.md` + `ROADMAP.md` (8 commits)

## Fuentes externas

- `api.doctacapital.com.ar` — `core\market_data\cronogramas.py`, `docs\CRONOGRAMAS-RENTA-FIJA.md`, `tests\test_market_data_cronogramas.py`
- `api.anthropic.com` — `backups-remotos\superapp-20260804-105642.db-shm`, `backups-remotos\superapp-20260804-110250.db-shm`
- `fmarconi1-dev.github.io` — `Borrar\scoring-retirado-1786650535\snapshot.py`, `Borrar\scoring-retirado-1786650535\view.py`
- `query1.finance.yahoo.com` — `core\market_data\indices.py`, `core\market_data\precios.py`
- `app.docta.com.ar` — `docs\CRONOGRAMAS-RENTA-FIJA.md`, `scripts\verificar_docta.py`
- `microsoft.com` — `backups-remotos\superapp-20260804-105642.db-shm`
- `diagnostics.microsoft.com` — `backups-remotos\superapp-20260804-105642.db-shm`
- `go.microsoft.com` — `backups-remotos\superapp-20260804-105642.db-shm`
- `finance.yahoo.com` — `Borrar\scoring-retirado-1786650535\view.py`
- `api.argentinadatos.com` — `core\market_data\mep.py`
- `data912.com` — `core\market_data\precios.py`
- `query2.finance.yahoo.com` — `core\market_data\sectores.py`

## Configuracion requerida

- `BACKUP_RETENTION` — `core\db.py`
- `CARTERA_USER_IDS` — `places\inversiones\cartera\view.py`
- `CARTERA_XLSX` — `tests\test_cartera_recon.py`
- `DB_PATH` — `core\db.py`
- `DIARIO_CSV` — `places\finanzas\core\ingest.py`, `tests\_oraculos.py`
- `DOCTA_CLIENT_ID` — `core\market_data\cronogramas.py`, `scripts\verificar_docta.py`
- `DOCTA_CLIENT_SECRET` — `core\market_data\cronogramas.py`, `scripts\verificar_docta.py`
- `MENSUAL_CSV` — `places\finanzas\core\ingest.py`, `tests\_oraculos.py`
- `SCORING_CACHE_PATH` — `Borrar\scoring-retirado-1786650535\snapshot.py`
- `SCORING_SNAPSHOT_URL` — `Borrar\scoring-retirado-1786650535\snapshot.py`
- `SESSION_SECRET` — `core\auth\session_tokens.py`
- `SIGNUP_CODE` — `core\auth\login.py`

## Frescura

- Bitacoras vencidas: `./`, `core/`, `core\auth/`, `core\market_data/`, `core\theme/`, `places\finanzas/`, `places\finanzas\core/`, `places\finanzas\helpers/`, `places\finanzas\views/`, `places\inversiones/`, `places\inversiones\cartera/`, `places\inversiones\cartera\paneles/`, `scripts/`, `tests/`
- Carpetas sin bitacora: `Borrar\scoring-retirado-1786650535/`
