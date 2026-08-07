# Bitácora — B.1 — Dashboard de Cartera

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: 2026-07-23 -->

## Estado del módulo
**Fase de implementación:** Fase 3a / 6
**Situación:** ✅ **Fase 3a COMPLETA** — los 5 pasos cerrados (parser · M9+ingest · market_data · vista con upload · **recon USD modo MEP actual**). La cartera vive en la app y reconcilia contra el Excel en cantidades y en costos. Próximo: merge a `main` + deploy, y luego 3b

## Registro

_(sin entradas todavía — este módulo aún no se implementó; ver `/ROADMAP.md`)_

## 2026-07-19 — Estudio de los Excel + diseño de la cartera nativa (sin código aún)
- **Autor:** Claude (Fable 5), con Franco.
- **Qué:** se estudió `Inversiones.xlsx` completo (LEEME, Cartera, Resumen Cartera, General, Config, Apoyo, Movimientos Crudo/Procesado) y se decidió con Franco el giro a **cartera nativa** (DB propia, mecánica tipo Transacciones) en vez de Excel-in-the-loop → `docs/decisiones/ADR-0003-cartera-nativa.md`. Decisiones: TC histórico por operación (BCRA), costo promedio ponderado, precios automáticos vía gauss314/skills con caché+override, alcance 3a = import + carga recurrente + posiciones + KPIs.
- **Hallazgos:** (1) el broker cambió el formato del export en mayo 2026 y el Excel no procesa 31 movimientos desde el 20/5 — el parser nativo debe soportar ambos formatos; (2) dos `#REF!` en Resumen Cartera por una fila huérfana (reparación indicada: eliminar fila 32 de Movimientos Procesado); (3) columna Moneda del formato viejo poco confiable.
- **Estado:** diseño cerrado y spec del parser documentada en `ESTADO.md`. Próximo: construir el parser con tests.

## 2026-07-23 — Parser del broker construido y testeado (paso 1/5 de la Fase 3a)
- **Autor:** Claude (Opus 4.8), con Franco.
- **Qué:** se rescató el borrador `parser.py` (estaba sin commitear y no compilaba) y se completó. **3 arreglos:** (1) `SyntaxError` en la línea 196 — un carácter árabe (tatweel, U+0640) incrustado en el literal numérico, probable artefacto de sync OneDrive; (2) el espejo de dividendos/renta ahora se aparea por `(fecha, ticker_base)` contra la línea USD de ingreso, **tolerante a la categoría**, para cubrir el **formato nuevo** (donde la pata base ARS se infiere RETENCION y la pata USD DIVIDENDO/RENTA, así que exigir misma categoría las dejaba sin aparear y contaba el espejo como retención real); (3) la detección del saldo inicial sintético buscaba `"(saldo inicial"` con paréntesis y se comía la fila del `"Saldo inicial sintetico (cubre AE38 + BITCOIN)"`. Se agregó `__init__.py` al paquete y `tests/test_cartera_parser.py` (**43 tests**: detección de formato, 12 categorías viejo + inferencia nuevo, moneda inferida —Cedear base/D, bono hard-dollar, ARS/100, BITCOIN, etiqueta mal puesta—, precio /100, saldos iniciales, espejo viejo **y** nuevo, GGAL ARS de una línea no-espejo, dedupe con contador, loader CSV).
- **Verificado contra el Excel:** el mapeo de columnas de **ambos** formatos calza con el crudo real (nuevo = filas 2-32, arranca en Concertación; viejo = 33-568, con Operación); `MAPA_OPERACION == Config!A5:B16` (12 categorías); la reclasificación Vencimiento→AMORTIZACION nunca dispara (97/97 vencimientos son cauciones).
- **Hallazgo nuevo en el Excel:** la columna **Moneda** de `Movimientos Procesado` (col F) está **desalineada ~30 filas** (lee la moneda de otra operación) — explica en parte la etiqueta de moneda poco confiable. **No afecta cantidades** (Resumen usa Δ Cantidad); toca costos de compras solo donde la moneda mal leída se voltea (raro: las compras son casi todas ARS). El parser **infiere** la moneda → inmune. A tratar como divergencia documentada en el recon (paso 5). Fila 32 de `Movimientos Procesado`: **confirmado que ya fue borrada** — no queda ningún `#REF!` en el libro.
- **Decisión menor (llamada de Franco):** el hash de dedupe usa `fecha+categoría+descripción+monto+cantidad` (categoría es estable entre formatos; cantidad desempata) en vez de `+operación`.
- **Estado:** paso 1/5 cerrado. Suite completa **157 en verde**. Commit local en `fase-3a/cartera-nativa` (pendiente de push por Franco vía GitHub Desktop). **Próximo:** paso 2 — modelo de datos (migración **M9**: tabla `mov_cartera` con TC MEP histórico congelado por fila, scope por usuario, mapping tipo `Config`, caché de precios).

## 2026-07-23 — Excel-oráculo actualizado + reconciliado 20/20 + modelo de datos M9 (paso 2)
- **Autor:** Claude (Opus 4.8), con Franco.
- **Excel-oráculo al día:** Franco pasó el export completo de inviu (movimientos "Todos", formato viejo con Operación, 580 filas hasta 14/7) + la Tenencia del broker al 24/7. Se reconstruyó `Inversiones.xlsx` (respaldo del original guardado): crudo = export + 4 saldos sintéticos + **ajuste de ratio de SPY (+70)** (confirmado por Franco: reajuste de conversión del CEDEAR); fórmulas de `Movimientos Procesado` regeneradas 1:1 con la **columna Moneda alineada** (arregla el desfase ~30 filas); Config con tickers nuevos (SATL, UNH, CEG); Resumen corregido (salteaba NBIS, duplicaba GGALX); Apoyo MEP=1519,725 y BTC=65877 (cierre 22/7). Recalculado con LibreOffice: **las 20 posiciones calzan EXACTO** contra la Tenencia del broker. Los `#NAME?` de Apoyo son del add-in `_xll.TiposCambioBD` (preexistentes; andan en Excel de Franco).
- **Reconciliación clave:** el parser (nuestro motor) procesó el export real y reprodujo 19/20 posiciones solo con los movimientos + saldos sintéticos; la única brecha (SPY) es el ajuste de ratio externo. Es la validación más fuerte posible del parser: contra la tenencia real del broker.
- **M9 (paso 2, esquema):** migración aditiva en `core/db.py` con 3 tablas **scope por user_id** (la cartera es personal, no workspace): `cartera_instrumentos` (mapa tipo Config), `cartera_movimientos` (salida del parser; `tc_mep` NULL hasta paso 3; `UNIQUE(user_id, hash_dedupe)` para carga idempotente) y `cartera_precios_cache`. `tests/test_cartera_db.py` (8 tests: creación, idempotencia de init_db, dedupe en reimport, aislamiento por usuario, PKs). Suite **165 en verde**.
- **Estado:** parser (paso 1) + esquema M9 (paso 2) cerrados. **Próximo:** ingest (parsear el export → cargar `cartera_movimientos` + poblar `cartera_instrumentos` desde Config) con `tests/test_cartera_recon.py` contra el Excel, y luego `core/market_data` (paso 3) para congelar el MEP histórico.

## 2026-07-23 — Ingest + posiciones + gate de reconciliación
- **Autor:** Claude (Opus 4.8), con Franco.
- **Qué:** se cerró la carga de la cartera nativa.
  - `places/inversiones/cartera/ingest.py`: `instrumentos_desde_config` (mapa para el parser), `cargar_instrumentos_en_db` (UPSERT de Config→`cartera_instrumentos`) e `importar_movimientos` (INSERT OR IGNORE con dedupe por `hash_dedupe`; re-importar el mismo export no duplica; devuelve (insertados, saltados)).
  - `places/inversiones/cartera/posiciones.py`: cálculo de posiciones portando la lógica de `Resumen Cartera` (Cant Comprada/Vendida/Actual por `ticker_base`, sobre COMPRA/VENTA con es_instrumento). Puro; `posiciones()` sobre objetos del parser, `posiciones_desde_db()` sobre la tabla.
  - `tests/test_cartera_ingest.py` (5 tests, sintéticos, CI): dedupe en reimport, aislamiento por usuario, posiciones, carga de instrumentos.
  - `tests/test_cartera_recon.py` (**gate**): parte del crudo del Excel → parser → posiciones y exige que cada ticker calce con `Resumen Cartera`. **Verificado: reconcilia exacto contra el Excel recalculado.** Se saltea con mensaje claro si el Excel no está o no fue recalculado (sin valores cacheados) → no rompe CI; corre local con `CARTERA_XLSX`.
- **Estado:** suite **170 passed, 1 skipped** (el recon, que corre local). Ingest cerrado. **Próximo:** `core/market_data` (paso 3) — MEP histórico (BCRA) para congelar `tc_mep` por fila + precios ARG (data912/byma) y CEDEARs/BTC (yahoo), con caché + override; después posiciones+KPIs+vista (paso 4).

## 2026-07-23 — `core/market_data`: MEP histórico + precios (paso 3)
- **Autor:** Claude (Opus 4.8), con Franco.
- **⚠️ Hallazgo que corrigió una decisión cerrada:** el ADR-0003 fijó el TC histórico "vía BCRA", pero **el BCRA no publica el MEP** — su API sirve el mayorista A3500 (1.480,86 vs MEP 1.521,9 al 22/7; ~3% de brecha, subvaluaría las compras en USD). Se relevaron alternativas y **Franco eligió `argentinadatos` (MEP bolsa)** → **`docs/decisiones/ADR-0004-fuente-mep-historico.md`**. Verificado antes de decidir: cubre **419/419 días hábiles** del historial, sin faltantes.
- **Qué se construyó** (`core/market_data/`, con `fetch` inyectable → tests sin red):
  - `mep.py`: descarga y parseo de la serie (usa precio de **venta**), `mep_para_fecha` con **último hábil anterior** (finde/feriado), caché en `cartera_precios_cache` (ticker `MEP`), `serie_mep_con_fallback` (proveedor → caché si cae) y `set_override_mep`.
  - `precios.py`: `precios_arg` (data912: acciones/CEDEARs/bonos; cae al mid si no hay cierre; un panel caído no tumba al resto), `precio_yahoo` (BTC/exterior), caché + `set_override_precio` y `resolver_precio` con precedencia **override → caché → proveedor**. **Normaliza bonos /100** (data912 sirve AE38 = 127.360 donde el broker muestra 1.262,6).
  - `ingest.congelar_tc_mep`: graba el MEP de la fecha de cada operación en `cartera_movimientos.tc_mep`; **idempotente** (solo filas NULL) y no pisa lo ya congelado.
