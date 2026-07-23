# Bitácora — B.1 — Dashboard de Cartera

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: 2026-07-23 -->

## Estado del módulo
**Fase de implementación:** Fase 3a / 6
**Situación:** 🔵 En curso — parser (paso 1) + modelo M9 + ingest + reconciliación hechos; Excel-oráculo actualizado y reconciliado 20/20 contra el broker. Sigue market_data (paso 3)

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
