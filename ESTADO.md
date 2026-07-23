# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".

<!-- ultima_actualizacion: 2026-07-23 · autor: Claude (Opus 4.8) · handoff: Fase 3a paso 1 (parser del broker) hecho y testeado; sigue paso 2 (modelo de datos M9) -->

## 🧭 Dónde estamos

- **Fase actual:** **Fase 3a — Cartera nativa, DISEÑADA y lista para construir** (2026-07-19). Diseño cerrado en `docs/decisiones/ADR-0003-cartera-nativa.md`; los Excel ya fueron estudiados a fondo.
- **Situación:** Superapp en producción con login único, dos lugares (Finanzas + Inversiones/Scoring), y **espacios compartidos** (grupo familiar D2) funcionando. 114 tests en verde. Incidente de migración del 17/7 resuelto (ver Nota post-incidente). radar-financiero sigue vivo como respaldo.
- **Hosting:** Fly.io. App `superapp-finanzas` (gru, 1 GB, auto-stop, volumen `finanzas_data` con snapshots diarios). Sin secrets (radar tampoco tenía; SIGNUP_CODE/SESSION_SECRET opcionales, ver `.env.example`). Ver `docs/DEPLOY.md`.
- **Repo git:** hasta `8a5087a` (migración Fase 1) + commits de cierre. Verificar push al retomar.

## 🔵 Tarea en curso

| Tarea | Estado | Autor | Desde |
|---|---|---|---|
| Fase 3a — Cartera nativa (ingest + posiciones + KPIs) | 🔵 EN CURSO | Claude (Fable 5) | 2026-07-19 |

## ✅ Hecho hasta ahora

- Premortem de la idea (`Premortem - Superapp Finanzas.html` + transcripción).
- Plan de trabajo maestro (`PLAN DE TRABAJO - Superapp Finanzas.md`).
- `EN-HUMANO.md` (diario en lenguaje llano) y `docs/PROMPT-INICIO-FABLE.md` (prompt de arranque).
- Esqueleto del monorepo: carpetas, READMEs, bitácoras, documentos de gobierno, `.gitignore`, `.pre-commit-config.yaml`, `.env.example`, docs y ADR-0001.
- **Fase 0 completa (2026-07-10):**
  - Primer commit del esqueleto pusheado al repo GitHub.
  - Pre-commit hook instalado con **dos capas**: chequeo anti-datos puro `sh` (funciona también desde GitHub Desktop/Windows, sin dependencias) + framework `pre-commit` cuando está disponible. **Probado:** un `.xlsx` de prueba fue bloqueado en ambas capas.
  - Hola mundo Streamlit desplegado en Fly.io (`app.py`, `Dockerfile`, `fly.toml`, `.dockerignore` anti-leak). Deploy verificado por Franco.

## ⏭️ Próximo paso concreto

**Fase 3a — Cartera NATIVA (construir; diseño cerrado en ADR-0003).** Orden de construcción (5 pasos):

> **Paso 1 ✅ HECHO (2026-07-23).** Parser del broker construido y testeado: `places/inversiones/cartera/parser.py` (rescatado del borrador untracked, 3 arreglos) + `places/inversiones/cartera/__init__.py` + `tests/test_cartera_parser.py` (43 tests). Suite completa **157 en verde**. Commiteado en `fase-3a/cartera-nativa` (pendiente de push por Franco). **Próximo: paso 2 (modelo de datos M9).** Detalle en `places/inversiones/cartera/bitacora_de_trabajo.md`.

1. **Parser del broker** (`places/inversiones/cartera/parser.py`) + tests. ✅ HECHO. Spec relevada del Excel:
   - **Formato viejo** (8 cols): Operación | Concertación | Liquidación | Descripción | Monto | Cantidad | Precio | Moneda. ⚠️ la col Moneda es poco confiable (hay compras ARS marcadas USD); inferir de la descripción/ticker (sufijo D = USD) y magnitudes.
   - **Formato nuevo** (desde ~mayo 2026, filas 2-32 del crudo): SIN columna Operación — arranca en Concertación; el tipo se infiere (monto<0+cantidad>0=compra; monto>0+cantidad<0=venta; "CC |"=caución; sin cantidad y monto chico=dividendo/retención según signo).
   - **12 categorías** (según `Movimientos Procesado`): COMPRA, VENTA, DIVIDENDO, RETENCION, RENTA, AMORTIZACION, CAUCION_COL, CAUCION_VTO, REMUNERACION, DEPOSITO, RETIRO, OTROS.
   - **Reglas del LEEME**: dividendos solo línea USD (la espejo ARS negativa se ignora); bonos ARS y USD dividen precio por 100; saldos iniciales sintéticos en crudo filas 525-528 (NO descartar); ticker se extrae de "TICKER | Descripción".
   - Dedupe por hash (fecha+operación+descripción+monto) para la carga recurrente.