- **Verificación real (humo contra APIs vivas):** serie de 2.826 puntos; **585 movimientos del Excel importados y TC congelado en las 585 filas, cero fechas sin dato**; 1.204 símbolos ARG vivos; AE38 resuelto en 1.273,6 (coherente con 1.262,6 del broker) y BTC vía yahoo.
- `tests/test_market_data.py` (**18 tests**, sin red): parseo, último hábil, caché, fallback con fuente caída, override que gana, mid de puntas, panel caído, normalización /100, precedencia, congelado idempotente y reporte de fechas sin dato. Suite **188 passed, 1 skipped**.
- **Estado:** paso 3 cerrado. **Próximo:** paso 4 — posiciones + KPIs + **vista de Cartera** (con `ui-ux-web-moderno`, obligatoria en UI), y paso 5: recon en USD modo "MEP actual" (metodología del Excel) además del histórico.

## 2026-07-23 — Vista de Cartera: la cartera ya vive en la app (paso 4)
- **Autor:** Claude (Opus 4.8), con Franco. Skill `ui-ux-web-moderno` aplicada (obligatoria en UI).
- **Lógica:** `posiciones.py` extendido con **costo promedio ponderado** (`ppc_ars`, `costo_ars_posicion`) y **costo USD con TC histórico** (`costo_usd_hist` usa el `tc_mep` congelado de cada compra → la vista fiel que el Excel no tiene). `kpis.py`: `valuar()` (precio inyectable, omite posiciones cerradas, tolera falta de precio) y `kpis_de()` (totales; **excluye del costo lo que no tiene precio** para no comparar valor parcial contra costo total). `tests/test_cartera_kpis.py` (12).
- **Vista** (`view.py`, cableada en la pestaña Cartera reemplazando el cartel de "Fase 3"): KPI cards en HTML propio con los tokens **Cosmic Slate** (`--cs-*`, sin hex ad-hoc), cifras **tabular-nums** en fuente mono, ganancia/pérdida con **signo + flecha + color** (nunca color solo), tabla con formato es-AR vía `column_config`, **upload del export del broker** (dedupe + congelado del TC en el mismo flujo), carga del mapa de instrumentos desde la hoja Config, botón de refresco y caché de 5 min para no pegarle a las APIs en cada rerun. Estados **empty** (con instrucción de dónde sacar el export), **error** (archivo no reconocido) y aviso de posiciones sin precio. Scope por usuario (`CARTERA_USER_IDS`, default solo Franco — ADR-0003).
- **Verificación end-to-end con datos reales** (no solo tests): flujo completo Excel → parser → DB → TC congelado → precios vivos → KPIs. Resultado: **valor $15.490.098 / US$10.101 · +19,8% · 23 posiciones valuadas**. BTC resuelto por yahoo (0,003 × $98.117.440 = $294.352).
- **⚠️ Hallazgo (para 3b):** 6 letras/bonos en pesos ya vencidos (S15G5, T15D5, S16E6, TTM26, S17A6, T2X5) quedan con **cantidad residual** porque el vencimiento se registra como `AMORTIZACION` y solo `VENTA` resta cantidad. El Excel arrastra lo mismo (por eso el recon pasa). No cotizan → sin precio, no ensucian los totales. Se resuelve al tratar amortizaciones en **3b**. Ídem `GGALX` (ticker viejo del canje, cantidad −100 compensada por el saldo sintético de GGAL).
- **Estado:** suite **200 passed, 1 skipped**. **Próximo:** paso 5 (recon USD en modo "MEP actual" para cerrar 3a) y luego merge a `main` + `fly deploy` para verla online.

## 2026-07-23 — Rendimiento completo ARS/USD + cierre de vencidos (adelanta 3b)
- **Autor:** Claude (Opus 4.8). **Pedido de Franco:** las amortizaciones son rendimiento y no se estaban computando; además, medirlo en dólares con el MEP del día de compra y de cobro. Decisión suya de adelantar esta parte de la 3b.
- **Evidencia que motivó el cambio:** $6.345.528 en flujos cobrados (amortizaciones $6,29M + rentas + dividendos) quedaban fuera del cálculo, y 6 letras vencidas figuraban con cantidad residual.
- **Cierre de posiciones vencidas sin heurísticas:** se usa la propia señal del Excel, `Config!L "Activo en cartera" = NO` (las 6 letras + GGALX). `Instrumento.activo` se puebla en el ingest y `Posicion.cant_actual` devuelve 0 si el instrumento venció (el broker manda `AMORTIZACION` con cantidad 0, por eso nunca se descontaba).
- **Rendimiento completo** (regla del LEEME: realizado en ventas + no realizado + dividendos + amortizaciones): `posiciones.py` acumula ventas y flujos en **ARS y USD al TC de cada fecha**; `kpis.py` expone `resultado_total_*` y `rendimiento_total_usd_pct`.
- **⚠️ Bug encontrado y corregido en el camino:** la amortización devuelve **capital + interés**; al sumarla como rendimiento sin descontar el capital, las letras daban ~100-113% de rendimiento. Se agregó `costo_amortizado_*` (PPC × unidades vencidas) y se resta del resultado. Tras el fix, cada letra reproduce **exactamente** el cálculo manual independiente (S15G5 +3,8% ARS / **−3,6% USD**; T15D5 +5,5% / +1,5%; TTM26 +13,3% / +18,0%).
- **Resultado con datos reales:** invertido $33.203.225 (US$25.219) → **resultado $10.398.493 (US$4.273) = +31,3% en pesos, +16,9% en dólares**. Ya no quedan posiciones sin precio.
- **Vista:** bloque "Rendimiento total" (invertido, resultado ARS, resultado USD, cobrado) + columna `Rend. US$ %` y toggle para ver posiciones cerradas.
- **Recon:** sigue **verde**. Se documentó explícitamente que `posiciones()` se llama SIN instrumentos en el gate, para comparar el mismo plano que el Excel (cantidades brutas); el cierre de vencidos es una capa deliberada por encima de la planilla.
- **Estado:** suite **206 passed, 1 skipped** (+ recon verde). `tests/test_cartera_kpis.py` (18).

## 2026-07-23 — CORRECCIÓN: el rendimiento estaba mal calculado (lo detectó Franco)
- **Autor:** Claude (Opus 4.8). **Franco objetó** el "invertido US$25.219": *"no hay 25 mil dólares invertidos, hay unos 10/11 mil; revisá los ingresos de dinero"*. Tenía razón en todo.
- **Error 1 — denominador inflado:** lo que llamé "invertido" era la **suma de todas las compras** (capital *rotado*). Si se compra, se vende y se vuelve a comprar, cuenta la misma plata varias veces. El denominador correcto es el **capital aportado** = depósitos − retiros.
- **Error 2 — saldos iniciales en la moneda equivocada:** el bloque sintético está denominado en **USD** (AE38D 0,6158 de paridad, BTC 98.094,78, GGAL 4,49 — imposible en pesos) y las 3 compras iniciales suman **exacto** el depósito que las cubre (6.593,38), probando que comparten moneda. El export no trae columna Moneda en esas filas y se tomaban como ARS → el capital inicial quedaba subvaluado ~1.000×. Corregido en el parser (`es_saldo_inicial → USD`). Con el fix, el capital aportado da **US$11.338**, que coincide con la estimación de Franco.
- **Error 3 (el más grave) — la suma por instrumento no sirve como total:** al convertir importes en USD a pesos con el TC de cada fecha, la devaluación genera "ganancias" nominales que no son reales. Verificado **en pesos**, donde no hay efecto FX: por componentes daba **$9,92M** contra **$2,27M** por patrimonio. La suma por componentes estaba inflada ~4×.
- **Solución — método del patrimonio** (el único verificable, y el que define el propio panel `General` del Excel): `resultado = (tenencia + efectivo) − (depósitos − retiros)`, con cada aporte al MEP de su fecha. No depende de sumar operación por operación, así que no acumula errores ni doble conteo. Nuevo `saldos_efectivo()` reconstruye el cash por moneda desde los movimientos y **se verificó contra el broker**: ARS $27.530 calculado vs $26.069 informado; USD 72 vs 54,5.
- **Números corregidos:** capital aportado $13.162.628 (US$11.338) · patrimonio hoy $15.544.931 (US$10.137) → **resultado +$2.382.303 (+18,1%) en pesos, −US$1.201 (−10,6%) en dólares**. El número anterior (+31,3% / +16,9%) era incorrecto.
- La tabla por ticker se conserva como **detalle**, con la advertencia explícita en la vista de que no suma al total.
- **Estado:** suite **209 passed, 1 skipped** + recon verde. `tests/test_cartera_kpis.py` (21, incluidos 3 del método patrimonio).
- **Lección:** todo agregado de una cartera bimonetaria necesita contrastarse contra una identidad contable independiente (patrimonio vs aportes) antes de mostrarse. Sumar operación por operación parece razonable y da resultados muy equivocados.

## 2026-07-23 — Import de Tenencias del broker (M10): los movimientos NO alcanzan
- **Autor:** Claude (Opus 4.8). **Franco volvió a objetar:** *"en dólares hay 15.489,19, como dice en las tenencias"* — mi total daba US$10.047. Tenía razón otra vez.
- **Causa raíz (hallazgo estructural):** el export de **movimientos no permite reconstruir la cartera**. Dos casos probados con datos reales:
  1. **Pagaré `#UMV060770008`** — el movimiento (`Compra cheque`, 6/7/2026) trae el monto pagado (US$5.032,12) pero **no la cantidad**. La posición real (5.500 a $1.480,86 = **US$5.359**) era el **35% de la cartera** y faltaba por completo.
  2. **Ajuste de ratio de CEDEAR (SPY)** — el broker cambia la relación y ajusta el saldo **sin postear movimiento** (ya lo habíamos parcheado a mano en el Excel).
