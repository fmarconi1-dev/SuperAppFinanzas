# Fase 2 · Frente 5 — Imágenes, fuentes y scripts (22/10/2026)

Anteriores: `LINEA-BASE.md` y `FRENTE-1` a `FRENTE-4`. Datos crudos y la captura comparada: `frente-5/`.

**Cierra sin cambios en el código de la app.** Se midió todo; lo único que movía algo cambiaba cómo se ve, y Franco decidió dejarlo como está.

## Inventario

| Asset | Qué hay | Veredicto |
|---|---|---|
| Imágenes | `logo.svg` (877 B) inline como data URI, con `width`/`height` (no corre el layout); `favicon.png` 6,5 KB | nada que ganar: no hay fotos ni PNG grandes, WebP/AVIF no aplica |
| Scripts | ninguno propio; el JS es todo de Streamlit (frente 2) | nada para `defer`/`async` |
| CSS inyectado | ~15 KB por click (`_styles.py` + `_responsive.py`), ~4 KB comprimido; minificado ahorraría ~1,5 KB comprimido por click | no vale la pena |
| Fuentes | `@import` de Google Fonts (Inter, Space Grotesk, JetBrains Mono) dentro del CSS inyectado + las de Streamlit (Source Sans 166 KB, Material Symbols 360 KB, a veces Source Code 88 KB) | se probó la alternativa: ver abajo |

Material Symbols hace falta: son los íconos de la navegación y las pestañas.

## Lo que se probó con las fuentes

Streamlit 1.58 deja declarar las fuentes en `.streamlit/config.toml` (`font`, `headingFont`, `codeFont`, con la URL de Google Fonts). Se probó con las mismas familias y pesos del `@import`, A/B en Chrome headless con caché fría (dos pasadas, orden A-B-B-A; `scripts/perf/probar_fuentes.py`, `probar_cls.py`, `medir_frontend.py`):

| | A (hoy) | B (fuentes en la config) |
|---|---|---|
| Fuentes de Google listas | ~2.960 ms | **~730 ms** |
| Bytes de fuentes | 543 KB | 543 KB (Source Sans se sigue bajando: Streamlit la pone de respaldo detrás de cada fuente) |
| Requests | 22 / 35 | 24 / 37 (tres CSS de Google en vez de uno) |
| CLS Inicio / Finanzas | 0,138–0,177 / 0,142–0,143 | 0,178–0,204 / 0,149–0,150 |
| FCP, LCP, contenido estable | — | dentro del ruido |

**El CLS no es de las fuentes** (`probar_cls.py`): el corrimiento grande (0,07–0,16) es el CSS inyectado cayendo sobre la primera pintada, y el segundo (0,057) son los bloques del Inicio apareciendo de a uno mientras Streamlit los manda. Ninguno coincide con la llegada de una fuente.

**Lo que B sí cambiaba**: el texto deja de mostrarse ~2 s con la letra de respaldo antes de pasar a Inter. Pero también cambia cómo se ve.

## Un hallazgo de diseño (no de rendimiento)

**Hoy los títulos y los textos chicos (captions) se ven en Source Sans**, la fuente de Streamlit, no en Space Grotesk / Inter como dice el sistema de diseño (`_styles.py`): el CSS de Streamlit le gana en especificidad al nuestro. Con B se veían como estaba pensado. Captura: `frente-5/fuentes_AB.png` (arriba hoy, abajo B).

**Decisión de Franco (22/10/2026): volver a como está hoy.** Se revirtieron `config.toml` y `_styles.py`. Si algún día se quiere el sistema de diseño tal cual, la vía medida es la de B.

## Herramientas que quedan

- `scripts/perf/probar_fuentes.py`: qué archivos de fuentes se bajan, cuáles se usan y con qué fuente se dibuja cada elemento (incluye "qué texto visible está en Source Sans").
- `scripts/perf/probar_cls.py`: cada corrimiento del layout con los nodos que se movieron y cuándo terminó de bajar cada fuente.
- `scripts/perf/probar_runtime.py` ya no corre sus pruebas al importarlo (lo importan los otros dos y `probar_cache_runtime.py`).

## Tests

999 passed, 0 skipped (sin cambios en la app).