2. **Modelo de datos**: tabla `mov_cartera` (migración M9; scope por usuario — solo Franco ve Cartera, configurable) con TC MEP histórico congelado por fila; tabla de mapping tipo hoja Config; caché de precios.
3. **`core/market_data/`**: MEP histórico y actual (BCRA oficial), precios ARG (data912/byma), CEDEARs/BTC (yahoo). Capa por proveedor + caché + override manual. Referencia: `gauss314/skills`.
4. **Posiciones + KPIs + vista** (promedio ponderado, como el Excel) en pestaña Cartera.
5. **Gate `tests/test_cartera_recon.py`**: correr el motor SOLO sobre las filas que el Excel procesó (hasta 19/5/2026) → cantidades y costos ARS deben calzar EXACTOS contra `Resumen Cartera`; USD se reconcilia en modo "MEP actual" (metodología del Excel). Después importar el resto.

⚠️ **Hallazgo clave (avisado a Franco):** el broker cambió el formato del export y el Excel NO procesa los movimientos desde el 20/5/2026 — hay 31 filas (compras NBIS/ASML, cauciones, dividendos) fuera del Total Cartera de la planilla. Nuestro parser debe manejar ambos formatos; la app quedará más al día que el Excel.
✅ Los 2 `#REF!` (Resumen Cartera L4/P4) están **resueltos**: Franco ya borró la fila 32 de `Movimientos Procesado` (verificado 2026-07-23 — no queda ningún `#REF!` en el libro; las fórmulas saltan de `Crudo!B62` a `B64`).

⚠️ **Hallazgo nuevo (2026-07-23): la columna Moneda de `Movimientos Procesado` (col F) está desalineada ~30 filas** — lee la moneda de otra operación (p. ej. un dividendo JPM real `USD.C` queda etiquetado `ARS`). Explica en parte la "columna Moneda poco confiable". **No afecta las cantidades** del recon (Resumen usa Δ Cantidad, col N); toca costos de compras solo donde la moneda mal leída se voltea (raro: las compras son casi todas ARS; los USD son dividendos/cauciones, que no son compras). El parser **infiere** la moneda, así que la app es inmune y más correcta que el Excel. En el paso 5 se reconcilia contra la moneda **corregida** (releída de la fila alineada) y se documenta la divergencia. Franco puede querer arreglar la col F de su Excel aparte (no se toca sin permiso).
3b (siguiente): realized PnL por trade, cauciones/dividendos como rendimientos, análisis sector (reusar sector del snapshot de scoring) y tipo de renta. Renta fija (`Renta fija ARG.xlsx`) NO va en cartera: queda para una futura sección de análisis de mercado (está en MEJORAS).

**Pendientes menores:**
- Retirar `radar-financiero` cuando la superapp esté validada unos días (`fly apps destroy radar-financiero`).
- Generar `requirements.lock` para builds reproducibles (ver `docs/DEPLOY.md`).
- Dominio personalizado (FreeDomain o propio): decisión de Franco, queda para el final — es estético. Pasos en `docs/DEPLOY.md`.

## 🚩 Bloqueos / decisiones abiertas

- Fuente de datos de mercado ARG: 🟢 candidatos en `gauss314/skills` (`bcra-macro`, `data912`, `byma`, `mae`). Se valida y elige en Fase 5. Ver `docs/DATOS-MERCADO-ARG.md`.
- Nombre de la app Fly: `superapp-finanzas`. **Fly no permite renombrar apps**; si se quiere otro nombre, crear app nueva y redeployar **antes** de crear el volumen de la DB (Fase 1), o resolverlo con dominio propio (FreeDomain).

## ⚠️ Nota post-incidente: migraciones (17/7/2026)

M4 (PK con user_id) se re-disparó tras M8 (PK con workspace_id) porque su guard solo miraba la PK: reconstruyó las tablas descartando `workspace_id` y desvinculó los datos en producción. Resuelto: guard de M4 exige tabla no-post-D2, y M8.5 repara filas huérfanas (idempotente, prefiere el dato original ante duplicados). **Lecciones para futuras migraciones:** (1) los guards de migraciones viejas deben seguir siendo correctos frente a esquemas futuros; (2) los tests de idempotencia deben correr CON datos y verificar vínculos, no solo que no crashee. Tests de regresión en `tests/test_workspaces_d2.py`.

## ⚠️ Nota operativa: git + OneDrive

La carpeta del repo vive en OneDrive y dio problemas reales en esta sesión: locks huérfanos (`HEAD.lock`, `index.lock`), archivos commiteados truncados por sync parcial y un índice corrupto (recuperado sin pérdida). **Protocolo para el Claude que trabaje acá:** editar archivos vía shell (no solo herramientas de archivo), y tras cada commit verificar `git status` limpio + `git fsck` + conteo de líneas de los archivos tocados en HEAD. Si git no ve un cambio, `touch` + `git update-index --really-refresh`. Mitigación aplicada (2026-07-10): Franco activó "mantener siempre en este dispositivo" para la carpeta, eliminando los placeholders cloud-only. El protocolo de verificación sigue vigente igual.

## 📌 Recordatorios permanentes

- No commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`).
- Una fase a la vez, cerrada y desplegable.
- Cerrar sesión = actualizar bitácora + este archivo.