- **Solución — dos fuentes complementarias** (como cualquier sistema serio de cartera): los **movimientos** dan el histórico (costos, aportes, rendimiento) y la **tenencia del broker** la foto actual (cantidades y precios de referencia). Su diferencia **es** la reconciliación contra el custodio.
  - `tenencias.py`: parser del export (bloques por tipo de activo, cabecera con fecha y TC), `guardar_foto`/`ultima_foto` y `comparar_con_movimientos`.
  - **M10**: tablas `cartera_tenencia` + `cartera_tenencia_meta` (aditivas, scope por usuario, idempotentes por fecha).
  - `Posicion.cant_broker`: cuando hay foto, **manda sobre lo derivado de movimientos**. Si un ticker **no** está en la tenencia se conserva lo derivado — hay tenencias reales fuera del broker: **el Bitcoin** (lo advirtió Franco: *"¿no faltan los 250 dólares del BTC?"*).
  - Vista: uploader de tenencia + panel de reconciliación con las diferencias.
- **Resultado con datos reales:** patrimonio **US$15.757** (posiciones US$15.685 incl. BTC US$192 + efectivo US$72) contra tenencia del broker US$15.575 (sin BTC). Aportado US$11.338 → **+US$4.419 (+39,0%) en dólares · +$10.783.811 (+81,9%) en pesos**.
- **La reconciliación encontró un dato desactualizado en el Excel:** **ASML** figura como `Activo en cartera = NO` en `Config` pero el broker informa 15 unidades. Conviene corregirlo en la planilla.
- **Pendiente menor:** el total del broker que calculo (US$15.575,14) difiere de los US$15.489,19 que reporta Franco en ~US$86 (0,6%); ninguna combinación de efectivo/posiciones lo explica exactamente — probablemente precios de otro momento del día. No afecta las conclusiones.
- **Estado:** `tests/test_cartera_tenencias.py` (9). Suite **218 passed, 1 skipped** + recon verde.

## 2026-07-23 — Cierre del Bitcoin y precios del broker (última corrección del día)
- **Autor:** Claude (Opus 4.8), con Franco. Tercera objeción suya, también correcta: *"mi posición en bitcoin es de 203,04 dólares"*.
- **Causa: la CANTIDAD, no el precio.** El Excel solo tenía el **saldo inicial** (0,003 BTC); la tenencia real es **0,00316847** (Binance). Con la cantidad correcta y el precio de yahoo: **US$202,91** contra los US$203,04 que informa Franco — 13 centavos de diferencia por el movimiento del precio. La hipótesis previa (precio distinto, US$67.680 implícito) era errónea: el precio estaba bien, faltaba un 5,6% de cantidad.
- **Tenencias manuales** (`set_tenencia_manual` / `tenencias_manuales`, fecha reservada `"manual"`): cantidades de activos fuera del custodio. Mandan sobre lo derivado de movimientos y **no se pisan** al reimportar una foto del broker (test dedicado). En la vista: bloque "Activos fuera del broker".
- **Precios del broker prioritarios:** cuando hay tenencia importada, la valuación usa **sus** precios (precedencia: override manual → broker → cripto/yahoo → mercado en vivo/caché). Antes se usaba el feed en vivo y los totales diferían del broker por precios de otro instante.
- **Los US$86 de diferencia — explicados:** las fórmulas internas del export de tenencias calculan el monto con la columna **C (Cantidad)**, que viene **vacía**, no con la **E (Disponibles)** que trae los datos. O sea, el "Total" del propio archivo daría 0: **los 15.489 que ve Franco salen de la pantalla del broker** (precios en vivo), no del archivo. Nuestra suma (15.575) es correcta *para los precios congelados en el export*. Franco decidió: es ruido de precios aceptable (0,55%).
- **Números finales:** subtotal broker US$15.575,14 + BTC US$202,91 = **patrimonio US$15.778** · aportado US$11.337,74 → **+US$4.440 (+39,2%) en dólares · +$10.815.664 (+82,2%) en pesos**.
- **Anotado en MEJORAS:** traer la tenencia de cripto directo de **Binance** (read-only; el agente no opera) y las amortizaciones parciales de bonos vivos.
- **Estado:** `tests/test_cartera_tenencias.py` (12). Suite **221 passed, 1 skipped** + recon verde.

## 2026-07-23 — Horizonte temporal y TIR (pedido de Franco)
- **Autor:** Claude (Opus 4.8). Franco: *"¿podemos poner en cuánto tiempo fue ese rendimiento acumulado?"*.
- **Por qué no alcanza con dividir por los años:** hubo **24 aportes** repartidos entre 12/2024 y 07/2026, así que cada peso estuvo invertido un plazo distinto. La medida correcta es la **TIR** (equivalente a XIRR): la tasa anual que iguala el valor presente de todos los aportes con el patrimonio final.
- **Implementación** (`posiciones.py`): `flujos_de_capital()` (aportes/retiros con fecha y signo del inversor) y `tir()` por **bisección** — se eligió bisección sobre Newton-Raphson porque con flujos irregulares (aportes de tamaños muy distintos) Newton diverge. Devuelve `None` si no hay cambio de signo o hay un solo flujo. `KPIs` expone `dias`, `anios`, `meses`, `tir_ars` y `tir_usd`; `completar_patrimonio()` los calcula.
- **Validado contra casos conocidos:** 100→110 en 1 año = 10%; 100→121 en 2 años = 10% (capitalizado, no 10,5%); pérdida −10%. Más un test que verifica que la TIR es **mayor** que el acumulado simple cuando parte del capital entró tarde.
- **Resultado con datos reales:** período **05/12/2024 → 24/07/2026 = 596 días (19,6 meses / 1,63 años)**. Acumulado +39,2% USD / +82,2% ARS → **TIR 26,0% anual en dólares · 53,6% anual en pesos**. (El CAGR simple daría 22,4%, subestimando: no reconoce que buena parte del capital entró después.)
- Vista: el título muestra el período y se agregaron dos KPI cards con la tasa anual.
- **Estado:** `tests/test_cartera_kpis.py` (25). Suite **225 passed, 1 skipped** + recon verde.

## 2026-07-30 — Consolidación de la semana + el pagaré con su tasa real
- **Autor:** Claude (Opus 4.8), con Franco. Franco subió movimientos al 30/7 y tenencia al 29/7 (ingreso de $300.000 + compras), y aportó un dato clave: **los pagarés rinden 10% anual en dólares**.
- **Consolidación:** el dedupe funcionó como se esperaba — de 586 movimientos del export, **580 ya estaban y entraron solo los 6 nuevos** (depósito $300.000, NVDA +20 —15 en ARS y 5 en USD—, GOOGL +10, y una caución). Tenencia nueva: GOOGL 45→55, NVDA 50→70, efectivo ARS $26.068→$42.556, MEP 1519,725→1522,185.
- **⚠️ Hallazgo del flujo de import:** importar **solo** del export del broker pierde los **saldos iniciales sintéticos** (que existen únicamente en el Excel) → el capital aportado caía de US$11.534 a US$4.941 y las posiciones daban negativas (AE38 −5.896). **El orden correcto es: Excel primero (base histórica con los sintéticos) y después los exports del broker encima** (el dedupe se encarga). Documentado acá porque es fácil de romper.
- **El pagaré, tres arreglos:** (1) `"Compra cheque"`/`"Venta cheque"` mapean a COMPRA/VENTA (antes caían en OTROS); (2) `_extraer_ticker` reconoce el formato de pagarés (`"Boleto / 2529140 / CCHDIF / 1 / #UMV060770008 / U$S"` → el token con `#`); (3) `_es_instrumento` acepta los tickers que arrancan con `#` aunque no estén en Config (el Excel nunca los tuvo). Además `_base_ppc` usa la cantidad de la tenencia cuando el movimiento no la trae, así el costo se puede promediar. Resultado: el pagaré pasó de **sin costo** a invertido US$5.032,12.
- **M11 + valuación devengada (opcional, NO por defecto):** columna `tasa_anual_usd` en `cartera_instrumentos` y `precio_devengado()` (capitaliza el costo en USD a la tasa pactada y pasa a ARS por el MEP). Precedencia del resolver: override → devengado (solo si hay tasa cargada) → **broker** → cripto/yahoo → mercado vivo/caché.
- **⚠️ Mi razonamiento sobre el pagaré estaba mal — lo corrigió Franco.** Interpreté que el "precio actual" del broker inflaba el valor porque el devengamiento desde la compra daba ~200% anualizado. **Franco explicó la mecánica real:** los pagarés se compran **a descuento** sobre su valor nominal. Invirtió **US$5.032,12** por un VN de **US$5.500**: la ganancia total es **US$467,88 = 9,3%**, que a un año **es** el 10% anual. El precio del broker refleja el valor presente, que converge al nominal a medida que se acerca el vencimiento — **no está inflado**. Los ~US$400 que muestra hoy son ganancia real (devengada hasta la fecha).
- **Conclusión: el precio del broker es el correcto y quedó como default.** La valuación devengada queda disponible para el caso en que el broker **no** informe precio de un instrumento sin mercado (ahí devengar es mejor que no valuar), pero no se aplica salvo que se cargue una tasa explícitamente.
- **Números al 30/7 (definitivos):** patrimonio $23.961.034 / **US$15.741,21** · aportado $13.462.628 / US$11.534,26 → resultado **+$10.498.406 (+78,0%) / +US$4.206,96 (+36,5%)** · **TIR 51,4% anual en pesos, 24,4% en dólares** (602 días).
- **Lección:** antes de "corregir" un dato del custodio hay que entender la mecánica del instrumento. Un pagaré comprado a descuento no devenga linealmente desde el costo: su precio converge al nominal.
- **Estado:** `tests/test_cartera_kpis.py` (29). Suite **229 passed, 1 skipped** + recon verde.

