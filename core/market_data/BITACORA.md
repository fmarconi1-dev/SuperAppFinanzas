# core/market_data/

<!-- huella: a4e54ac721d6 -->

Resumen: Datos de mercado para valuar la cartera: MEP histórico (argentinadatos), precios ARG (data912) y globales (yahoo), sectores por ticker y cronogramas de renta fija (Docta).

## Buscar acá si

- dólar MEP histórico o de hoy, el TC congelado por operación (`mep.py`)
- un precio falta o viene raro: bonos ×100, override, caché (`precios.py`)
- sector/industria de un ticker para el análisis de composición (`sectores.py`)
- cronogramas de pago, cupones, Docta (`cronogramas.py`, `DOCTA_CLIENT_ID/SECRET`)
- una fuente externa caída y qué fallback aplica

## Qué hay acá

- `mep.py` — serie histórica MEP con último hábil anterior, caché y override (ADR-0004).
- `precios.py` — data912 (ARG) + yahoo (BTC/exterior); precedencia override → caché → proveedor; normaliza bonos /100.
- `sectores.py` — sector e industria vía Yahoo (100% Yahoo desde el retiro del scoring).
- `cronogramas.py` — flujos de renta fija desde la API de Docta, con caché en DB (M15).

## Trampas

- **El BCRA no publica el MEP**: su API sirve el mayorista A3500 (~3% abajo). Fuente elegida: argentinadatos (ADR-0004).
- data912 sirve bonos ×100 (AE38 = 127.360 donde el broker muestra 1.262,6): `precios.py` normaliza /100.
- `fetch` es **inyectable**: los tests corren sin red. No metas `requests` directos.
- URLs vivas: api.doctacapital.com.ar, api.argentinadatos.com, data912.com, query1/query2.finance.yahoo.com.

## Estado

- **Funciona:** todo en producción; caché de cronogramas (M15) verificada contra la cuenta real.

## Proximo paso

—
