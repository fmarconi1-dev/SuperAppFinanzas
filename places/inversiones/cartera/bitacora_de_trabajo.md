# Bitácora — B.1 — Dashboard de Cartera

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: 2026-07-23 -->

## Estado del módulo
**Fase de implementación:** Fase 3a / 6
**Situación:** 🟢 Fase 3a funcional — pasos 1 a 4 hechos (parser · M9+ingest+recon · market_data · **vista de Cartera con upload**). La cartera ya vive en la app. Falta el paso 5 (recon USD modo MEP actual) para cerrar la fase

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