## 2026-07-30 — Paso 5: recon de costos en USD → **FASE 3a COMPLETA**
- **Autor:** Claude (Opus 4.8).
- **Qué cierra el paso 5:** el gate ya verificaba **cantidades**; ahora también los **costos en dólares** con la metodología del Excel (**MEP único actual**, ADR-0003), replicando su col K de `Movimientos Procesado` (`monto_usd = monto si USD, monto/MEP si ARS`) sumada en la col H de `Resumen Cartera`.
- **Resultado: reconcilian los 49 tickers comparables** (tolerancia de 1 centavo por dólar, por redondeos del Excel). La vista de la app sigue usando el **TC histórico por operación** (más fiel); el modo MEP único existe solo para poder reconciliar contra la planilla.
- **Divergencia deliberada, congelada en un test propio** (`test_saldos_iniciales_divergen_del_excel_a_proposito`): AE38, GGAL y BITCOIN difieren porque su saldo inicial sintético está en **USD** y el Excel lo computa como ARS (subvalúa ~1.500×). El test verifica que el Excel *siga* subvaluándolo: si algún día se corrige la planilla, **falla y avisa** que hay que quitar la excepción. Así la divergencia no se puede olvidar ni tapar.
- **Estado:** `tests/test_cartera_recon.py` (3 tests). Suite **229 passed** + **3/3 del gate en verde**. **Fase 3a cerrada.**
- **Próximo:** merge a `main` + `fly deploy` (la app queda usable desde cualquier lado) y después **3b**: realized PnL por trade, cauciones/dividendos como rendimientos, análisis por sector y tipo de renta, amortizaciones parciales.

## 2026-07-30 — Export a Excel de la cartera (pedido de Franco)
- **Autor:** Claude (Opus 4.8). Skills aplicadas: **`xlsx`** (formato de salida) y `ui-ux-web-moderno` (color semántico y accesibilidad).
- **Qué:** `places/inversiones/cartera/export.py` — genera la hoja **"Resumen Cartera"** con la identidad visual de la planilla de Franco (encabezados azul `1F4E78` con texto blanco, totales en gris `F2F2F2`) y le suma lo que le faltaba:
  - **formatos de número reales** — en el Excel original *todas* las celdas del Resumen están en "General", así que los importes salían crudos;
  - **bloque de KPIs** arriba: patrimonio, capital aportado, resultado, rendimiento acumulado y **TIR anualizada**, en pesos y dólares, con color semántico (verde/rojo) y signo;
  - **agrupado por tipo de activo con subtotales** (Acciones, Bonos, Cedears, Cripto, Pagarés, Efectivo), cada uno con su % de cartera y su rendimiento;
  - **barra de datos** en la columna "% cartera" para leer el peso de un vistazo;
  - panel congelado, autofiltro, cifras monoespaciadas a la derecha;
  - **nota de metodología al pie** (regla del skill: los supuestos van donde se leen).
- **La planilla queda VIVA:** los derivados (valor, ganancia, rend %, subtotales, total) son **fórmulas de Excel**, no números calculados en Python. El **MEP vive en una celda amarilla editable (H2)** y todas las columnas en dólares la referencian: cambiarlo recalcula todo.
- **Decisión de diseño clave:** el **efectivo entra como dos filas más** (pesos y dólares en cuenta), así el **TOTAL de la tabla coincide exacto con el patrimonio de los KPIs**. Sin eso la suma daba menos y el archivo parecía tener un error.
- **Verificado con `recalc.py`:** **159 fórmulas, 0 errores**. Y con datos reales: TOTAL $23.962.038 = patrimonio, 100,0% de la cartera.
- Detalles que atraparon los tests: el BTC necesitaba **8 decimales** (mostraba 0,00), el pagaré caía en "Otros" (ahora "Pagarés", tomando el tipo de la tenencia), y con **cartera vacía** el autofiltro y la barra de datos lanzaban `TypeError` por rango inválido.
- Botón **"Descargar Excel"** en la vista. `tests/test_cartera_export.py` (10 tests). Suite **243 passed, 3 skipped** + recon verde.

## 2026-07-30 — Revisión pre-deploy + carga en UN paso con autodetección
- **Autor:** Claude (Opus 4.8), con Franco. PR #2 mergeado a `main`.
- **⚠️ Bloqueante del deploy encontrado en la revisión:** el mapa de instrumentos se pedía como **ruta del disco** (`C:\...\Inversiones.xlsx`). En el servidor esa ruta no existe → la función era inutilizable online, y sin instrumentos los tickers no se clasifican ni se sabe qué bonos cotizan por cada 100. Cambiado a `file_uploader`; verificado que `cargar_instrumentos_en_db` e `instrumentos_desde_config` leen bien un archivo **en memoria** (57 instrumentos). También se agregó `Borrar/` al `.dockerignore` (si no, ~200 archivos de basura iban a la imagen).
- **Franco pidió no tener que cargar los 4 pasos a mano.** No es posible hacerlo desde acá: la DB vive en el volumen de Fly (sin acceso desde el sandbox) y sus archivos **no pueden ir al repo** (regla dura). Lo que sí: **reducir 4 pasos a 1**.
- **`detectar_tipo()`**: reconoce cada archivo **por su estructura, no por el nombre** — Excel propio (tiene las hojas `Config` + `Movimientos Crudo`), tenencia (cabecera con "Fecha de valuación"/"TC USD MEP") y movimientos del broker (encabezados Operación/Concertación/Descripción). Tolera archivos irreconocibles y no-Excel sin explotar.
- **`_importar_todo()`**: un uploader múltiple + un botón. **La app decide el orden**, que es lo que evita el error grave: el crudo del Excel primero (trae los saldos iniciales sintéticos), después los movimientos del broker (dedupe), después la tenencia (+ caché de sus precios), y al final el congelado del TC.
- **Verificado con los archivos reales subidos en orden ALEATORIO** (tenencia, Excel, movimientos): la app los ordenó sola → 57 instrumentos · 585 históricos · 6 nuevos (580 ya estaban) · tenencia al 30/7 (21 posiciones) · TC en 591 filas, y **capital aportado US$11.534,26** — el correcto, no los US$4.941 que daría sin el Excel.
- La cantidad de BTC queda **precargada** (0,00316847): es confirmar, no tipear.
- **Estado:** suite **245 passed, 3 skipped**. `tests/test_cartera_ingest.py` (7).

## 2026-07-30 — DOS BUGS en producción, detectados por Franco al usar la app
- **Autor:** Claude (Opus 4.8), con Franco. Franco importó y la pantalla mostró **37 posiciones** (deberían ser 22), 9 sin precio, tickers `SPYD`/`GOGLD`/`NVDAD`/`YPFDD` sueltos, cantidades **negativas** (TXAR −300, GGALX −100), letras vencidas como "abierta", patrimonio US$14.794 (vs 15.742) y TIR 19,2% (vs 24,4%).
- **Bug 1 — `ticker_base` se graba al importar y quedaba mal para siempre.** En la primera corrida Franco subió por error el export de la app en vez de su `Inversiones.xlsx`, así que los movimientos entraron **sin el mapa de instrumentos** y las variantes en dólares no se plegaron (`SPYD` como posición propia en vez de sumar a `SPY`). Al reimportar con el Excel, **el dedupe salta esas filas** → el error quedaba grabado, inflando posiciones y costo. **Fix: `remapear_tickers_base()`** recalcula `ticker_base` de lo ya importado contra el mapping actual; idempotente; se ejecuta solo al cargar instrumentos. En los datos de Franco: **65 filas corregidas**.
- **Bug 2 — `_instrumentos_de_db` no leía la columna `activo`.** Todos los instrumentos quedaban como vigentes, así que las 6 letras vencidas y GGALX seguían figurando con su cantidad residual (el vencimiento entra como `AMORTIZACION` y no descuenta unidades). Una línea: pasar `activo` al construir el `Instrumento`.
- **Resultado tras los dos fixes** (reproduciendo su secuencia exacta): **22 posiciones abiertas** (antes 37), **0 sin precio** (antes 9), sin variantes D sueltas, sin negativas; valor cartera **US$15.701**, patrimonio **US$15.742**, resultado **+36,5%**, **TIR 24,4%** — los números correctos.
- **Mejora de mensajes:** la app ahora **reconoce su propio export** (`TIPO_EXPORT_APP`) y avisa *"esto es un resumen que generó la app, el que hace falta es tu Inversiones.xlsx"* en vez de "no reconocido". El aviso del faltante nombra el archivo y explica la consecuencia.
- **Lección:** un dato **derivado** que se persiste al importar (como `ticker_base`) es una trampa cuando el import puede correr sin todo el contexto — y el dedupe impide que se corrija solo. Si se persiste, hay que tener una reparación explícita.
- **Estado:** `tests/test_cartera_ingest.py` (11, con 4 de regresión de estos bugs). Suite **249 passed, 3 skipped**.

