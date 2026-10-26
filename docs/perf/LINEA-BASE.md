# Línea base de rendimiento (Fase 1) — 21/10/2026

Medido **antes de tocar código**. La Fase 3 tiene que correr exactamente lo mismo
(`scripts/perf/`) en las mismas condiciones para que el delta valga.

## Condiciones

| | |
|---|---|
| Código | `main` @ `5872a08` (con `.mapa/mapa.json` sin commitear, no afecta) |
| Base | **sintética**, `scripts/perf/generar_base.py` (seed 42): 1 usuario, 4 años, **5.320 movimientos**. Las fechas son relativas a hoy: los números del mes en curso cambian con el día, los tiempos no deberían |
| App | Streamlit 1.58.0 local, `127.0.0.1:8599`, sin `APPS_SCRIPT_URL` (agenda apagada) |
| Navegador | Chrome 152 headless (`--headless=new`), **perfil nuevo por corrida = caché fría**, ventana 1350×940 |
| Corridas | 3 por página y perfil, se reporta la **mediana** |
| Ventana de observación | 14 s desktop · 90 s móvil |
| Perfil "móvil Lighthouse" | CPU 4× más lenta, RTT 150 ms, 1,6 Mbps bajada / 750 kbps subida (lo que simula Lighthouse mobile) |
| PC | la de Franco, sin otra carga pesada corriendo |

**No es Lighthouse** (no hay Node en la PC): mismas definiciones de métricas
(FCP, LCP, CLS, TBT) tomadas por CDP, sin el puntaje 0–100.

**Métrica principal para Streamlit: "contenido estable"** = último cambio del DOM.
El LCP salta con el primer título y no ve que la pantalla sigue armándose varios
segundos más por el websocket.

**Compresión:** local, Streamlit no comprime (transferido ≈ decodificado).
Producción (Fly) sirve Brotli + `cache-control: immutable, 1 año`. Los KB locales
son *sin comprimir*; los de producción están en su tabla aparte.

## Frontend

| Métrica (mediana) | Inicio desktop | Finanzas desktop | Inicio móvil | Finanzas móvil |
|---|---:|---:|---:|---:|
| TTFB | 8 ms | 10 ms | 9 ms | 10 ms |
| FCP | 448 ms | 492 ms | 13,95 s | 14,50 s |
| LCP | 508 ms | 724 ms | 14,84 s | 18,15 s |
| **Contenido estable** | **2,15 s** | **4,77 s** | **22,6 s** | **56,7 s** |
| CLS | 0,177 | 0,144 | 0,143 | 0,158 |
| TBT | 0 ms | 716 ms | 770 ms | 5.283 ms |
| Long task más larga | — | 386 ms | 465 ms | 1.666 ms |
| Requests | 22 | 54 | 22 | 54 |
| Bajado por red (sin comprimir) | 3,93 MB | 10,07 MB | 3,93 MB | 10,07 MB |
| de eso JS | 3,19 MB | 9,19 MB | | |
| de eso fuentes | 614 KB | 526 KB | | |
| Websocket (deltas de Streamlit) | 36 frames / 21 KB | 220 frames / 247 KB | | |
| Nodos DOM | 297 | 2.774 | | |

Recursos más pesados en Finanzas (local, sin comprimir → producción con Brotli):

| Recurso | Local | Producción |
|---|---:|---:|
| `PlotlyChart.*.js` | 4.553 KB | 1.602 KB |
| `index.*.js` (núcleo Streamlit) | 2.309 KB | 660 KB |
| `embed.*.js` | 774 KB | 312 KB |
| `pandasStylerUtils.*.js` | 716 KB | 61 KB |
| `DataFrame.*.js` | 429 KB | 168 KB |
| `MaterialSymbols-Rounded.woff2` | 360 KB | 359 KB |
| `/media/*.xlsx` (el export de Configuración) | 231 KB | — |
| Google Fonts (CSS por `@import` + 3 familias) | externo, bloquea el render del CSS | |

Producción, ida y vuelta medida desde la PC: `/_stcore/health` 256 ms TTFB, `/api/health` 256 ms.

## Backend (AppTest, sin navegador, misma base)

| Pantalla | Primer render | **Rerun** (cualquier click) | Conexiones / rerun | Sentencias / rerun (PRAGMA) | SQL / rerun |
|---|---:|---:|---:|---:|---:|
| Shell + Inicio | 1.452 ms | **60 ms** | 5 | 30 (15) | 25 ms |
| Finanzas (5 pestañas) | 1.246 ms | **1.176 ms** | 22 | 116 (66) | 121 ms |

SQL = las SELECT capturadas y reejecutadas aparte: aproximado, ~10 % del rerun de Finanzas.

Consultas repetidas en **un** render de Finanzas: categorías 11×, `saldo_inicial_caja` 6×,
`tutorial_completado` 5×, **transacciones completas 5×** (89 ms de los 121), `fondo_emergencia_usd` 3×,
workspace personal 3×.

Planes: todas usan índice por `workspace_id`; las dos lecturas de transacciones ordenan con
`USE TEMP B-TREE FOR ORDER BY` (no hay índice `(workspace_id, fecha, id)`).

Funciones sueltas (mediana de 5): `load_transactions` 13 ms · `compute_kpis` 134 ms ·
`resumen_del_mes` 47 ms · `saldo_cuenta_corriente` 0,5 ms · bot `procesar("resumen")` 24 ms.

## Dónde se va un render de Finanzas (cProfile; solo proporciones, cProfile infla ~2,5×)

| | Parte del render |
|---|---:|
| `configuracion.render` → `export_xlsx` (arma el Excel entero **en cada rerun**) | ~74 % |
| `_aplicar_grupo_efectivo` (`iterrows` sobre todas las filas, 5 veces) | ~16 % |
| `diario.render` → `libro_diario` | ~14 % |
| `dashboard.render` | ~8 % |
| pandas, por librería | ~38 % del tiempo propio |

(Se superponen: el export llama a `compute_kpis`, que llama a `_aplicar_grupo_efectivo`.)

## Renders

- `st.tabs` dibuja **las 5 pestañas en cada rerun**, se vea la que se vea: un click en Inicio cuesta 60 ms, en Finanzas 1,2 s.
- 0 `st.cache_data` en Finanzas (el único es la agenda del Inicio) y 0 `st.fragment`.
- 21 widgets que disparan rerun en las vistas de Finanzas (5 en el Dashboard), 4 forms.
- ~30 `st.rerun()` explícitos: cada uno duplica el costo del click que lo dispara.

## Cómo repetir

```bash
.venv/Scripts/python.exe scripts/perf/generar_base.py . <carpeta>/sintetica.db
.venv/Scripts/python.exe scripts/perf/medir_backend.py . <carpeta>/sintetica.db <carpeta>/backend.json
.venv/Scripts/python.exe scripts/perf/perfil_finanzas.py . <carpeta>/sintetica.db
# app local: DB_PATH=<copia de la sintética> SESSION_SECRET=<uno nuevo> streamlit run app.py --server.address 127.0.0.1 --server.port 8599 --server.headless true
# token: issue_token(1) de core/auth/session_tokens.py con ese mismo secret
.venv/Scripts/python.exe scripts/perf/medir_frontend.py "http://127.0.0.1:8599/?s=<token>" <carpeta>/front.json
```

Medir de a una cosa (frontend y backend en paralelo se ensucian entre sí). En Windows,
cerrar la página antes de matar Chrome (el script lo hace): si no, el `accept` de asyncio
tira `WinError 64` y el servidor deja de atender.
