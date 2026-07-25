# ADR-0004 — Fuente del MEP histórico (corrige un supuesto del ADR-0003)

**Fecha:** 2026-07-23 · **Estado:** aceptada · **Fase:** 3a (paso 3, `core/market_data`)

## Contexto
El ADR-0003 fijó **TC MEP histórico por operación** y anotó la fuente como
*"(serie MEP, BCRA)"*. Al construir `core/market_data` se comprobó que ese
supuesto es **falso**: el BCRA **no publica el MEP**. Su API v4.0
(`estadisticas/v4.0/Monetarias`) expone el **mayorista A3500** (id 5), que al
22/7/2026 marcaba **1.480,86** contra un MEP de **1.521,9** — ~3% de brecha.
Usar A3500 subvaluaría las compras en dólares y se apartaría de la metodología
del Excel, que valúa con MEP.

Alternativas evaluadas:

1. **`argentinadatos` (MEP "bolsa")** — serie diaria desde 2018. Verificada
   contra el historial real: **419/419 días hábiles cubiertos, sin faltantes**;
   al 24/7 marca 1.533,5, coherente con el 1.519,725 de la tenencia del broker.
   Comunitaria (no oficial).
2. **BCRA A3500** — oficial y estable, pero es otro tipo de cambio (mayorista).
   Descartada: distorsiona los números respecto del Excel.
3. **Derivar de AL30/AL30D** (`MEP = precio_ARS / precio_USD`) — la definición
   pura. Descartada por ahora: no se encontró fuente **histórica** gratuita y
   estable de esos precios (`data912` sirve datos *live*, no series).

## Decisión
Tomar el MEP histórico de **`argentinadatos`** (`/v1/cotizaciones/dolares/bolsa`),
con los tres resguardos que ya exige el repo para fuentes comunitarias:

- **Congelado por fila:** el TC se graba en `cartera_movimientos.tc_mep` al
  importar. Una caída futura de la API **no altera** los movimientos ya
  importados — el dato histórico es inmutable por diseño.
- **Caché en DB** (`cartera_precios_cache`, ticker `MEP`): si la API no
  responde, se sirve la serie cacheada.
- **Override manual:** se puede fijar el TC de una fecha a mano
  (`es_override=1`), y el override gana sobre cualquier proveedor.

Para fechas sin cotización (fin de semana, feriado) se usa el **último día
hábil anterior con dato**, que es el criterio del mercado.

## Consecuencias
- ✔ Se mantiene la decisión de fondo del ADR-0003 (TC histórico por operación,
  más fiel que el "MEP actual para todo" del Excel); solo cambia el proveedor.
- ✔ La reconciliación contra el Excel sigue siendo posible: el Excel valúa con
  MEP actual único, así que el recon en USD se corre en modo "MEP actual"
  (según ADR-0003) y el modo histórico es la vista propia de la app.
- ✖ Se depende de una API comunitaria para el *backfill* inicial. Mitigado por
  el congelado + caché + override. Si `argentinadatos` desapareciera, el
  histórico ya importado queda intacto y solo haría falta fuente para fechas
  nuevas.
- La decisión definitiva del stack de datos de mercado sigue siendo de Fase 5
  (`docs/DATOS-MERCADO-ARG.md`); este ADR resuelve solo el MEP histórico de 3a.