## 2026-07-30 — Fase 3b, paso 1: el motor cronológico (`ledger.py`)
- **Autor:** Claude (Opus 5), con Franco. Arranque de la **Fase 3b**.
- **Hallazgo que definió el orden de la fase:** los cuatro puntos de 3b (amortizaciones parciales, realizado por operación, cauciones/dividendos, análisis por sector) comparten una misma limitación estructural: `_acumular()` de `posiciones.py` es una **agregación sin orden temporal**. Por eso el realizado de una venta se mide contra el **PPC de toda la historia**, incluidas las compras **posteriores** a esa venta. Se decidió construir la línea de tiempo una sola vez y apoyar los cuatro puntos ahí.
- **`ledger.py` (motor cronológico, módulo puro):** recorre los eventos ordenados por fecha con **PPC móvil** y emite una `Realizacion` por cada cierre (ticker, fecha, unidades, ingreso, costo liberado al PPC vigente, resultado ARS/USD, rendimiento %, **días de tenencia** contra la fecha de compra promedio ponderada por costo). `EstadoTicker` mantiene cantidad, costo vivo, flujos y **retenciones por separado** (para poder mostrar el dividendo bruto y el neto en el punto 3). Adaptadores `eventos_desde_movimientos` (parser) y `eventos_desde_db`.
- **Reglas explícitas:** ante misma fecha se procesa **primero la compra** (el export no trae hora; si no, una venta liquidada el mismo día quedaría sin costo); vender más de lo registrado **no inventa costo** — cierra lo que hay y marca `descubierta` con advertencia; una compra sin cantidad (pagaré) acumula costo y avisa que el PPC necesita la tenencia del broker.
- **Convención de amortización (dato de dominio aportado por Franco):** en Argentina la amortización se refleja en el **precio, nunca en los nominales** — el broker deja la cantidad quieta. Por eso `AMORTIZACION` se registra como cobro y **no** toca cantidad ni costo. Queda documentado en el módulo y cubierto por test.
- **⚠️ Corrección de un supuesto sobre AE38 (verificado contra el crudo real):** no hubo amortización el 9/7/2026. Los movimientos muestran **solo cupones**: US$237,50 (9/1/2025), US$236,31 (10/7/2025 y 9/1/2026) sobre 9.500 VN = **2,4875 por cada 100**, y US$89,65 el 13/7/2026 sobre los 3.604 VN que quedaron tras la **venta** de 5.896 el 6/7/2026 — **la misma tasa por nominal**. Si hubiera amortizado 4,545%, ese cupón habría sido US$85,56. La primera amortización de AE38 es el **9/7/2027** (22 cuotas semestrales del 4,545% hasta el 9/1/2038). AN29 es **bullet** (100% al 30/11/2029). → **Ningún instrumento de la cartera amortiza parcialmente antes de julio de 2027.**
- **Verificación con datos reales** (crudo completo, 585 movimientos, 46 ventas): el realizado en pesos cambia en **9 tickers** y el total pasa de **$3.297.014 a $3.145.965 (−$151.050, −4,6%)**. Dos mecanismos distintos, ambos corregidos por la cronología:
  1. **Eventos retroactivos que contaminan ventas pasadas — `SPY`, el mayor de todos (−$688.510).** El ajuste de ratio de CEDEAR está en el crudo como una **compra de 70 unidades a costo cero fechada el 23/7/2026**, tres meses **después** de la venta del 20/4/2026. Con PPC global esas 70 unidades gratis diluyen el promedio de toda la historia (69 compradas por $2.754.458 + 70 gratis → PPC $19.672) y ese promedio diluido se aplica **hacia atrás** a una venta anterior: la app informa **$1.122.268** de ganancia cuando el costo real de esas 35 unidades ese día era $39.343 c/u → **$433.757 (+31,5% en 143 días)**.
  2. **Comprar, vender y recomprar más caro — `TGNO4` es el caso testigo.** Vendió 30 el 27/10/2025 a $3.183 que había comprado a $3.132 → **ganancia real de $1.540 (+1,6%)**, pero la app informa **−$37.700 de pérdida** porque la compra de diciembre a $4.870 le sube el promedio histórico. Ídem GGAL (+$279.883), ASML, VIST, NU, MELI, NVDA, BYMA.
- ⚠️ **Caveat de esta medición:** se corrió sobre el crudo con los objetos del parser, que **no tienen el TC congelado** — las compras denominadas en USD aportan ~0 al costo en pesos, así que los **absolutos** se van a mover al correrlo contra la base. La **diferencia entre los dos métodos** usa exactamente los mismos insumos en ambos casos, así que el mecanismo y el signo no cambian. Repetir la medición contra la DB antes de cablear.
- Las 3 advertencias del motor (GGALX, BYMA, TXAR) son las ventas descubiertas ya conocidas.
- **Nada cambió todavía en la app:** el módulo es aditivo y no está cableado. El patrimonio, la TIR y el gate de reconciliación son **inmunes** (el método del patrimonio no suma operación por operación).
- **Estado:** `tests/test_cartera_ledger.py` (**17 tests**). Suite completa en verde.
- **Próximo:** ADR-0005 (PPC móvil para el realizado; ADR-0003 fijó "costo promedio ponderado como el Excel") y enchufar el realizado por operación en `posiciones.py`/`kpis.py` + vista.

## 2026-07-30 — Fase 3b, paso 2: el realizado por operación entra a la app (ADR-0005)
- **Autor:** Claude (Opus 5), con Franco. Skill `ui-ux-web-moderno` aplicada (obligatoria en UI).
- **`docs/decisiones/ADR-0005-realizado-ppc-movil.md`:** el resultado realizado pasa a medirse con el **PPC vigente al momento de cada venta**. Se **mantiene** el costo promedio ponderado (no se adopta FIFO, sigue en MEJORAS): lo que cambia es *cuándo* se promedia. Se registra explícitamente que el realizado por ticker deja de coincidir con el Excel, y que el gate de recon (cantidades + costos USD) no se toca.
- **⚠️ Consistencia obligatoria: el realizado y el costo del remanente van juntos.** Enchufar solo el realizado dejaba la mitad de cada ticker medida con un método y la otra mitad con el otro, y la identidad `costo liberado + costo remanente = total comprado` dejaba de cerrar (en ASML, por $104.552). Por eso `Ledger.plano_por_ticker()` devuelve las cuatro cifras juntas y `kpis.valuar(cronologico=...)` las aplica de a pares. **Test de la identidad** incluido — la lección de 3a: todo agregado se contrasta contra una identidad independiente antes de mostrarse.
- **`kpis.valuar(cronologico=None)`**: sin ledger conserva exactamente el comportamiento anterior (PPC global), que es lo que usa el gate de reconciliación. Cuando el ledger no tiene PPC (pagarés: el movimiento no trae cantidad) se cae al cálculo de `posiciones.py`, que promedia contra la tenencia del broker.
- **Vista — "Operaciones cerradas"** (`_operaciones_cerradas`): 3 KPI cards (realizado en pesos, en dólares, aciertos + la mejor operación) y una fila por venta con fecha, unidades, **PPC del día**, precio de venta, resultado, rendimiento en ARS y USD, y **días de tenencia**. Tokens `--cs-*`, cifras tabulares, signo + flecha + color, `column_config` es-AR, empty state propio. La lógica de armado vive en `ledger.tabla_operaciones()` / `resumen_operaciones()` para poder testearse **sin Streamlit**.
- 🔎 **Hallazgo con datos reales — ASML, y la guarda funcionó.** La venta de 9 unidades del 21/1/2026 daba **+22.754%**: la compra del 16/5/2025 figura como **9 unidades a $60,10** (total $543,05) contra una venta a $13.840. **Franco confirmó la causa el mismo día: el broker le sacó dos ceros — fueron a $6.010.** Efecto en la app **actual**: arrastra el PPC global de ASML a $11.677 cuando las 15 unidades vivas costaron **$18.647**.
- **Impacto de la corrección (medido, todavía NO aplicada):** la venta pasa a **+$69.803 (+128,5% ARS / +80,2% USD en 250 días)**; realizado total $5.630.023 → **$5.576.261**; el PPC de las 15 unidades vivas **no cambia** (vienen de la compra de junio 2026); operaciones a revisar 4 → 3.
- ⚠️ **La corrección no es trivial y no se hizo sin decidirlo con Franco: el `hash_dedupe`.** La fila ya está en la DB con el hash del monto equivocado. Arreglar el crudo y reimportar **duplicaría** la compra (18 unidades en vez de 9), porque el hash nuevo no matchea el viejo — misma clase de trampa que el `ticker_base`. Toda corrección de un movimiento debe **recalcular `hash_dedupe` con la misma regla del parser** (fecha + categoría + descripción + monto + cantidad) para que una reimportación posterior del Excel corregido dedupe en vez de duplicar.
- **Guarda nueva (`Realizacion.sospechosa`, umbral 1.000%):** una operación con rendimiento de cuatro cifras se marca `revisar` en la tabla, se explica en las advertencias y **queda excluida de "la mejor operación"** — destacar un +22.754% que sale de un dato malo sería presentar un error como un logro. Regla de la casa: *cuando un número no cierra, sospechá de la cantidad o del precio antes que del cálculo*.
- **Verificación end-to-end con datos reales** (crudo de 585 movimientos con el **MEP congelado** desde `argentinadatos`, cantidades y precios de la foto del 30/7):

  | | Hoy (PPC global) | Con el motor | Δ |
  |---|---:|---:|---:|
  | Valor de cartera | $23.900.213 | $23.900.213 | **0** |
  | Costo de la tenencia | $21.070.343 | $20.640.875 | −$429.468 |
  | Resultado no realizado | $2.829.869 | $3.259.338 | +$429.468 |
  | Realizado en ventas | $6.063.678 | $5.630.023 | −$433.655 |
  | Invertido / flujos cobrados | $41.354.011 / $7.494.203 | idem | **0** |
  | Rendimiento sobre costo | 13,4% | **15,8%** | |

  **El valor de cartera no se mueve → patrimonio, capital aportado, resultado total y TIR quedan intactos.** Cambian 8 PPC: ASML 11.677→18.647, SPY 23.519→15.679, GGAL 5.848→7.314, TGNO4 4.440→4.797, VIST, NU, NVDA, MELI.
- **Operaciones:** 45 cerradas, 38 ganadoras. La mejor **AE38 +97,7% en 578 días**; la peor **AGRO −31,8% en 130 días**. (Antes de la guarda, "la mejor" era el ASML fantasma.)
- **Estado:** `tests/test_cartera_ledger.py` (**27 tests**). Suite **271 passed, 3 skipped**.
- **Próximo:** punto 3 de la 3b — cauciones y dividendos como rendimientos con su propia tasa (101 cauciones, ≈$33.365 de interés; $53.701 de dividendos brutos contra $5.191 de retenciones que ya se acumulan aparte en el ledger).

