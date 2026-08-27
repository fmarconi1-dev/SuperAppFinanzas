# core/market_data/

<!-- huella: a596d2255df5 -->

Resumen: Datos de mercado para valuar la cartera: MEP histórico (argentinadatos), precios ARG (data912) y globales (yahoo), sectores por ticker y cronogramas de renta fija (Docta).

## Buscar acá si

- dólar MEP histórico o de hoy, el TC congelado por operación (`mep.py`)
- un precio falta o viene raro: bonos ×100, override, caché (`precios.py`)
- sector/industria de un ticker para el análisis de composición (`sectores.py`)
- cronogramas de pago, cupones, Docta (`cronogramas.py`, `DOCTA_CLIENT_ID/SECRET`)
- una fuente externa caída y qué fallback aplica
- la serie histórica de un índice para comparar contra la cartera (`indices.py`)

## Qué hay acá

- `mep.py` — serie histórica MEP con último hábil anterior, caché y override (ADR-0004).
- `precios.py` — data912 (ARG) + yahoo (BTC/exterior); precedencia override → caché → proveedor; normaliza bonos /100.
- `sectores.py` — sector e industria vía Yahoo (100% Yahoo desde el retiro del scoring).
- `cronogramas.py` — flujos de renta fija desde la API de Docta, con caché en DB (M15).
- `indices.py` — series históricas de SPY y Merval (Yahoo) para el benchmark money-weighted de la cartera.

## Trampas

- **El BCRA no publica el MEP**: su API sirve el mayorista A3500 (~3% abajo). Fuente elegida: argentinadatos (ADR-0004).
- data912 sirve bonos ×100 (AE38 = 127.360 donde el broker muestra 1.262,6): `precios.py` normaliza /100.
- `fetch` es **inyectable**: los tests corren sin red. No metas `requests` directos.
- URLs vivas: api.doctacapital.com.ar, api.argentinadatos.com, data912.com, query1/query2.finance.yahoo.com.
- `indices.py` usa **`adjclose`, no `close`**: el cierre ajustado incluye dividendos reinvertidos. Comparar el rendimiento total de Franco contra un SPY sin dividendos le regalaría ~1,3% anual a la cartera.
- `indices.py` **no necesitó migración**: cachea en `cartera_precios_cache`, porque el cierre de un índice tiene exactamente la forma que esa tabla guarda (ticker, fecha, precio, moneda, fuente).
- El símbolo del Merval es `^MERV` y el `^` hay que **url-encodearlo** (`%5EMERV`) o Yahoo devuelve vacío.

## Estado

- **Funciona:** todo en producción; caché de cronogramas (M15) verificada contra la cuenta real.

## Proximo paso

—
