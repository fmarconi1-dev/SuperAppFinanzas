# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".

<!-- ultima_actualizacion: 2026-07-30 · autor: Claude (Opus 5) · handoff: **FASE 3b COMPLETA** (puntos 2, 3 y 4; el 1 quedó en MEJORAS con motivo). Puntos 3 y 4 SIN DESPLEGAR. Próximo: desplegar y arrancar Fase 4 — ver docs/PROMPT-INICIO-FASE-4.md -->

## 🧭 Dónde estamos

- **Fase actual:** **Fase 3a — Cartera nativa, COMPLETA Y EN PRODUCCIÓN** (2026-07-30, release **v11** verificada por Franco usando la app). Diseño en `docs/decisiones/ADR-0003-cartera-nativa.md` + `ADR-0004` (fuente MEP).
- **Situación:** Superapp en producción con login único, dos lugares (Finanzas + Inversiones/Scoring), **espacios compartidos** (grupo familiar D2) y **Cartera nativa** funcionando. **249 tests en verde** (3 skipped: el gate de recon necesita `CARTERA_XLSX`). Incidente de migración del 17/7 resuelto (ver Nota post-incidente). radar-financiero sigue vivo como respaldo.
- **Hosting:** Fly.io. App `superapp-finanzas` (gru, 1 GB, auto-stop, volumen `finanzas_data` con snapshots diarios). Sin secrets (radar tampoco tenía; SIGNUP_CODE/SESSION_SECRET opcionales, ver `.env.example`). Ver `docs/DEPLOY.md`. Uso real medido: **152 MB al arrancar, import en 2,2 s** — holgado en 1 GB.
- **Repo git:** hasta **`8f020b9`** (merge del PR #3, Fase 3b pasos 1-2), pusheado y sincronizado con `origin/main`. **Desplegado en Fly.io.**
- **Entorno local (2026-07-30):** la suite se corre desde el venv `.venv` con **Python 3.11** (la misma versión del `Dockerfile`). Franco tiene además 3.12 y 3.14 instalados; con 3.14 y sin dependencias la suite ni siquiera colecta. `py -3.11 -m venv .venv` → `.venv\Scripts\activate.bat` → `pip install -r requirements.txt`. **Verificado por Franco: 284 passed, 0 skipped**, incluido el gate de recon contra el Excel corregido.

## 🔵 Tarea en curso

| Tarea | Estado | Autor | Desde |
|---|---|---|---|
| Fase 3a — Cartera nativa (ingest + posiciones + KPIs + recon + export) | ✅ **CERRADA Y DESPLEGADA** (2026-07-30, v11) | Claude (Fable 5 → Opus 4.8) | 2026-07-19 |
| Fase 3b — Rendimientos finos | ✅ **COMPLETA** (2026-07-30). Punto 2 desplegado; **3 y 4 sin desplegar** | Claude (Opus 5) | 2026-07-30 |
| Fase 4 — Mejoras del Lugar A (Finanzas Personales) | ⬜ SIGUIENTE — arrancar con `docs/PROMPT-INICIO-FASE-4.md` | — | — |

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
> 🔄 **Consolidación al 30/7/2026 + pagaré con su tasa.** Franco subió movimientos al 30/7 y tenencia al 29/7. **Dedupe verificado en producción real: de 586 movimientos, 580 ya estaban y entraron solo los 6 nuevos.**
>
> ⚠️ **ORDEN DE IMPORT (fácil de romper):** importar **solo** del export del broker **pierde los saldos iniciales sintéticos**, que existen únicamente en el Excel → el aportado caía de US$11.534 a US$4.941 y las posiciones daban negativas. **Siempre: Excel primero (base histórica), exports del broker encima** (el dedupe se encarga).
>
> 💵 **El pagaré, resuelto** (era el 35% de la cartera y no computaba costo): `"Compra cheque"` ahora mapea a COMPRA, `_extraer_ticker` reconoce el formato `"Boleto / … / #UMV060770008 / U$S"`, `_es_instrumento` acepta tickers con `#` (no están en Config) y `_base_ppc` toma la cantidad de la tenencia cuando el movimiento no la trae. Ahora computa costo: **invertido US$5.032,12**.
>
> ⚠️ **Corrección de Franco sobre la valuación del pagaré (importante para quien siga).** Se había implementado valuación **devengada** asumiendo que el precio del broker inflaba el valor (daba ~200% anualizado desde la compra). **Franco explicó la mecánica real: los pagarés se compran a DESCUENTO sobre el nominal.** VN US$5.500 comprado en US$5.032,12 → ganancia total US$467,88 = **9,3%, que a un año es el 10% anual**. El precio del broker es el valor presente, que **converge al nominal** al acercarse el vencimiento: no está inflado, y los ~US$400 de hoy son ganancia real devengada. **El precio del broker es el default correcto.** M11 (`tasa_anual_usd` + `precio_devengado()`) queda disponible solo para instrumentos sin mercado **cuyo precio el broker no informe**; no se aplica salvo carga explícita de tasa. Precedencia: override → devengado (si hay tasa) → **broker** → cripto/yahoo → vivo/caché.
>
> **Números definitivos al 30/7:** patrimonio $23.961.034 / **US$15.741,21** · aportado $13.462.628 / US$11.534,26 → **+$10.498.406 (+78,0%) / +US$4.206,96 (+36,5%)** · **TIR 51,4% anual en pesos, 24,4% en dólares** (602 días). Suite **229 passed, 1 skipped** + recon verde.
>
> 🧭 **Lección:** antes de "corregir" un dato del custodio, entender la mecánica del instrumento. Un pagaré comprado a descuento no devenga linealmente desde el costo.
>
> ⏱️ **Horizonte temporal + TIR (2026-07-23).** El acumulado no dice nada sin el tiempo, y anualizarlo dividiendo por los años sería incorrecto: hubo **24 aportes** entre 12/2024 y 07/2026, cada uno invertido un plazo distinto. Se implementó `flujos_de_capital()` + `tir()` (XIRR por **bisección** — Newton diverge con flujos irregulares), validada contra casos conocidos. **Período: 05/12/2024 → 24/07/2026 = 596 días (19,6 meses).** Acumulado +39,2% USD → **TIR 26,0% anual en dólares · 53,6% anual en pesos** (el CAGR simple daría 22,4%, subestimando). Suite **225 passed, 1 skipped**.
>
> 📌 **Nota para el gate:** `tests/test_cartera_recon.py` llama a `posiciones()` **sin** instrumentos a propósito — compara el plano que calcula el Excel (cantidades brutas). El cierre de vencidos es una capa deliberada por encima de la planilla; pasar instrumentos ahí haría fallar el recon por la mejora, no por un error.
>
> **Paso 5 ✅ HECHO (2026-07-30) — FASE 3a COMPLETA.** El gate ya validaba cantidades; ahora también los **costos en USD** con la metodología del Excel (**MEP único**, replicando su col K sumada en col H): **reconcilian los 49 tickers comparables**. La vista sigue usando el TC histórico por operación (más fiel); el modo MEP único existe solo para reconciliar. La divergencia de **AE38/GGAL/BITCOIN** (saldo inicial en USD que el Excel toma como ARS) quedó **congelada en un test propio** que falla si algún día la planilla se corrige — así no se puede olvidar. `tests/test_cartera_recon.py` (3 tests, los 3 verdes).
>
> **Próximo: merge a `main` + `fly deploy`** (hoy el trabajo vive en `fase-3a/cartera-nativa`, que Fly no despliega). Después **3b**: realized PnL por trade, cauciones/dividendos como rendimientos, análisis por sector y tipo de renta, y **amortizaciones parciales** de bonos vivos (hoy suman como flujo sin reducir tenencia).

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
### 🐛 Cierre del 30/7: dos bugs que Franco encontró usando la app en producción

Los detectó él, no los tests — la única forma de encontrarlos era **reimportar en el orden en que se usa la app de verdad**.

1. **`ticker_base` se guardaba al importar y quedaba mal grabado.** Franco importó los movimientos **sin** el mapa de instrumentos: las variantes en dólares no se plegaron (`SPYD` como posición aparte de `SPY`). Lo grave es que **reimportar con el Excel NO lo corregía**: el dedupe salta las filas ya existentes, así que el error se volvía permanente — 37 posiciones en vez de 22, variantes D sueltas, cantidades negativas en los tickers base y costo inflado. → **`ingest.remapear_tickers_base()`**: al cargar el Excel repara las filas ya importadas (65 en la cartera de Franco), idempotente.
2. **`view._instrumentos_de_db` no leía la columna `activo`.** Todo quedaba como vigente, así que las letras vencidas y GGALX seguían figurando "abierta" con su cantidad residual (el vencimiento entra como AMORTIZACION y no descuenta unidades). → una línea.

**Antes → después:** 37 → **22** posiciones · 9 → **0** sin precio · patrimonio US$14.794 → **US$15.742** · resultado +28,3% → **+36,5%** · TIR 19,2% → **24,4%**. 4 tests de regresión en `test_cartera_ingest.py`.

🧭 **Lección:** guardar un valor **derivado** en el momento del import es una trampa si el import puede correr sin todo el contexto — el dedupe después impide que se autocorrija. O se deriva al leer, o hay una reparación explícita.

⚠️ **Falso positivo de deploy (anotado para no perder tiempo de nuevo):** `fly deploy` avisó *"The app is not listening on the expected address"* y solo mostró `/.fly/hallpass` escuchando. **La app estaba perfecta** (`fly status` → `started`, check passing; `/_stcore/health` → `ok`). Es una carrera de tiempos: Fly mira el puerto durante el arranque y `grace_period` está en `"30s"`. Antes de tocar código: `fly status` + `fly releases` + el health endpoint. Si molesta, subir `grace_period` a `"60s"` en `fly.toml` (1 línea, sin efecto en runtime).

### ⏭️ Fase 3b — Rendimientos finos (EN CURSO desde 2026-07-30)

> **Decisión de arranque (Franco, 30/7):** los cuatro puntos comparten una misma limitación estructural — `_acumular()` de `posiciones.py` **agrega sin orden temporal**, así que el realizado de una venta se mide contra el PPC de **toda** la historia, incluidas las compras posteriores a esa venta. Se construye **la línea de tiempo una sola vez** y los cuatro puntos se apoyan ahí. *"Empezá a crear esa línea de tiempo y vamos paso a paso."*
>
> **Paso 1 ✅ HECHO (2026-07-30) — `places/inversiones/cartera/ledger.py`, módulo puro, aditivo, NO cableado.** Recorre los eventos por fecha con **PPC móvil** y emite una `Realizacion` por cierre (fecha, unidades, costo liberado al PPC vigente, resultado ARS/USD, %, días de tenencia sobre la fecha de compra promedio ponderada). Guarda las **retenciones aparte** de los dividendos (insumo del punto 3). Reglas: ante misma fecha primero la COMPRA (el export no trae hora); vender más de lo registrado **no inventa costo** (marca `descubierta`); compra sin cantidad (pagaré) acumula costo y avisa. `tests/test_cartera_ledger.py` (17 tests).
>
> **Impacto medido sobre el crudo real (585 movimientos, 46 ventas):** el realizado en pesos cambia en **9 tickers**; total $3.297.014 → **$3.145.965 (−$151.050, −4,6%)**. **Patrimonio, TIR y el gate de recon son inmunes** (el método del patrimonio no suma operación por operación). Dos mecanismos:
> 1. **`SPY` (−$688.510, el mayor):** el ajuste de ratio está en el crudo como **compra de 70 unidades a costo cero fechada el 23/7/2026**, tres meses **después** de la venta del 20/4/2026. Con PPC global esas unidades gratis diluyen el promedio de toda la historia y se aplican **hacia atrás**: $1.122.268 informados contra **$433.757** reales (+31,5% en 143 días). Un evento retroactivo no puede cambiar el resultado de una venta ya hecha.
> 2. **`TGNO4` (+$39.239) y 7 más:** comprar, vender y recomprar más caro. Vendió 30 el 27/10/2025 a $3.183 compradas a $3.132 → **+$1.540 real**, pero hoy la app informa **−$37.700** porque la compra de diciembre a $4.870 sube el promedio histórico.
>
> ⚠️ **Caveat de la medición:** se corrió sobre el crudo con objetos del parser, **sin TC congelado** (las compras en USD aportan ~0 al costo en pesos) → los **absolutos** se moverán al correrlo contra la DB; la diferencia entre métodos usa los mismos insumos y no cambia. **Repetir contra la base antes de cablear.**
>
> ⚠️ **Convención de amortización (dato de dominio de Franco, adoptada):** en Argentina la amortización va **por precio, nunca por nominales** — el broker deja la cantidad quieta. Por eso `AMORTIZACION` no toca cantidad ni costo en el ledger. Cubierto por test.
>
> ⚠️ **Supuesto corregido con datos reales — AE38 NO amortizó todavía.** El 9/7/2026 se cobró **solo cupón**: US$89,65 sobre 3.604 VN = **2,4875 por cada 100**, exactamente la misma tasa por nominal que los cupones de 9/1/2025 (US$237,50 sobre 9.500), 10/7/2025 y 9/1/2026 (US$236,31). Con una amortización del 4,545% ese cupón habría sido US$85,56. Los 3.604 VN actuales salen de la **venta** de 5.896 el 6/7/2026, no de una amortización. **Primera amortización de AE38: 9/7/2027** (22 cuotas semestrales del 4,545% hasta el 9/1/2038). **AN29 es bullet** (100% al 30/11/2029, cupón 6,5% semestral). → **Ningún instrumento de la cartera amortiza parcialmente antes de julio de 2027.**
>
> **Paso 2 ✅ HECHO (2026-07-30) — el realizado por operación ya está en la app.** **`ADR-0005`** registra la decisión (PPC vigente al vender; se mantiene costo promedio ponderado, FIFO sigue en MEJORAS; el realizado por ticker deja de coincidir con el Excel a propósito). `kpis.valuar(cronologico=...)` y la sección **"Operaciones cerradas"** en la vista: 3 KPI cards + una fila por venta con PPC del día, precio, resultado ARS/USD y **días de tenencia**. Sin ledger, `valuar()` conserva el comportamiento anterior → el gate de recon no se toca.
>
> ⚠️ **Consistencia obligatoria (casi me lo como):** el realizado y el costo del remanente **van juntos**. Enchufar solo el realizado dejaba cada ticker medido mitad con un método y mitad con el otro, y rompía la identidad `costo liberado + costo remanente = total comprado` (en ASML, por $104.552). `Ledger.plano_por_ticker()` devuelve las cuatro cifras juntas y hay **test de la identidad**.
>
> **Verificación end-to-end con datos reales** (585 movimientos con MEP congelado + foto del 30/7): **valor de cartera idéntico** ($23.900.213) → **patrimonio, aportado, resultado total y TIR intactos**. Costo de la tenencia $21.070.343 → $20.640.875; no realizado $2.829.869 → **$3.259.338**; realizado $6.063.678 → $5.630.023; rendimiento sobre costo 13,4% → **15,8%**. Cambian 8 PPC (ASML 11.677→18.647, SPY 23.519→15.679, GGAL, TGNO4, VIST, NU, NVDA, MELI). **45 operaciones, 38 ganadoras**; mejor **AE38 +97,7% en 578 días**, peor **AGRO −31,8% en 130 días**.
>
> ✅ **ASML — RESUELTO el mismo día.** La compra del 16/5/2025 figuraba como 9 unidades a **$60,10** ($543,05): **el broker le sacó dos ceros**, fueron a **$6.010**. Lo detectó sola la guarda nueva `Realizacion.sospechosa` (>1.000%). Corregido **en la app y en el Excel**: la venta del 21/1/2026 pasa de un absurdo +22.754% a **+$69.802,85 (+128,5% ARS / +80,2% USD en 250 días)** — es, legítimamente, la mejor operación de la cartera. Realizado total $5.630.023 → **$5.576.261**; operaciones a revisar 4 → **3**.
>
> **Cómo se corrige un movimiento (importa para la próxima vez).** `parser.clave_dedupe()`/`hash_dedupe()` centralizan la regla de identidad, e `ingest.corregir_movimiento()` **recalcula el hash** al corregir → después de corregir en la app y poner los mismos valores en el Excel, reimportar **dedupea**. Si se corrigiera **solo** el Excel, la compra entraría de nuevo y quedarían **18 unidades de ASML donde hay 9**: las dos rutas están congeladas en tests (`..._deja_el_hash_que_produciria_el_excel_corregido` y `..._el_excel_arreglado_DUPLICA`). En la vista: expander "Corregir un movimiento mal informado por el broker".
>
> **Excel de Franco:** `Inversiones.xlsx` → `Movimientos Crudo` E460/G460 corregidos, con respaldo en *"Inversiones - respaldo pre-fix-ASML 2026-07-30.xlsx"*. **Edición quirúrgica sobre el XML del .xlsx** — un round-trip de openpyxl le borra formato condicional y extensiones a un libro de 16 hojas. Verificado: 16 hojas, 586 filas, resto intacto.
>
> 📌 **PARA FRANCO — segundo candidato, NO tocado: `TTM26`.** Un barrido de precios anómalos (cada precio contra la mediana de su ticker) marcó 12 filas; 11 son legítimas (compras en USD, donde el precio está en dólares). La que queda: la compra del **4/2/2026 de 17.395 nominales por $17,78** (precio 0,00102) cuando ese mismo día compraste a 1,458. Si el precio correcto fuera ~1,40, el costo del bono pasa de $633.940 a $658.275 y su resultado de **+13,3% a +9,1%**. **Chequealo con el broker**: no lo toqué porque el +13,3% es el número que validaste a mano el 23/7.
>
> ✅ **DESPLEGADO (2026-07-30).** Merge del PR #3 a `main` (`8f020b9`) y `fly deploy`. Verificación previa hecha por Franco en su venv de Python 3.11: **284 passed, 0 skipped**, con el gate de recon en **3/3 contra el Excel ya corregido** — el `Resumen Cartera` de la planilla computa ASML en **$334.016,68** (= 54.305 + 279.711,68), el mismo número que la app. La corrección quedó validada por el oráculo, no solo por los tests propios.
>
> **Punto 3 ✅ HECHO (2026-07-30) — `rendimientos.py` + sección "La plata quieta".** Las cauciones **no son instrumentos** (pseudo-ticker `CC`), así que su rendimiento estaba dentro del efectivo pero sin nombre. Relevado sobre los datos reales (no supuesto): **colocación y vencimiento comparten la fecha de concertación** y el plazo sale de la diferencia entre las **liquidaciones**. **101 pares, cero huérfanas.** Dividendos netos de retención por instrumento + cuenta remunerada.
>
> ⚠️ **La tasa va ponderada por capital y tiempo**, no es el promedio de las TNA: promediarlas le da el mismo peso a una caución de $20.000 por un día que a una de $2,7M por cinco. Test sintético donde el promedio simple da **48%** y la tasa real **5,3%**.
>
> **Identidad independiente (lección de 3a), en test y con datos reales:** el interés apareado es idéntico al **neto de todos los movimientos de caución** — cálculo que no depende del apareo. Da **$33.365,31** por las dos vías.
>
> **Números (dic-2024 → jul-2026):** 101 cauciones · interés **$33.365,31** · **TNA ponderada 25,60%** (2024: 24,48% · 2025: 29,31% · 2026: 21,38%) · dividendos 62 cobros, **$89.086,78** brutos − **$5.190,66** de retención = **$83.896,12** netos · remunerada **$3.300,98** · **total caja $120.562,41**. Retenciones muy distintas por papel: GGAL 10,9%, TGNO4/BMA 7,1%, CEDEARs en dólares 0%. Las TNA más altas de la serie (hasta 105%) son todas de **octubre 2025** — el apretón pre-electoral quedó registrado solo.
>
> **⚠️ Es atribución, no plata nueva:** ya estaba todo dentro del patrimonio. La vista lo dice explícitamente.
>
> **Punto 4 ✅ HECHO (2026-07-30) — `analisis.py` + sección "Cómo está repartida". FASE 3b COMPLETA.** Decisión de Franco: tipo de renta como corte principal (cobertura total) y sector como capa secundaria solo donde el dato exista. El snapshot del scoring ya trae **100 empresas**, no las ~20 que decía este archivo.
>
> **Dos decisiones para no repetir errores viejos:** el porcentaje se mide **contra el patrimonio con el efectivo adentro** (si no, la caja desaparece del cuadro), y se agrega **solo el resultado no realizado** — sumar el total por grupo repetiría la trampa de 3a.
>
> ⚠️ **Dos cosas que no cerraban en la primera corrida, encontradas mirando los números reales:** (1) el **pagaré, el 34% de la cartera**, caía en "Sin dato" porque su ticker empieza con `#` y nunca estuvo en `Config` → se reconoce por el ticker y es **renta fija** (se compra a descuento); (2) el corte por sector se diluía a un **"Sin dato" del 74,6%** porque entraban bonos, pagaré, cripto y efectivo — a esos **no les falta el sector: no tienen** → `por_sector` mira **solo la renta variable** y la cobertura pasó de un 25% engañoso a un **65,7% real**.
>
> **Foto de la cartera al 30/7 (patrimonio $23.962.038):** renta fija **60,1%** ($14.406.991, 3 posiciones) · renta variable **38,3%** ($9.183.750, 18) · cripto 1,3% · efectivo 0,3%.
>
> ✅ **SECTOR E INDUSTRIA AUTOMÁTICOS (2026-07-30, pedido de Franco).** `core/market_data/sectores.py` + **M12** (`cartera_sectores`): cascada **override → scoring → Yahoo `v1/finance/search`** (sin autenticación; ⚠️ `quoteSummary` exige un *crumb* con cookie y devuelve `Unauthorized` — probado). `fetch` inyectable, caché en DB, **caché negativa** (si no, un ticker desconocido dispara una búsqueda en cada carga), coincidencia **exacta** de símbolo (buscando `URA` aparece `UROY`), sufijo **`.BA`** para las argentinas, y los pagarés no se consultan. **Cobertura 100% de la renta variable, cero "Sin dato"** (antes 65,7%). `tests/test_market_data_sectores.py` (18 tests, sin red). Suite **342 passed, 3 skipped**.
>
> **Los ETF no tienen sector porque son una canasta** → etiqueta desde el nombre del fondo: **ETF · Oro / Uranio / Cobre / S&P 500**.
>
> 📌 **Decisión de Franco:** Yahoo clasifica **TGNO4** como **Energy · Oil & Gas Midstream** (GICS mete el transporte de gas en Energía), no Utilities. Eligió que **mande Yahoo** para quedar comparable contra el estándar; el **override manual gana siempre** y tiene UI.
>
> **Sector (sobre renta variable):** ETF · S&P 500 22,1% · Technology 21,5% · Energy 12,3% · Financial Services 11,3% · Consumer Cyclical 10,7% · Communication Services 9,3% · ETF Uranio/Oro/Cobre 7,5% · Healthcare+Utilities+Industrials 5,3%. **Con el nivel de industria aparece que el 21,5% de Technology es 16% en semiconductores** (NVDA + TSM + ASML).
>
> **Próximo paso concreto:** **desplegar los puntos 3 y 4** (merge del PR + `fly deploy`) y arrancar la **Fase 4** con `docs/PROMPT-INICIO-FASE-4.md`. El punto 1 de la 3b (amortizaciones parciales) queda en `MEJORAS.md` con motivo: la primera amortización real del AE38 es el **9/7/2027** y todavía no se puede saber si el precio del broker vendrá por 100 de nominal original o residual.

**Los cuatro puntos, en orden:**

- ✅ **Realizado por operación** (punto 2) — hecho: motor cronológico + ADR-0005 + sección "Operaciones cerradas".
- **Amortizaciones parciales** de bonos vivos: un evento más de la misma línea de tiempo. Importante pero **no urgente** (primer evento real: 9/7/2027). Falta resolver, cuando llegue, si el precio del broker viene por 100 de nominal **original** o **residual** — se decide con la foto de la tenencia del día que amortice, no antes.
- ✅ **Cauciones y dividendos como rendimientos** con su propia tasa — hecho: `rendimientos.py` + sección "La plata quieta". **Falta desplegarlo.**
- 🔵 **Análisis por sector** (reusar el sector del snapshot de scoring) y por **tipo de renta** — **el que sigue**. Ojo con la cobertura: la cartera es casi toda CEDEARs y el scoring cubre ~20 tickers; el corte por tipo de renta sale de `categoria_activo` y está disponible hoy.
- Renta fija (`Renta fija ARG.xlsx`) NO va en cartera: futura sección de análisis de mercado (está en MEJORAS).
- Pendiente de Franco (opcional): feedback sobre el formato del **export a Excel** de la cartera.

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