## 2026-07-30 — Corrección de movimientos mal informados por el broker (ASML resuelto)
- **Autor:** Claude (Opus 5), con Franco. **Franco confirmó la causa del ASML:** *"las compré a 6010 pesos pero le quitó dos ceros por error"*. Decisión suya: corregir **en la app y en el Excel** para que quede limpio.
- **`parser.clave_dedupe()` / `parser.hash_dedupe()`:** la regla de identidad de un movimiento pasa a vivir en **un solo lugar** y se expone. Era condición para lo que sigue: cualquier corrección posterior tiene que producir **exactamente** el hash que generaría re-parsear el archivo corregido.
- **`ingest.corregir_movimiento()`** (+ `movimientos_de_ticker()`): corrige monto/cantidad/precio de un movimiento ya importado y **recalcula el `hash_dedupe`** con esa regla. Si el hash cae ocupado prueba la ocurrencia siguiente, igual que el parser dentro de un archivo. Reescala `precio_normalizado` en la misma proporción (bonos por 100). Scope por usuario.
- ⚠️ **La trampa, congelada en dos tests.** `test_corregir_movimiento_deja_el_hash_que_produciria_el_excel_corregido` verifica que después de corregir en la app, reimportar el Excel corregido dé **(0 insertados, 1 salteado)**. Y `test_sin_corregir_en_la_app_el_excel_arreglado_DUPLICA` deja documentado qué pasa si alguien decide que la corrección desde la app "sobra": quedan **18 unidades de ASML donde hay 9**.
- **Vista:** expander "Corregir un movimiento mal informado por el broker" — buscar por ticker, elegir el movimiento, editar monto y precio, con el recordatorio explícito de poner los mismos valores en el Excel.
- **Excel de Franco corregido** (`Cartera personal/Inversiones.xlsx`, `Movimientos Crudo` fila 460): `E460` −543,05 → **−54.305** y `G460` 60,10 → **6.010**. Respaldo previo en *"Inversiones - respaldo pre-fix-ASML 2026-07-30.xlsx"*. **Edición quirúrgica sobre el XML del .xlsx**, no round-trip de openpyxl: el libro tiene 16 hojas con fórmulas, formato condicional y extensiones que openpyxl **descarta al reescribir**. Verificado post-edición: 16 hojas, 586 filas, resto intacto.
- **Resultado:** la venta del 21/1/2026 pasa de **+22.754%** a **+$69.802,85 (+128,5% ARS / +80,2% USD en 250 días)** — y pasa a ser, legítimamente, la mejor operación de la cartera. Realizado total $5.630.023 → **$5.576.261**. Operaciones a revisar: 4 → **3** (quedan las descubiertas conocidas GGALX/BYMA/TXAR).
- **Barrido preventivo de precios anómalos** (cada precio contra la mediana de su ticker, factor >8×): **12 filas** salen marcadas y **11 son legítimas** — son las compras denominadas en USD, donde el precio está en dólares (AAL US$9 contra $10.400, SPY US$35 contra $42.522, etc.).
- 📌 **Candidato pendiente, NO tocado — `TTM26`.** La compra del 4/2/2026 de **17.395 nominales por $17,78** (precio 0,00102) contra otra compra del **mismo día** a 1,458. Si el precio correcto fuera ~1,40, el costo del bono pasaría de $633.940 a $658.275 y su resultado de **+13,3% a +9,1%**. No se toca sin que Franco lo confirme con el broker: el +13,3% es el número que él validó a mano el 23/7.
- **Estado:** `tests/test_cartera_ingest.py` (**16 tests**). Suite **276 passed, 3 skipped**.

## 2026-07-30 — Fase 3b, punto 3: la plata quieta (cauciones, dividendos, cuenta remunerada)
- **Autor:** Claude (Opus 5), con Franco. Skill `ui-ux-web-moderno` aplicada.
- **`rendimientos.py` (módulo puro).** Las cauciones **no son instrumentos** (`es_instrumento = False`, pseudo-ticker `CC`), así que hasta ahora eran invisibles: ni figuraban en la tabla de posiciones ni tenían tasa. El interés estaba dentro del efectivo pero sin nombre.
- **Cómo vienen los datos (relevado sobre los 585 movimientos reales, no supuesto):** la colocación (`CAUCION_COL`, monto negativo) y su vencimiento (`CAUCION_VTO`, positivo) **comparten la fecha de concertación**; lo que cambia es la de liquidación, y esa diferencia **es el plazo**. **101 pares, cero huérfanas, todas en ARS.** Plazos reales: 1 día (77), 2 (1), 3 (21), 5 (2).
- ⚠️ **La tasa va ponderada por capital y tiempo**, no es el promedio de las TNA. Promediarlas le daría el mismo peso a una caución de $20.000 por un día que a una de $2,7 millones por cinco. La medida correcta es `interés total / (Σ capital × días / 365)`. En los datos de Franco casi coinciden (25,60% vs 25,37%), pero el test sintético muestra el caso donde el promedio simple da **48%** y la tasa real es **5,3%**.
- **Identidad contable independiente (la lección de 3a), en test y verificada con datos reales:** sin importar cómo se apareen las patas, la plata que las cauciones dejaron en la cuenta es la **suma neta de todos sus movimientos**. Da **$33.365,31** por las dos vías → el apareo es correcto.
- **Casos que no se inventan:** una colocación sin vencimiento queda `abierta` (está viva o el export se cortó) y **no** se le calcula tasa; un vencimiento sin colocación se descarta (sin capital no hay tasa); si algún día hubiera varias el mismo día, se aparean ordenadas por monto.
- **Dividendos netos de retención** por instrumento (`dividendos_por_ticker`), respetando la regla del LEEME de ignorar el espejo en pesos. **Cuenta remunerada** (`total_remuneracion`).
- **Vista — "La plata quieta":** 3 KPI cards (interés de cauciones con su TNA, dividendos netos, cuenta remunerada), tabla de cauciones por año, tabla de dividendos por instrumento con el % retenido, y un expander con las 101 cauciones. **Aclara explícitamente que es atribución, no plata nueva**: ya está todo dentro del patrimonio.
- **Números reales (dic-2024 → jul-2026):**

  | | |
  |---|---:|
  | Cauciones | **101** · interés **$33.365,31** (US$24,19) |
  | TNA ponderada | **25,60%** — 2024: 24,48% · 2025: 29,31% · 2026: 21,38% |
  | Capital rotado | $37.792.222 (no es capital propio: se recoloca casi todos los días) |
  | Dividendos | 62 cobros · bruto **$89.086,78** · retención **−$5.190,66** · neto **$83.896,12** |
  | Cuenta remunerada | 41 acreditaciones · **$3.300,98** |
  | **Total de la caja** | **$120.562,41** |

- **Retenciones muy distintas según el papel:** GGAL **10,9%**, TGNO4 y BMA **7,1%**, y los CEDEARs que pagan en dólares **0%**. Antes esto no se veía en ningún lado.
- 🔎 **Señal de que los datos son buenos:** las TNA más altas de toda la serie (hasta 105% anual) son todas de **octubre 2025**, el mes de las elecciones legislativas — el apretón de liquidez pre-electoral quedó registrado solo. Ojo igual: en montos chicos y plazos de un día, unos pesos de redondeo mueven la TNA individual decenas de puntos; por eso la representativa es la ponderada.
- **Doble camino verificado:** los módulos puros y los adaptadores de DB (`cauciones_desde_db`, `flujos_caja_desde_db`) dan **exactamente los mismos números** sobre los 585 movimientos importados a una base real.
- **Estado:** `tests/test_cartera_rendimientos.py` (**19 tests**). Suite **295 passed, 3 skipped**.
- **Próximo:** punto 4 de la 3b — análisis por sector (reusando el snapshot de scoring) y por tipo de renta.

## 2026-07-30 — Fase 3b, punto 4: cómo está repartida la cartera → **FASE 3b COMPLETA**
- **Autor:** Claude (Opus 5), con Franco. Skill `ui-ux-web-moderno` aplicada.
- **Decisión de Franco antes de codear:** tipo de renta como corte principal (cobertura total) y sector como capa secundaria solo donde el dato exista, con un "Sin dato" honesto. **Nada inventado.**
- **`analisis.py` (módulo puro).** `por_tipo_de_renta` (desde `categoria_activo` de Config) y `por_sector` (desde el snapshot del scoring, que hoy trae **100 empresas**, no las ~20 que decía ESTADO). `sectores_desde_snapshot` tolera un snapshot caído o vacío → todo queda en "Sin dato" y la cartera se muestra igual.
- **Dos decisiones que evitan repetir errores viejos:**
  1. **El porcentaje se mide contra el patrimonio, con el efectivo adentro.** Si se midiera solo sobre las posiciones, la caja desaparecería del cuadro y todo lo demás se vería más grande.
  2. **Se agrega el resultado NO realizado, nunca el total.** Sumar el resultado total por grupo repetiría la trampa de 3a (la devaluación infla los subtotales: $9,92M por componentes contra $2,27M por patrimonio). `valor − costo` vive entero en pesos de hoy y sí se puede sumar. Está dicho en el docstring, en el `help` de la columna y en un test.
- ⚠️ **Dos cosas que no cerraban en la primera corrida, encontradas mirando los números reales:**
  1. **El pagaré —el 34% de la cartera— caía en "Sin dato".** Su ticker empieza con `#` y **nunca** estuvo en `Config`, así que llega con categoría "Otros". Se reconoce por el ticker: es **renta fija** por definición (se compra a descuento y su precio converge al nominal).
  2. **El sector se diluía a un "Sin dato" del 74,6%** porque entraban bonos, pagaré, cripto y efectivo. A esos **no les falta el sector: no tienen**. `por_sector` ahora mira **solo la renta variable** y el porcentaje se lee como *"de mi renta variable, cuánto en cada sector"*. La cobertura pasó de un 25% engañoso a un **65,7% real**.
- **Números reales (al 30/7/2026, patrimonio $23.962.038):**

  | Tipo de renta | peso | posiciones | valor |
  |---|---:|---:|---:|
  | Renta fija | **60,1%** | 3 | $14.406.991 |
  | Renta variable | **38,3%** | 18 | $9.183.750 |
  | Cripto | 1,3% | 1 | $309.472 |
  | Efectivo | 0,3% | 1 | $61.825 |

  **Sector (sobre la renta variable):** Technology 21,5% · Financial Services 11,3% · Consumer Cyclical 10,7% · Communication Services 9,3% · Energy 7,6% · Healthcare 2,2% · Utilities 2,0% · Industrials 1,1% · **Sin dato 34,3%** (TGNO4 y los 4 ETFs: SPY, URA, GLD, COPX).
- **Vista — "Cómo está repartida":** dos tablas lado a lado con barra de peso (`ProgressColumn`), valor en pesos y dólares, no realizado y rendimiento. "Sin dato" **siempre va último** aunque pese mucho: es una etiqueta de ignorancia, no una categoría que compita.
- **Estado:** `tests/test_cartera_analisis.py` (**29 tests**). Suite **324 passed, 3 skipped**. **Fase 3b completa.**

