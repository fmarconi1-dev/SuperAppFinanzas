# Reporte de impacto — auditoría de rendimiento (21–26/10/2026)

**Antes** = `main` @ `5872a08` (el código de la línea base, `LINEA-BASE.md`). **Después** = ese mismo commit + los frentes 1 a 4, **sin commitear ni desplegar**. El frente 5 cerró sin cambios en la app. Datos crudos: `fase-3/`.

## En una línea

**Un click en Finanzas pasó de ~2 s a 30–70 ms en el servidor (−96 a −99 %)** cuando no cambió nada, y a ~155 ms en el Dashboard justo después de cargar algo (−92 %). Los ~2 s de "antes" son el código viejo con la PC de hoy; el día de la línea base, con la PC menos cargada, eran 1,2 s. El bot arranca 4 veces más rápido después de que Fly apaga la máquina, y la primera carga de Finanzas baja 1,6 MB menos y queda estable un 29 % antes. Lo que no se movió es la primera carga del Inicio en un celular lento: la domina el JavaScript de Streamlit, que no es nuestro.

## Cómo se midió (y por qué así)

- **Mismas herramientas que la Fase 1** (`scripts/perf/`): `medir_backend.py` (AppTest), `medir_frontend.py` (Chrome por CDP, perfil nuevo = caché fría, desktop y móvil con el throttling de Lighthouse) y, para el arranque en frío, `medir_arranque.py`. Misma base sintética (`generar_base.py`, seed 42, 5.320 movimientos), misma PC.
- **Antes y después corrieron intercalados, el mismo día** (A, B, A, B; el frontend en orden A-B-B-A). Entre el 21 y el 26/10 la carga de la PC varió hasta 3× y Chrome se actualizó solo (152 → 156): comparar contra los números del 21/10 habría mezclado eso con las mejoras. Los números de `LINEA-BASE.md` quedan como contexto, no como "antes".
- Se reportan medias de dos pasadas (backend, desktop) o la mediana de 5 procesos (arranque) o de 3 corridas (móvil).
- **No es Lighthouse** (no hay Node en la PC): mismas métricas por CDP, sin el puntaje. La métrica principal del navegador es **"contenido estable"** (último cambio del DOM): el LCP salta con el primer título y no ve que Streamlit sigue dibujando.
- Local, Streamlit no comprime: los KB del navegador son **sin comprimir**. Producción sirve Brotli; donde importa, va la estimación comprimida.
- Dos errores de las herramientas aparecieron y se corrigieron en esta fase: el token de sesión de prueba había vencido (la primera corrida de frontend midió la pantalla de login; se descartó, y `medir_frontend.py` ahora verifica que la pantalla sea la pedida), y el escenario "primer gasto" de `medir_arranque.py` mandaba un texto que el bot rechaza (ahora manda `3500, Compras` y verifica el "Cargado").

## 1. Lo que cuesta cada click (servidor, AppTest)

| Pantalla | Click sin cambios | Click justo después de cargar algo | Primera vez que se abre |
|---|---:|---:|---:|
| Inicio | 115 → **19 ms (−84 %)** | 97 → 86 ms (−12 %) | 3.151 → 1.592 ms (−49 %) |
| Finanzas · Dashboard (la que abre) | 2.023 → **67 ms (−97 %)** | 1.994 → **155 ms (−92 %)** | 2.209 → 150 ms (−93 %) |
| Finanzas · Transacciones | 1.997 → **33 ms (−98 %)** | 2.125 → 37 ms (−98 %) | 1.973 → 41 ms (−98 %) |
| Finanzas · Diario | 2.027 → **29 ms (−99 %)** | 2.034 → 57 ms (−97 %) | 2.208 → 72 ms (−97 %) |
| Finanzas · Mensual | 2.004 → **71 ms (−96 %)** | 2.008 → 71 ms (−96 %) | 2.013 → 81 ms (−96 %) |
| Finanzas · Configuración | 2.006 → **31 ms (−98 %)** | 2.002 → 34 ms (−98 %) | 1.988 → 38 ms (−98 %) |

En producción cada click suma además la ida y vuelta por internet (~250 ms), que no cambió.

## 2. Base de datos

**Consultas que se dejaron de hacer** (un click sin cambios en el Dashboard; la mayor parte es la caché del frente 3, que no pregunta, y las pestañas que ya no corren):

| | Antes | Después | Δ |
|---|---:|---:|---:|
| Conexiones | 22 | 3 | −86 % |
| Sentencias SQL (de ellas PRAGMA) | 116 (66) | 17 (11) | −85 % |
| Tiempo en SQL de ese click (reproducido) | ~190 ms | ~4,5 ms | −98 % |
| Veces que se leen todas las transacciones | 5 | 0 (con caché) / 1 (después de cargar algo) | |

**Latencia de cada consulta o cálculo** (lo que tarda cuando sí hay que hacerlo):

| Consulta o cálculo | Antes | Después | Δ |
|---|---:|---:|---:|
| Últimos 5 movimientos (M25) | 2,68 ms | 0,02 ms | −99 % |
| Leer todas las transacciones (M25) | 26,6 ms | 20,1 ms | −24 % |
| `compute_kpis` de toda la historia (sin `iterrows`) | 221 ms | 15 ms | **−93 %** |
| Resumen del mes del Inicio | 75,5 ms | 62,9 ms | −17 % |
| `resumen` del bot | 41 ms | 36 ms | −11 % |

No había un N+1 de SQL clásico: las búsquedas por fila del bot ya usaban índice. El "N+1" de esta app era pandas recorriendo toda la historia fila por fila (frente 4).

## 3. Arranque en frío (después de que Fly apaga la máquina)

