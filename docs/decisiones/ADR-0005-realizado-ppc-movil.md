# ADR-0005 — El resultado realizado se mide con el PPC vigente al vender

**Fecha:** 2026-07-30 · **Estado:** aceptada · **Fase:** 3b (paso 1-2, motor cronológico)
**Precisa (no reemplaza) el ADR-0003**, que fijó *"costo promedio ponderado (como el Excel). FIFO → MEJORAS"*.

## Contexto

`posiciones.py` calcula el resultado realizado así:

```python
realizado = ingreso_de_las_ventas − PPC_global × unidades_vendidas
```

donde `PPC_global = Σ costo de TODAS las compras / Σ TODAS las unidades
compradas`, sobre la historia completa. Es un port fiel del Excel (por eso el
gate de reconciliación pasa), pero tiene una consecuencia que el Excel también
arrastra: **el costo de una venta depende de hechos posteriores a esa venta.**

Medido sobre los datos reales de Franco (585 movimientos, 46 ventas), el
realizado en pesos cambia en **9 tickers**; el total pasa de **$3.297.014** a
**$3.145.965** (−$151.050, −4,6%). Dos mecanismos distintos:

1. **Eventos retroactivos.** `SPY` es el mayor desvío (−$688.510). El ajuste
   de ratio del CEDEAR entró como una **compra de 70 unidades a costo cero
   fechada el 23/7/2026**, tres meses **después** de la venta del 20/4/2026.
   Con PPC global esas unidades gratis diluyen el promedio de toda la historia
   (69 compradas por $2.754.458 + 70 gratis → PPC $19.672) y ese promedio
   diluido se aplica hacia atrás: la app informa **$1.122.268** de ganancia
   cuando el costo real de esas 35 unidades ese día era $39.343 c/u →
   **$433.757 (+31,5% en 143 días)**.
2. **Comprar, vender y recomprar más caro.** `TGNO4`: vendió 30 el 27/10/2025
   a $3.183 que había comprado a $3.132 → ganancia real de **$1.540 (+1,6%)**,
   pero la app informa **−$37.700 de pérdida** porque la compra de diciembre a
   $4.870 sube el promedio histórico. Ídem GGAL, ASML, VIST, NU, MELI, NVDA,
   BYMA.

## Decisión

El **resultado realizado** pasa a medirse con el **PPC vigente al momento de
cada venta**, calculado por el motor cronológico `ledger.py` (recorrido por
fecha con costo promedio móvil). Cada venta produce una `Realizacion` con su
fecha, unidades, costo liberado, resultado en ARS y USD, rendimiento % y días
de tenencia.

**Se mantiene el costo promedio ponderado** como método de costeo (ADR-0003):
no se adopta FIFO, que sigue en `MEJORAS.md`. Lo que cambia es *cuándo* se
promedia — al momento de cada operación, no al final de la historia.

**Lo que NO cambia:**

- **El gate de reconciliación** (`tests/test_cartera_recon.py`): compara
  **cantidades** y **costos en USD** contra `Resumen Cartera`, no el
  realizado. Sigue verde y sigue siendo el oráculo.
- **El patrimonio, el rendimiento total y la TIR**: se calculan por el método
  del patrimonio —`(tenencia + efectivo) − (depósitos − retiros)`— que **no
  suma operación por operación** y por lo tanto es inmune a esto.
- **El costo de la tenencia viva** (`costo_ars_posicion`) y el resultado no
  realizado: la posición que queda se sigue valuando al PPC promedio, que tras
  una venta a costo proporcional es el mismo número.

## Alternativas evaluadas

1. **Dejarlo como el Excel.** Ventaja: cero divergencia con la planilla.
   Descartada: la planilla informa pérdidas en operaciones que ganaron
   (TGNO4) y ganancias infladas en las que se cruzaron con un ajuste
   retroactivo (SPY). El Excel es el oráculo de *cantidades y costos*, no de
   la atribución por operación — para eso nunca tuvo cronología.
2. **FIFO.** Sería más preciso a efectos impositivos, pero rompe la
   continuidad con el ADR-0003 y con toda la reconciliación ya construida, y
   no es lo que Franco usa para pensar su cartera. Queda en `MEJORAS.md`.
3. **Corregir la fecha del ajuste de ratio de SPY en el crudo.** Arreglaría
   ese caso puntual y ninguno de los otros ocho. Además el problema volvería
   con cualquier evento retroactivo futuro (canjes, splits, nuevos ajustes).

## Consecuencias

- ✔ El resultado por operación deja de depender de lo que pasó después.
- ✔ Habilita los otros tres puntos de la Fase 3b: la amortización parcial es
  un evento más de la misma línea de tiempo, las cauciones y dividendos son
  eventos fechados con capital y plazo, y el análisis por sector agrupa lo
  anterior.
- ✔ Aparece información que antes no existía: **cuántos días** duró cada
  operación y su rendimiento en ese plazo.
- ✖ **Los números de realizado por ticker de la app dejan de coincidir con la
  columna equivalente del Excel.** Es deliberado y está documentado acá; el
  recon (cantidades + costos USD) sigue siendo la red.
- ✖ El motor depende de que las fechas de los movimientos sean correctas. Los
  registros sintéticos (saldos iniciales, ajuste de ratio) llevan una fecha
  elegida a mano: si esa fecha es posterior a una venta del mismo ticker, el
  motor la trata —correctamente— como un evento posterior. Las ventas que
  quedan **descubiertas** (más unidades vendidas que registradas) se marcan y
  se muestran, nunca se completan con costo inventado.