## 2026-07-30 — Sector e industria automáticos (pedido de Franco sobre el punto 4)
- **Autor:** Claude (Opus 5), con Franco. Pedido textual: *"la app debería ser capaz de reconocer por sí sola los sectores de las empresas"*, más TGNO4 (utilities argentina de transporte de gas) y una categoría propia para los ETF (*"ETF - Oro"*).
- **Fuente elegida: Yahoo `v1/finance/search`.** Devuelve `sector` **e `industry`** sin autenticación. ⚠️ `quoteSummary` (el endpoint "natural" para esto) **exige un crumb con cookie** y devuelve `Unauthorized` — probado antes de elegir.
- **`core/market_data/sectores.py`** con los mismos resguardos que `mep.py` y `precios.py`: `fetch` inyectable (tests sin red), **caché en DB** (M12, `cartera_sectores`), **override manual** que gana siempre, y nunca lanza.
- **Cascada:** override → snapshot del scoring (ya está en memoria, no cuesta red) → Yahoo. Solo se consultan los papeles de **renta variable**.
- **Detalles que evitan errores reales:**
  - **Coincidencia exacta de símbolo.** Buscando `URA` Yahoo devuelve también `UROY` (una minera de uranio): quedarse con el primer resultado le habría puesto a un ETF el sector de una empresa.
  - **Sufijo `.BA`** para las argentinas: `TGNO4` no existe en Yahoo, `TGNO4.BA` sí.
  - **Caché negativa.** Lo que no resuelve también se guarda; si no, un ticker desconocido dispararía una búsqueda en **cada** carga de la pantalla, para siempre. `forzar=True` reintenta.
  - **Los pagarés no se consultan**: no son una empresa.
- **Los ETF no tienen sector, y está bien**: Yahoo los marca `quoteType: ETF` con `sector: null` porque **son una canasta**. Se les arma la etiqueta desde el nombre del fondo con un mapa corto de palabras clave: `SPDR Gold Shares` → **"ETF · Oro"**. Lo que no matchea cae al nombre del fondo — nunca a un sector inventado.
- 📌 **Decisión de Franco (discrepancia real):** Yahoo clasifica a **TGNO4** como **Energy · Oil & Gas Midstream** (el estándar GICS mete el transporte de gas en Energía), no como Utilities. Franco eligió **que mande Yahoo**, para que su cartera quede comparable contra cualquier referencia que use GICS. El override queda disponible y hay UI para usarlo.
- **Industria como segundo nivel** (también decisión suya): viene gratis en la misma llamada.
- **Resultado: cobertura 100% de la renta variable** (antes 65,7%). **Cero "Sin dato".**

  | Sector | peso | | Industria | peso |
  |---|---:|---|---|---:|
  | ETF · S&P 500 | 22,1% | | ETF · S&P 500 | 22,1% |
  | Technology | 21,5% | | Semiconductors | 13,2% |
  | Energy | 12,3% | | Banks—Regional | 11,3% |
  | Financial Services | 11,3% | | Internet Retail | 10,7% |
  | Consumer Cyclical | 10,7% | | Internet Content & Information | 9,3% |
  | Communication Services | 9,3% | | Oil & Gas E&P | 7,6% |
  | ETF · Uranio / Oro / Cobre | 7,5% | | Software—Application | 5,5% |
  | Healthcare · Utilities · Industrials | 5,3% | | Oil & Gas Midstream | 4,7% |

- **Lo que se ve ahora y antes no:** el 21,5% de Technology es en realidad **16% en semiconductores** (NVDA + TSM + ASML) — una concentración que el corte por sector escondía. Y TGNO4 se juntó con VIST en Energy (12,3%).
- **Vista:** el cuadro por sector, un expander con el detalle por industria y otro para **fijar el sector a mano**, con el caso de TGNO4 explicado ahí mismo.
- **Estado:** `tests/test_market_data_sectores.py` (**18 tests**, sin red). Suite **342 passed, 3 skipped**.

## 2026-07-30 — La cartera ahora deja punto de retorno antes de escribir (Fase 4)
- **Autor:** Claude (Opus 5). Detalle completo del respaldo en `docs/RUNBOOK.md`; acá queda lo que toca a este módulo.
- **Agujero encontrado al relevar la Fase 4:** `backup_db()` lo disparaban **solo** las escrituras de Finanzas Personales (transacciones, presupuestos, categorías). **Importar 585 movimientos de cartera no generaba ninguna copia** — y un import masivo es la operación más destructiva de la app: si el archivo está mal entran cientos de filas equivocadas, y el **dedupe hace que reimportar el bueno no las arregle** (la misma trampa del `ticker_base` y del ASML).
- **Ahora sacan copia previa:** `importar_movimientos`, `corregir_movimiento`, `guardar_foto` (la foto del broker manda sobre las cantidades, importar la equivocada altera todas las valuaciones) y `set_tenencia_manual`.
- **La copia se saca ANTES de escribir**, así sirve para deshacer: hay test que verifica que la copia dejada por el segundo import contiene el estado del primero.
- **Estado:** `tests/test_backup_restore.py` (5 tests). Suite **347 passed, 3 skipped**.

## 2026-08-04 — La tabla de posiciones mostraba otro número que el broker
- **Autor:** Claude (Opus 5), con Franco. **Lo detectó Franco comparando la app contra la pantalla de inviu** (ASML: la app decía −20% USD, el broker −2,95%).
- **Causa (de diseño, no de cálculo):** la columna `Rend. US$ %` mostraba `resultado_usd / invertido_usd`, o sea el **rendimiento total histórico del papel** — ventas pasadas + dividendos + no realizado, sobre **todo** lo que se compró alguna vez. El broker muestra otra cosa: el **no realizado de la tenencia viva**. Para un papel que nunca se vendió casi coinciden; **ASML se vendió en enero**, así que eran números estructuralmente distintos.
- **Regla que fijó Franco, y que el motor ya implementaba:** *"cada operación con posición abierta que vuelve a cerrarse es un trade con su propio rendimiento"* — comprar a 100 y vender a 150 es +50%; volver a comprar a 150 y vender a 135 es −10%, y **no se restan entre sí**. Con compras a varios precios, el costo es el promedio ponderado y la venta (total o parcial) se mide contra ese promedio. Es exactamente el PPC móvil del **ADR-0005**: no hubo que recalcular nada, solo mostrar lo correcto.
- **Cambio:** `PosicionValuada.rendimiento_vivo_pct` y `rendimiento_vivo_usd_pct` (no realizado / costo de la tenencia). La tabla de posiciones pasa a mostrar **solo la posición viva**: `No realizado`, `Rend. %`, `Rend. US$ %` y el valor en `US$`. Las posiciones cerradas muestran `—` en esas columnas: su resultado vive en *Operaciones cerradas*. El rendimiento total del papel sigue existiendo (`rendimiento_usd_pct`) y se ve en el bloque de arriba.
- **Verificado contra el broker:** con los datos sanos de ASML (15 unidades compradas en junio a $279.711,68, valuadas a $18.360) la columna nueva da **−2,91%** contra el **−2,95%** de inviu — 0,04 pp, ruido de precio. La columna vieja daba **+13,9%**.
- ⚠️ **Queda pendiente de Franco:** ninguna de las dos fórmulas da el **−20%** que él ve en producción, así que **hay además un problema de datos** en la base. Sospecha principal: la compra de ASML del 16/5/2025 **duplicada** — si se corrigió el Excel y se reimportó **sin** usar antes el panel de corrección, entran las dos filas ($543,05 y $54.305). Es la trampa 14 del prompt de inicio. Se verifica en *Corregir un movimiento* → `ASML`, y en el panel de reconciliación (la pantalla reporta **3 diferencias**).
- **Estado:** `tests/test_cartera_kpis.py` (32 tests). Suite **365 passed, 3 skipped**.

