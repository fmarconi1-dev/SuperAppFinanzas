# Datos de mercado argentino — investigación

> **Bloqueante de la sección "Mercado en vivo" (B.3) y de la cartera con precios automáticos.**
> Hoy los precios (MEP, bonos, CEDEARs, ONs) se cargan **a mano** en el Excel. Este documento define de dónde los tomará la app.

## Estado
🟢 **Candidatos identificados** — vía el repo público [`gauss314/skills`](https://github.com/gauss314/skills) (skills compatibles con el estándar SKILL.md / skills.sh, licencia MIT, desarrolladas para los cursos de IA de la UCEMA). Falta validar y elegir la combinación definitiva en Fase 5 (y usar algunas antes, en Fase 3).

## Requisitos
- Precios de cierre y (deseable) intradía de: acciones panel líder, bonos soberanos, CEDEARs, ONs, letras.
- Tipo de cambio MEP / CCL.
- Estabilidad y, si es posible, gratis o barato.

## Fuentes candidatas (de `gauss314/skills`)

### Argentina (todas gratis, sin API key salvo aclaración)
| Skill | Cubre | Uso en la superapp |
|---|---|---|
| **`bcra-macro`** | API oficial BCRA: MEP, CCL, CER, UVA, tasas (BADLAR, política monetaria), reservas, base monetaria. Desde 1996. | Reemplaza los inputs manuales del Excel (MEP en `Apoyo!G15`, CER, UVA, tasas para renta fija). **Oficial → confiable.** |
| **`data912`** | Mercado AR **en vivo** (refresh ~20s): acciones locales, CEDEARs, bonos, letras, opciones, MEP, CCL. Histórico OHLCV + screener. | **Motor de "Mercado en vivo" (B.3)** y de precios automáticos de la cartera. |
| **`byma`** | Bolsa AR completa: panel líder, CEDEARs, soberanos + LECAPs/BONCAPs, ONs, cauciones, opciones. **Ficha técnica de bono con cronograma de amortización.** OHLCV histórico (MERVAL, BURCAP). | Precios y datos de la **cartera** (B.1); el cronograma de amortización alimenta los flujos de fondos de renta fija. |
| **`mae`** | Mayorista: renta fija (LECAPs, BONCAPs, BOPREALes, hard-dollar, ONs), cauciones, REPO, FX mayorista, **flujos de fondos para curvas TIR/MD**. | Alimenta la lógica de **renta fija** (equivalente a las hojas FF/TIRES de `Renta fija ARG.xlsx`). |
| **`cafci`** | Fondos comunes de inversión (VCP, patrimonio, TNA por período, cartera). | Opcional, si se agregan FCI a la cartera. |
| **`indec`** | API oficial de Series de Tiempo del Estado: IPC (inflación), EMAE, dólar, reservas, REM. **La más estable y documentada del repo.** | Contexto macro para el dashboard. **Oficial → confiable.** |

### Globales (para scoring y análisis)
| Skill | Uso |
|---|---|
| **`yahoo-finance`** | Ya usado por Scoring-Inversiones; base del scoring técnico/fundamental. |
| **`sec-data`** | Fundamentals de filings SEC (10K/10Q). Insumo del scoring y del agente de tesis. |
| **`morningstar`** | Incluye CEDEARs argentinos (XBUE) + 39 países; 33 campos por listing (ratios, retornos, sector). |
| **`tradingview`** | Screener global con ~300 columnas (RSI/MACD/EMAs, ratings, financials). |
| **`google-finance`** | Quotes BCBA + OHLC intradía 1-min gratis; recomendaciones de analistas. |
| **`fred-macro`** | 840k+ series macro de la Fed (contexto internacional). |

### Herramientas (cálculo)
| Skill | Uso |
|---|---|
| **`option-pricing`** | Black-Scholes, binomial CRR, Monte Carlo, griegas, vol implícita. **Reemplaza `opciones argy.xlsx`.** |
| **`backtesting`** | 30+ ratios de riesgo, Altman Z, Piotroski, DuPont, Markowitz. **Enriquece el scoring** y el análisis de cartera. |

## ⚠️ Caveats de confiabilidad (honestidad)
- **Oficiales y estables:** `bcra-macro`, `indec` (APIs oficiales del Estado/BCRA). Preferir estas como base.
- **APIs comunitarias / no oficiales:** `data912`, `byma`, `mae` funcionan bien pero pueden cambiar o cortar sin aviso. Diseñar `core/market_data/` con: (a) capa de abstracción por proveedor, (b) caché local, (c) **fallback a carga manual** (subir el panel a `data/`) si una fuente se cae. Esto respeta el mandato del premortem: no prometer "tiempo real" sin resguardo.
- **Scrapers globales** (`investing`, `tradingview`, `google-finance`): útiles pero frágiles; usar con caché y como complemento, no como única fuente.

## Cómo se usan estas skills
Son skills del estándar SKILL.md; se instalan con `npx skills add gauss314/skills --skill <nombre>`. Dos modos de uso en el proyecto:
1. **Durante el desarrollo:** el Claude que construya `core/market_data/` las usa como referencia/implementación de cada proveedor.
2. **En la app:** portar la lógica de fetch a módulos propios en `core/market_data/` (respetando la licencia MIT), con la capa de abstracción + caché + fallback descrita arriba.

## Decisión
_(pendiente de Fase 6 — registrar como ADR cuando se elija la combinación final. Recomendación inicial: `bcra-macro` + `data912` + `byma` + `mae` para AR; `option-pricing` + `backtesting` como herramientas; `yahoo-finance` + `sec-data` para el scoring.)_

### Resuelto en Fase 3a (2026-07-23) — `core/market_data`
Lo que la **cartera** necesita ya está implementado y verificado contra las APIs reales:

| Necesidad | Fuente elegida | Estado |
|---|---|---|
| **MEP histórico** (congelar TC por operación) | **`argentinadatos`** `/v1/cotizaciones/dolares/bolsa` → **ADR-0004** | ✅ serie 2018→hoy; **419/419 días hábiles** del historial de Franco, sin faltantes |
| Precios ARG (acciones, CEDEARs, bonos) | **`data912`** `/live/{arg_stocks,arg_cedears,arg_bonds}` | ✅ ~1.200 símbolos vivos |
| BTC / exterior | **`yahoo`** `/v8/finance/chart/{symbol}` | ✅ |

⚠️ **Hallazgo importante: el BCRA NO publica el MEP.** Su API v4.0 sirve el **mayorista A3500** (id 5): 1.480,86 vs MEP 1.521,9 al 22/7/2026 (~3% de brecha). El supuesto original del ADR-0003 ("serie MEP, BCRA") era incorrecto → corregido en **ADR-0004**. `bcra-macro` sigue siendo la fuente oficial para CER/UVA/tasas (renta fija, futuras fases).

**Normalización relevante:** `data912` sirve bonos/letras **por cada 100 nominales** (AE38 = 127.360 donde el broker muestra 1.262,6) → los instrumentos con `moneda_cotiz` terminada en `/100` se dividen por 100, misma regla que el LEEME del Excel.

Resguardos implementados (regla del repo — nada de "tiempo real" sin red de contención): capa por proveedor, **caché en DB**, **override manual** que gana sobre cualquier fuente, y **congelado del TC por fila** (una caída futura no altera lo ya importado). Todo con `fetch` inyectable → los tests corren sin red.

## Fuentes marcadas por Franco
- [`gauss314/skills`](https://github.com/gauss314/skills) — el repo clave (arriba).
- 4 posts de X (`@anyelamarillo`, `@0xjokker`, `@_guillecasaus`, `@untalnixon_exe`) — no se pudieron leer automáticamente (requieren login/JS). Revisar manualmente y agregar acá lo que aporte.