| Escenario, proceso nuevo | Antes | Después | Δ |
|---|---:|---:|---:|
| La API (el bot) arranca | 1.206 ms | 279 ms | **−77 %** |
| Arranca + **primer gasto** por WhatsApp | 1.225 ms | 315 ms | **−74 %** |
| Arranca + primer `resumen` | 1.225 ms | 937 ms | −24 % (pandas se paga en ese mensaje) |
| Primer Inicio de la app | 1.857 ms | 1.471 ms | −21 % |
| Primera vez que se abre Finanzas | 3.656 ms | 1.457 ms | **−60 %** |

## 4. Navegador — primera carga, caché fría

**Desktop, sin throttling:**

| Finanzas | Antes | Después | Δ |
|---|---:|---:|---:|
| **Contenido estable** | 7,01 s | 4,97 s | **−29 %** |
| TBT | 1.031 ms | 862 ms | −16 % |
| Requests | 54 | 35 | −35 % |
| Bajado por red (sin comprimir) | 10,07 MB | 8,45 MB | **−1,62 MB (−16 %)** |
| de eso JS | 9,19 MB | 7,81 MB | −1,38 MB |
| Mensajes del websocket | 220 (244 KB) | 74 (203 KB) | −66 % |
| Nodos DOM | 2.774 | 1.324 | −52 % |
| FCP | 0,80 s | 0,80 s | = |
| LCP | 1,26 / 1,14 s | 1,31 / 3,06 s | sin mejora (una corrida atípica en "después") |
| CLS | 0,14 | 0,16 | = |

El LCP de Streamlit se dispara con el primer título y no ve el resto del dibujo (por eso la métrica principal es "contenido estable", desde la línea base); la corrida de 3,06 s es una sola de dos, pero no hay mejora que reportar.

En el Inicio, desktop: contenido estable 4,08 → 2,98 s (−27 %); bytes, requests, FCP, LCP y CLS iguales. Parte de esa mejora es la caché del frente 3, que es de todo el proceso: una visita encuentra lo que calculó la anterior (así se comporta también en producción, salvo la primera visita después de un arranque).

**Móvil (CPU 4×, 150 ms, 1,6 Mbps):**

| | Antes | Después | Δ |
|---|---:|---:|---:|
| Finanzas · FCP / LCP | 14,8 / 19,1 s | 14,8 / 18,5 s | = / −3 % |
| Finanzas · contenido estable | 58,6 s | 50,3 s | −14 % |
| Finanzas · TBT | 7,29 s | 4,55 s | **−38 %** |
| Finanzas · tarea larga más larga | 2,29 s | 1,76 s | −23 % |
| Inicio (FCP 14,2 s, LCP 15,1 s, contenido estable 23,0 s, CLS 0,14) | | | = en todo |

**Ahorro en producción (estimado con los tamaños Brotli medidos el 21/10):** la primera carga del Dashboard deja de bajar los chunks de tablas (`pandasStylerUtils` 62 KB y `DataFrame` 168 KB comprimidos, más ~0,24 MB sin comprimir de dependencias, ~70 KB comprimidas) y el Excel de 231 KB que se armaba en cada carga, que ya es un formato comprimido y pesa lo mismo en producción: **~0,5 MB menos por primera carga de Finanzas**.

## Qué se hizo, por frente

| Frente | Cambio | Detalle |
|---|---|---|
| 1 · Renders | solo corre la pestaña abierta; el Excel se arma al descargar; dos fragmentos en el Dashboard; los filtros sobreviven al cambiar de pestaña | `FRENTE-1-RENDERS.md` |
| 2 · Bundle / carga diferida | openpyxl, pandas del bot y las vistas de Finanzas se importan cuando hacen falta (Plotly se quedó: decisión de Franco) | `FRENTE-2-CARGA-DIFERIDA.md` |
| 3 · Requests y caché | caché por versión de la base (`version_datos`, ve lo que escribe el bot desde otro proceso) en Inicio, Dashboard y Diario | `FRENTE-3-CACHE.md` |
| 4 · Queries y N+1 | `grupos_efectivos` en vez de `iterrows` (resultados idénticos); M25, índice por fecha | `FRENTE-4-QUERIES.md` |
| 5 · Assets | sin cambios: nada que ganar en imágenes y scripts; las fuentes en la config cambiaban cómo se ve (Franco eligió dejarlas) | `FRENTE-5-ASSETS.md` |

## Lo que no cambió y por qué

- **La primera carga del Inicio en un celular lento** (~23 s locales sin comprimir; bastante menos en producción con Brotli y caché de 1 año): la dominan los ~3,2 MB de JavaScript de Streamlit, iguales para cualquier app Streamlit.
- **La primera carga del Dashboard sigue bajando Plotly** (4,5 MB sin comprimir, 1,6 MB en producción). Pasar los gráficos a los nativos de Streamlit ahorraba ~1,3 MB comprimidos; se decidió no hacerlo.
- **El CLS (~0,14–0,18)**: lo causan el CSS inyectado cayendo sobre la primera pintada y los bloques del Inicio apareciendo de a uno, no las fuentes (`FRENTE-5-ASSETS.md`).
- **El ~cuarto de segundo de red por click en producción.**

## Lo que falta para que esto llegue a producción

1. Commitear (está todo en `main`, sin commitear) y desplegar. M25 corre sola al arrancar: crea un índice, no toca datos.
2. Medir en Fly lo que se pueda medir allá (el arranque en frío y un click reales). Lo de este reporte es local, con base sintética: los porcentajes deberían trasladarse; los milisegundos, no (la CPU de Fly es otra).

Tests: 999 passed, 0 skipped.