## 2026-08-04 — Ajustes de tenencia: lo que el broker no informa (M13)
- **Autor:** Claude (Opus 5), con Franco. Disparado por los cinco avisos de *Operaciones a revisar*.
- **Diagnóstico de los cinco avisos** — tres causas distintas, ninguna un bug del código:
  - **BYMA**: compró 5 a $481 y 4 a $410 (9 u, $4.061,15) y vendió **18** a $226. Cantidad ×2, precio ÷2, resultado −$7,92: un **split** que el export no informa. Confirmado por Franco.
  - **TXAR**: vendió 300 el 10/7/2025 por $186.751,31 **sin ninguna compra**. Las tenía desde antes del registro.
  - **GGALX**: 100 **cupones de suscripción recibidos gratis** por tener GGAL, vendidos por $1.494,01.
  - **#UMV060770008**: pagaré sin cantidad en el movimiento — conocido y esperado (trampa #4), lo cubre la tenencia del broker.
  - **ASML**: **el aviso confirmó que NO hay duplicado.** Reporta PPC $60,34 y `543,05 / 9 = 60,34` exacto: en producción quedó **solo la fila vieja**. El Excel ya está corregido ($54.305 a $6.010) pero la corrección nunca se aplicó en la base. **Se arregla desde el panel de corrección, no reimportando** — al corregir el Excel cambió el `hash_dedupe` y un reimport sí crearía el duplicado (trampa #14).
- **Solución (elección de Franco entre parchar el Excel o construir el mecanismo):** **M13 + `ajustes.py`**. Un primitivo único —`(fecha, ticker, Δcantidad, Δcosto, tipo)`— cubre los cuatro casos: split (+9, $0), saldo inicial (+300, su costo), canje/cupón (+100, $0) y ratio de CEDEAR.
- **Tabla aparte de `cartera_movimientos`, a propósito.** Esa tabla es *lo que dice el broker*; `cartera_ajustes` es *lo que el broker no informa*. Mezclarlas rompería el sentido de la reconciliación (su diferencia **es** el chequeo) y los ajustes se perderían al borrar los movimientos para reimportar de cero.
- ⚠️ **El punto que hacía peligroso el módulo: la identidad del patrimonio.** `capital_aportado()` leía solo `DEPOSITO`/`RETIRO`. Cargar el costo de las TXAR sin más habría hecho que el método del patrimonio contara los **$186.751 enteros como ganancia**, porque esa plata entró antes del registro y no figura como aporte. **Regla implementada, única y automática: el depósito sintético es igual al costo del ajuste.** Costo 0 (split, cupón) → aporte 0, que es lo correcto: no entró ni salió plata. Es el mismo mecanismo que la fila *"Saldo inicial sintetico"* del Excel, pero explícito y con test. Los ajustes entran también a `flujos_de_capital()` **con su fecha**, o si no la TIR se calcularía sobre menos capital y salteando el momento del aporte.
- **Verificado sobre los datos reales del Excel:** los tres avisos desaparecen; BYMA cierra en **−$7,92**, TXAR en **−$46.687,83 (−20,00%)** y GGALX en **+$1.494,01** (rendimiento `s/d`: sin costo no hay porcentaje, y no se inventa un infinito). El realizado total baja de **$3.092.202,73** a **$2.858.763,59**: exactamente **$233.439,14**, que es exactamente el capital que declaran los ajustes. **La identidad cierra al centavo.**
- **`estimado`:** el costo de TXAR se despejó de un rendimiento recordado (`costo = ingreso / (1 + r)`). Un número deducido de la memoria no se distingue después de uno verificado si no se guarda que lo era, así que se persiste el flag y la app lo muestra marcado como *aproximado*.
- **Las dos vías alimentadas:** ledger (`eventos_desde_db`, con `con_ajustes=True` **por defecto** para que ningún consumidor se los olvide) y `posiciones_desde_db` (un `AJUSTE` se acumula como una compra). Si divergieran, la tabla y la reconciliación se contradirían.
- **`tests/test_nombres_definidos.py` (nuevo, 58 casos):** salió de un error propio — usé `backup_db` en `view.py` sin importarlo. Lee el **bytecode** de cada módulo, junta los `LOAD_GLOBAL` y verifica que existan. Mirar bytecode y no AST evita los falsos positivos de atributos y locales. **Verificado al revés:** se reintrodujo el error y el test lo nombró; se sacó y pasó. Cubre la misma familia que el `UnboundLocalError: firma_val` de producción.
- ⚠️ **Pendiente de dato de Franco:** el costo real de las **100 GGAL** del saldo inicial. Hoy están a **$4,49** (la fila sintética hace doble trabajo: cubre las acciones *y* dice "canje GGALX"), y $4,49 no es un precio de GGAL en diciembre de 2024. Con ese costo la venta de 200 del 27/10/2025 da **+$815.000**; con un costo realista daría **~+$316.000**. **Medio millón de diferencia**, el mismo mecanismo que ASML.
- **Estado:** `tests/test_cartera_ajustes.py` (26 tests) + `tests/test_nombres_definidos.py`. Suite **434 passed, 3 skipped** (local, con oráculos).

## 2026-08-04 (corrección) — El "problema de las 100 GGAL" no existía
- **Autor:** Claude (Opus 5). **Retracta** la última viñeta de la entrada anterior.
- **Lo que se afirmó mal:** que el saldo inicial de GGAL estaba cargado a **$4,49 por acción** y que eso inflaba la venta del 27/10/2025 en **~$500.000**. Se presentó como el número pendiente más grande. **Era falso.**
- **La causa, y es una trampa nueva del proyecto:** la fila del saldo inicial está **denominada en USD** (US$449 por 100 acciones = US$4,49 c/u, el precio correcto de GGAL en diciembre de 2024). La verificación se corrió sobre los objetos del **parser**, y **el parser no lleva el TC MEP: se congela al importar** (ADR-0004; está documentado en el docstring de `posiciones()`). Con `tc_mep=None`, `Evento.importes` devuelve **0 pesos** para todo lo denominado en dólares, así que esas 100 acciones se computaron con un costo de **$449 en vez de $476.748**.
- **Producción estaba bien todo el tiempo:** PPC **$5.188,63**, venta del 27/10/2025 **+$339.256,70**. Despeje que lo confirma: $476.748 / US$449 = **TC $1.061,80**, MEP plausible de diciembre de 2024.
- **El mismo error contaminó los totales que se le dieron a Franco como "esperados".** Se anunció un realizado de **$2.858.763,59** y la app mostró **$5.432.244**. La diferencia **no era un bug**: (a) el sim ponía en cero el resultado en pesos de todo lo que estaba en dólares, y (b) la mayor operación de la cartera —**AE38, venta del 6/7/2026, 5.896 nominales, +$3.764.597,55 (+97,65% ARS / +37,61% USD, 578 días)**— sí está en el Excel y el sim la computaba en $0 por la misma razón. En esa fecha se vendió el AE38 y se compró el pagaré `#UMV060770008` por $7.674.486,21: la punta de compra explica la de venta.
- **Lo que sí era correcto de la verificación:** BYMA, TXAR y GGALX son instrumentos **en pesos**, así que sus números (−$7,92 / −$46.687,83 / +$1.494,01) no estaban afectados y coinciden con producción.
- 🧭 **Regla que queda:** **nunca validar totales en pesos corriendo el ledger sobre objetos del parser.** Para totales, la fuente es la DB (con el TC congelado) o la app. El parser sirve para lógica de cantidades y para instrumentos en pesos.
- **Estado de los ajustes en producción:** BYMA ✔ y TXAR ✔ (el aporte sintético se ve: capital aportado $13.462.628 → **$13.696.067**, exactamente +$233.439). **GGALX quedó sin cargar** — su aviso sigue apareciendo. El otro aviso restante es el del pagaré, esperado.

## 2026-08-05 — Vencimientos de renta fija (M14)
- **Autor:** Claude (Opus 5), con Franco. Primer paso del **análisis enriquecido** (ítem 🔴 de `MEJORAS.md`).
- **Hallazgo que evitó cargar datos a mano:** las fechas de vencimiento **ya estaban** en la cartera, en la columna *Descripción* de la hoja `Config` — `"Bono Tesoro Nacional Vto. 30/11/2029"`, `"Letra Tesoro Vto. 17/04/2026"`, `"ON MSU Energy Vto. 05/12/2030"`. **12 de 14 instrumentos de renta fija resuelven solos.**
- ⚠️ **Bug de fondo encontrado en el camino:** `cargar_instrumentos_en_db()` guardaba `descripcion` en `cartera_instrumentos`, pero **el dataclass `Instrumento` no tenía el campo**, así que el dato existía en la base y no llegaba a ninguna parte del código. Se agregó a `Instrumento`, a `instrumentos_desde_config()` (Config!I) y a `_instrumentos_de_db()`. Es la trampa #5 al revés: no se guardaba un derivado, se derivaba sin leer lo guardado.
- **Tres calidades de dato, distinguidas a propósito** (`precision`): `dia` (fecha completa), `anio` (`"Bono Tesoro Vto. 2028"` — se sabe el año y nada más) y `sin_dato`. **Nunca se fabrica una fecha:** un `31/12/2028` inventado se ve idéntico a uno real y contamina cualquier cuenta de días posterior. Con `precision="anio"` la etiqueta muestra `2028` y `dias_restantes()` devuelve `None`. Misma disciplina que el `estimado` de los ajustes.
- **El año del nombre NO es un vencimiento:** `"Bono USD 2038"` (AE38) y `"Bono USD 2029"` (AL29) tienen el año en el nombre del bono, no como fecha. Tomarlo sería afirmar algo que la descripción no dice. Quedan en `s/d` y se corrigen a mano. Hay test explícito.
- **M14 `cartera_vencimientos`:** overrides manuales con la cascada ya probada de `cartera_sectores` (**el manual gana siempre**). Tabla aparte porque `cartera_instrumentos` **se re-escribe en cada import** desde Config y pisaría el dato. Sin `user_id`: que el AN29 venza el 30/11/2029 no depende de quién lo tenga.
- **Vista:** KPI de cuánta plata vence en 90 días + cuál es el próximo, tabla ordenada del que vence antes al que vence después (**lo que no tiene fecha va al final**, no mezclado, porque no se puede afirmar que vence tarde), y expander para fijar fechas a mano. Lo ya vencido no aparece y solo entran posiciones vivas: un bono que ya vendiste no te vence.
- **Verificado contra los datos reales de Franco:** próximo vencimiento **X30N6 el 30/11/2026 (117 días)**; 8 instrumentos ya vencidos que la tabla no muestra; `TZX28` como `2028`; `AE38` y `AL29` en `s/d`.
- **El test de nombres se ganó el sueldo:** `date` no estaba importado a nivel de módulo en `view.py` y `_vencimientos()` lo usaba. Lo cazó antes del deploy — mismo tipo de error que el `firma_val` y el `backup_db`.
- **Estado:** `tests/test_cartera_vencimientos.py` (29 tests). Suite **502 passed, 3 skipped** (local, con oráculos).
- ⏭️ **Sigue:** benchmark money-weighted contra SPY y Merval. La **TIR esperada y la duration siguen bloqueadas**: necesitan el cronograma de cupones y amortizaciones de cada bono, que no está ni en la app ni en el Excel (la hoja *Flujo de Fondos* tiene 3 instrumentos y **un** flujo cargado). Franco eligió **buscar una fuente automática** (data912 / IAMC / BYMA) — investigación pendiente.

## 2026-08-05 (corrección) — "Próximo vencimiento X30N6" era falso
- **Autor:** Claude (Opus 5). **Lo detectó Franco**: *"yo no tengo ese bono"*. Tenía razón.
- **El error fue del reporte, no del código.** La verificación se corrió con `v.resolver(...)` **sin pasarle la tenencia**, así que listó los 14 instrumentos de renta fija de la hoja `Config` tuviera o no posición. `proximos()` sí filtra por posiciones vivas cuando recibe `valuadas`, y el panel de la vista se lo pasa: X30N6 (cantidad 0, marcado inactivo en Config) **nunca se habría mostrado en la app**. Hay test que lo cubre (`test_solo_entra_lo_que_todavia_tenes`).
- ⚠️ **Lo que la corrección destapó, y es más importante que el error.** El "12 de 14 resuelven solos" era cierto pero **engañoso: 12 de esos 14 son instrumentos que Franco ya no tiene**. Su renta fija viva son tres cosas y el panel resuelve **una**:

  | Instrumento | Vencimiento | Estado |
  |---|---|---|
  | AN29 | 30/11/2029 | ✔ leído de la descripción |
  | AE38 | `s/d` | el año está en el *nombre* ("Bono USD 2038"), no como Vto. |
  | `#UMV060770008` | `s/d` | el pagaré no tiene descripción con fecha |

- 🧭 **Y para el AE38 la pregunta está mal planteada.** Ese bono **no vence hasta 2038 pero empieza a amortizar el 9/7/2027**: lo útil no es *cuándo vence* sino *cuándo cobra*. Para una cartera con soberanos amortizables, el vencimiento es un dato pobre y el **cronograma de cupones y amortizaciones** es el dato real. Eso refuerza la prioridad de la investigación de fuentes (data912 / IAMC / BYMA) por encima de seguir puliendo este panel.
- **Regla de verificación que queda:** al validar una feature que filtra por tenencia, **correrla con la tenencia puesta**. Un listado sin filtrar se ve igual de plausible y no lo es.
