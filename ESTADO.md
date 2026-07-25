# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".

<!-- ultima_actualizacion: 2026-07-23 · autor: Claude (Opus 4.8) · handoff: Fase 3a pasos 1-4 hechos; la Cartera YA vive en la app (vista + upload). Falta paso 5 (recon USD modo MEP actual) + merge a main + deploy -->

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

> **Paso 1 ✅ HECHO (2026-07-23).** Parser del broker construido y testeado: `places/inversiones/cartera/parser.py` (rescatado del borrador untracked, 3 arreglos) + `places/inversiones/cartera/__init__.py` + `tests/test_cartera_parser.py` (43 tests).
>
> **Excel-oráculo actualizado y reconciliado (2026-07-23).** Franco pasó el export completo de inviu + la Tenencia del broker al 24/7. Se reconstruyó `Inversiones.xlsx` (respaldo del original en "Inversiones - respaldo pre-2026-07-23.xlsx"): crudo = export + saldos sintéticos + ajuste de ratio SPY (+70, confirmado); Procesado con fórmulas 1:1 y **columna Moneda alineada**; Config con SATL/UNH/CEG; Resumen corregido (salteaba NBIS, duplicaba GGALX); MEP=1519,725, BTC=65877. **Recalculado con LibreOffice: 20/20 posiciones EXACTAS vs broker.** El parser reprodujo 19/20 solo con movimientos+seeds (la brecha SPY es el ajuste de ratio externo) → validación fuerte del motor.
>
> **Paso 2 ✅ HECHO (2026-07-23).** Modelo de datos **M9** (aditivo, `core/db.py`): `cartera_instrumentos`, `cartera_movimientos` (con `tc_mep` NULL hasta paso 3, `UNIQUE(user_id, hash_dedupe)`), `cartera_precios_cache` — **scope por user_id** (la cartera es personal). `tests/test_cartera_db.py` (8 tests).
>
> **Ingest + reconciliación ✅ HECHO (2026-07-23).** `places/inversiones/cartera/ingest.py` (instrumentos desde Config + `importar_movimientos` con dedupe) y `posiciones.py` (portan `Resumen Cartera`). Gate `tests/test_cartera_recon.py`: parte del crudo del Excel → parser → posiciones y **reconcilia exacto contra `Resumen Cartera`** (verificado con el Excel recalculado; se saltea sin romper CI si no hay Excel/caché — corre local con `CARTERA_XLSX`). `tests/test_cartera_ingest.py` (5). Suite **170 passed, 1 skipped**.
>
> **Paso 3 ✅ HECHO (2026-07-23).** `core/market_data/` con `fetch` inyectable (tests sin red): `mep.py` (serie histórica, último hábil anterior, caché, fallback, override) y `precios.py` (data912 ARG + yahoo BTC, caché, override, **bonos /100**), más `ingest.congelar_tc_mep` (idempotente). **⚠️ El BCRA NO publica MEP** (sirve el mayorista A3500: 1.480,86 vs MEP 1.521,9 al 22/7) → supuesto del ADR-0003 corregido en **ADR-0004**: fuente `argentinadatos` (elegida por Franco; cubre 419/419 días hábiles del historial). **Humo real: 585 movimientos del Excel importados con TC congelado en las 585 filas, cero fechas sin dato.** `tests/test_market_data.py` (18). Suite **188 passed, 1 skipped**.
>
> **Paso 4 ✅ HECHO (2026-07-23) — la Cartera ya vive en la app.** `posiciones.py` con costo promedio ponderado + costo USD a TC histórico; `kpis.py` (valuación con precio inyectable; el costo de lo que no tiene precio no entra a los totales); **`view.py`** cableada en la pestaña Cartera: KPI cards con tokens Cosmic Slate (tabular-nums, signo+flecha+color), tabla es-AR, **upload del export del broker** (dedupe + congelado de TC en el mismo flujo), carga de instrumentos desde Config, caché de 5 min y estados empty/error. Scope por usuario (`CARTERA_USER_IDS`, default solo Franco). `tests/test_cartera_kpis.py` (12). **Verificado end-to-end con datos reales: $15.490.098 / US$10.101 · +19,8% · 23 posiciones.** Suite **200 passed, 1 skipped**.
>
> **Rendimiento completo ✅ HECHO (2026-07-23, a pedido de Franco — adelanta parte de 3b).** Las amortizaciones son rendimiento y no se computaban ($6.345.528 en flujos afuera), y las 6 letras vencidas figuraban con cantidad residual. Ahora: **cierre de vencidos** usando la señal del propio Excel (`Config!L = NO`, sin heurísticas) y **rendimiento completo** (realizado en ventas + no realizado + amortizaciones/rentas/dividendos) **en ARS y en USD al MEP del día de cada operación**. ⚠️ Bug corregido en el camino: la amortización devuelve **capital + interés** — sin descontar el capital, las letras daban ~100-113%; se agregó `costo_amortizado_*`. Tras el fix, cada letra reproduce exactamente el cálculo manual (S15G5 +3,8% ARS / **−3,6% USD**).
>
> ⚠️ **CORREGIDO (mismo día, lo detectó Franco).** Los primeros números (+31,3% / +16,9% sobre US$25.219 "invertidos") **eran incorrectos**. Tres errores: (1) el denominador era la suma de todas las compras — capital *rotado*, que cuenta la misma plata cada vez que se reinvierte — en vez del **capital aportado** (depósitos − retiros); (2) los **saldos iniciales sintéticos están en USD** (las 3 compras suman exacto el depósito que las cubre) y se tomaban como ARS, subvaluando el capital inicial ~1.000×; (3) **la suma por instrumento no sirve como total de cartera**: al pasar importes USD a pesos con el TC de cada fecha, la devaluación infla el resultado — verificado en pesos (sin efecto FX): $9,92M por componentes contra $2,27M por patrimonio.
>
> **Método adoptado: patrimonio** (el único verificable; es el que define el panel `General` del Excel): `resultado = (tenencia + efectivo) − (depósitos − retiros)`, cada aporte al MEP de su fecha. `saldos_efectivo()` reconstruye el cash y se contrastó contra el broker (ARS $27.530 vs $26.069; USD 72 vs 54,5).
>
> **Números correctos:** capital aportado $13.162.628 (**US$11.338**) · patrimonio hoy $15.544.931 (US$10.137) → **+$2.382.303 (+18,1%) en pesos, −US$1.201 (−10,6%) en dólares**. Suite **209 passed, 1 skipped** + **recon verde**.
>
> 🧭 **Lección para quien siga:** todo agregado de una cartera bimonetaria debe contrastarse contra una identidad contable independiente (patrimonio vs aportes) **antes** de mostrarse. Sumar operación por operación parece razonable y da resultados muy equivocados.
>
> ⚠️ **HALLAZGO ESTRUCTURAL (M10): el export de movimientos NO alcanza para reconstruir la cartera.** Franco detectó que faltaba el 35% del total. Dos casos probados: (1) el **pagaré `#UMV060770008`** — su movimiento (`Compra cheque`) trae el monto pero **no la cantidad**, y la posición real vale **US$5.359**; (2) los **ajustes de ratio de CEDEAR** (SPY) no generan movimiento. **Solución: dos fuentes complementarias** — movimientos = histórico (costos, aportes, rendimiento); **tenencia del broker = foto actual** (cantidades y precios). Su diferencia **es** la reconciliación contra el custodio. Implementado en `tenencias.py` + **M10** (`cartera_tenencia`, `cartera_tenencia_meta`) + `Posicion.cant_broker` (manda sobre lo derivado; si el ticker **no** está en la tenencia se conserva lo derivado, porque hay tenencias fuera del broker: **el Bitcoin**).
>
> **Números con las dos fuentes:** patrimonio **US$15.757** (posiciones US$15.685 incl. BTC + efectivo US$72) vs tenencia del broker US$15.575 (sin BTC). Aportado US$11.338 → **+US$4.419 (+39,0%) en dólares · +$10.783.811 (+81,9%) en pesos**. Suite **218 passed, 1 skipped** + recon verde.
>
> 📌 **Para Franco:** la reconciliación detectó que **ASML** está marcado `Activo en cartera = NO` en `Config` del Excel pero el broker informa 15 unidades — conviene corregirlo en la planilla.
>
> ✅ **Bitcoin cerrado (3ª objeción de Franco, también correcta):** su posición vale US$203,04 y la app mostraba US$192. **La causa era la CANTIDAD, no el precio**: el Excel solo tenía el saldo inicial (0,003) y la tenencia real es **0,00316847** (Binance). Con la cantidad correcta: US$202,91 (13 centavos de diferencia por el movimiento del precio). Se agregaron **tenencias manuales** (`set_tenencia_manual`, fecha reservada `"manual"`) para activos fuera del custodio: mandan sobre los movimientos y no se pisan al reimportar la foto del broker.
>
> **Precios: precedencia override → broker → cripto/yahoo → mercado vivo/caché.** Con tenencia importada se usan los precios del broker, así los totales coinciden con lo que Franco ve.
>
> 🔍 **Los US$86 de diferencia — explicados:** las fórmulas del export de tenencias calculan con la columna **C (Cantidad)**, que viene **vacía**, no con la **E (Disponibles)**. El "Total" del propio archivo daría 0 → los 15.489 que ve Franco vienen de la **pantalla del broker** (precios en vivo), no del archivo. Nuestra suma es correcta para los precios congelados del export. Decisión de Franco: ruido de precios aceptable (0,55%).
>
> **Números finales del día:** patrimonio **US$15.778** (broker US$15.575 + BTC US$203) · aportado US$11.338 → **+US$4.440 (+39,2%) en dólares · +$10.815.664 (+82,2%) en pesos**. Suite **221 passed, 1 skipped** + recon verde.
>
> 💡 **En MEJORAS:** traer la tenencia de cripto directo de **Binance** (read-only — el agente no opera) y las **amortizaciones parciales** de bonos vivos (hoy suman como flujo sin reducir tenencia; con vencimiento total ya funciona).
>
> ⏱️ **Horizonte temporal + TIR (2026-07-23).** El acumulado no dice nada sin el tiempo, y anualizarlo dividiendo por los años sería incorrecto: hubo **24 aportes** entre 12/2024 y 07/2026, cada uno invertido un plazo distinto. Se implementó `flujos_de_capital()` + `tir()` (XIRR por **bisección** — Newton diverge con flujos irregulares), validada contra casos conocidos. **Período: 05/12/2024 → 24/07/2026 = 596 días (19,6 meses).** Acumulado +39,2% USD → **TIR 26,0% anual en dólares · 53,6% anual en pesos** (el CAGR simple daría 22,4%, subestimando). Suite **225 passed, 1 skipped**.
>
> 📌 **Nota para el gate:** `tests/test_cartera_recon.py` llama a `posiciones()` **sin** instrumentos a propósito — compara el plano que calcula el Excel (cantidades brutas). El cierre de vencidos es una capa deliberada por encima de la planilla; pasar instrumentos ahí haría fallar el recon por la mejora, no por un error.
>
> **Próximo: paso 5 — recon en USD modo "MEP actual"** (metodología del Excel) para cerrar la Fase 3a. Después: **merge a `main` + `fly deploy`** para verla online (hoy el trabajo vive en `fase-3a/cartera-nativa`, que Fly no despliega). Pendiente de 3b: amortizaciones **parciales** (bonos vivos que amortizan en cuotas, ej. AE38 a futuro) — hoy se cuentan como flujo sin reducir tenencia.

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

