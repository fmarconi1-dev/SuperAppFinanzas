# Fase 2 · Frente 2 — Bundle y carga diferida (21/10/2026)

Línea base: `LINEA-BASE.md`. Frente anterior: `FRENTE-1-RENDERS.md`. Datos crudos: `frente-2/`.

## Qué se podía tocar y qué no

- **El bundle de Streamlit no es nuestro.** `index.js` (2,3 MB) y `embed.js` (774 KB) los baja cualquier app Streamlit, aunque esté vacía (medido con una app mínima). Producción ya los sirve con Brotli y caché inmutable de 1 año.
- **El chunk de Plotly sí depende de nosotros: 4.553 KB** (1,6 MB comprimido) que el navegador baja y compila apenas aparece un gráfico. Los gráficos nativos de Streamlit (Vega-Lite) suman 1.370 KB, contando el chunk de tablas que traen. Pasar los 4 gráficos a Vega-Lite ahorraba ~3,2 MB sin comprimir (~1,3 MB comprimido) en la primera carga del Dashboard. **Franco decidió dejar Plotly** (21/10): no se tocó.
- **Lo que quedó: la carga diferida del lado de Python.** Fly apaga la máquina cuando no hay tráfico (`min_machines_running = 0`), así que después de un rato el primer mensaje de WhatsApp y la primera visita pagan el arranque entero de Python. Ahí se pagaban librerías que ese arranque no usaba.

## Qué cambió

| Cambio | Dónde | Lo que se dejó de pagar al arrancar |
|---|---|---|
| openpyxl se importa al leer un extracto | `places/finanzas/core/extracto_galicia.py` (`leer_extracto`) | ~0,2–0,3 s, en la API y en la app |
| `metrics` (y con él pandas) se importa al calcular totales | `places/finanzas/core/comandos.py` (`totales_mes`) | ~0,5 s en la API: cargar un gasto no usa pandas |
| Cada pestaña de Finanzas importa su vista al abrirse | `places/finanzas/home.py` (`PESTANAS` guarda el nombre del módulo) | el Inicio ya no trae las 5 vistas, ni Plotly Express ni el export |

`tests/test_arranque_liviano.py` lo vigila en un proceso nuevo: la API arranca sin pandas ni openpyxl, y Finanzas no importa sus vistas hasta abrir la pestaña. Se verificó que **falla con el código anterior**.

La base de Plotly (`plotly.graph_objects`, 5–7 ms) la importa el propio Streamlit: no se puede evitar ni vale la pena. Pandas sigue entrando con el Inicio, que lo necesita para sus números.

## Cómo se midió

`scripts/perf/medir_arranque.py`: cada escenario en un **proceso de Python nuevo** (como después de que Fly apaga la máquina), sobre copias de la base sintética. A = el código con el frente 1 y sin el frente 2; B = con los dos. Intercalados A, B, A, B, 5 veces cada uno, se reporta la mediana. El arranque del intérprete y el import de Streamlit son iguales en A y B y no se cuentan.

## Resultado (mediana de 5, ms)

| Escenario en frío | A | B | Δ |
|---|---:|---:|---:|
| La API arranca (`import api`) | 1.458 | 302 | **−79 %** |
| La API arranca + **primer gasto** por WhatsApp | 1.147 | 271 | **−76 %** |
| La API arranca + **primer `resumen`** | 1.141 | 887 | −22 % |
| Primer Inicio de la app | 1.761 | 1.414 | **−20 %** |
| Primera vez que se abre Finanzas (Dashboard) | 1.379 | 1.344 | = |

- ⚠️ **Corrección del 26/10/2026:** el escenario "primer gasto" mandaba `café 3500`, que el bot rechaza ("No encontré monto y categoría"): medía un mensaje rechazado, no una carga. La conclusión no cambia (lo que pesa es el arranque), pero el número bueno es el de la Fase 3, con `3500, Compras` y verificando el "Cargado": **1.225 → 315 ms (−74 %)** (`REPORTE-IMPACTO.md`).
- El `resumen` mejora menos porque pandas no se evita, se corre: lo paga ese mensaje (651 ms) en vez del arranque. El gasto no lo necesita nunca (13 ms de mensaje en A y en B).
- Finanzas da igual porque ahí sí hacen falta sus vistas: el costo pasa del arranque al primer click en Finanzas. Una vez por proceso.
- Pasada la primera vez, todo es igual que antes: Python no vuelve a importar.

## Probado en el runtime real

`scripts/perf/probar_runtime.py` contra la app local: las pestañas, los dos fragmentos y la descarga del Excel andan igual que en el frente 1, sin `Traceback` en el log.

## Tests

988 passed, 0 skipped.