La carpeta del repo vive en OneDrive y dio problemas reales: locks huérfanos (`HEAD.lock`, `index.lock`), archivos commiteados truncados por sync parcial y un índice corrupto (recuperado sin pérdida). **Protocolo para el Claude que trabaje acá:** editar archivos vía shell (no solo herramientas de archivo), y tras cada commit verificar `git status` limpio + `git fsck` + conteo de líneas de los archivos tocados en HEAD. Si git no ve un cambio, `touch` + `git update-index --really-refresh`. Mitigación aplicada (2026-07-10): Franco activó "mantener siempre en este dispositivo" para la carpeta, eliminando los placeholders cloud-only. El protocolo de verificación sigue vigente igual.

> **Nota (2026-07-23):** en el sandbox de Cowork, `rm` sobre el mount OneDrive da "Operation not permitted" — **solo `mv` funciona**. Por eso, cuando git deja locks/temporales huérfanos (`*.lock`, `.git/objects/**/tmp_obj_*`) que bloquearían el push, el Claude los **mueve a la carpeta `Borrar/` de la raíz** (gitignoreada) en vez de borrarlos, y **avisa a Franco en el chat** para que borre `Borrar/` a mano antes del push. En el Windows de Franco el `rm` anda normal; el bloqueo es solo del sandbox. Tras cada commit: barrer locks/tmp a `Borrar/` → confirmar que no queda ningún `*.lock` activo → avisar.

## 📌 Recordatorios permanentes

- No commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`).
- Una fase a la vez, cerrada y desplegable.
- Cerrar sesión = actualizar bitácora + este archivo.
