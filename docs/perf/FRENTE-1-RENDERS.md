# Fase 2 · Frente 1 — Renders innecesarios (21/10/2026)

Línea base: `LINEA-BASE.md`. Datos crudos de esta medición: `frente-1/`.

## Qué cambió

| Cambio | Dónde | Por qué |
|---|---|---|
| El Excel de Configuración se arma **al tocar "Descargar"**, no en cada rerun (`download_button(data=callable)`) | `places/finanzas/views/configuracion.py` (`_generador_excel`) | Era ~3/4 de cada rerun de Finanzas y viajaba al navegador (231 KB) en cada carga |
| Corre **solo la pestaña abierta** (`st.tabs(on_change="rerun")` + `.open`) | `places/finanzas/home.py` (`PESTANAS`, `CLAVE_PESTANA`) | Las 5 pestañas corrían en cada click, se viera la que se viera |
| Las medias móviles y "Agrupar por" son **fragmentos** (`@st.fragment`): tocarlos redibuja solo su gráfico | `places/finanzas/views/dashboard.py` (`_grafico_caja`, `_grafico_categorias`) | Cada uno rerunneaba el Dashboard entero y reenviaba los 3 gráficos |

Tres cosas que hay que saber:
- El generador del Excel y el fragmento de la Caja corren **sin los contextvars del script** (el Excel en otro hilo; el fragmento sin pasar por `app.py`): llevan el usuario y el workspace consigo. Sin eso, en un espacio familiar el Excel exportaría el personal. Lo cubre `test_el_excel_se_arma_al_descargar_con_el_workspace_activo`.
- Cambiar de pestaña ahora es un rerun (de esa sola pestaña): en producción suma la ida y vuelta (~250 ms). Antes era instantáneo pero cada click costaba 1,2 s.
- Streamlit borra el estado de un widget que no se dibujó: al volver al Dashboard los filtros estaban otra vez en "Este mes". Se encontró probándolo y se arregló con `FILTROS_QUE_PERSISTEN` en `home.py` (test `test_los_filtros_del_dashboard_sobreviven_a_cambiar_de_pestana`). Un formulario a medio llenar en otra pestaña sí se pierde, a propósito.

## Cómo se midió el delta

A la hora de medir, la PC estaba **~1,8× más cargada que al tomar la línea base** (`compute_kpis`, que no se tocó, pasó de 134 a ~240 ms). Comparar contra los números de `LINEA-BASE.md` habría inflado la mejora. Por eso: el código de la línea base (`git archive HEAD`) y el nuevo, **intercalados** (A, B, A, B), en el mismo momento, con las mismas herramientas. El Inicio, que no se tocó, sirve de control: tiene que dar igual en las dos versiones.

## Backend: costo de un click (AppTest, mediana; dos pasadas A/B)

| Caso | Antes | Después | Δ | Conexiones | Sentencias SQL |
|---|---:|---:|---:|---:|---:|
| Inicio (control) | 117 / 107 ms | 121 / 105 ms | = | 5 → 5 | 30 → 30 |
| Finanzas · Dashboard (la que abre) | 2.125 / 2.011 ms | 214 / 212 ms | **−90 %** | 22 → 5 | 116 → 28 |
| Finanzas · Transacciones | 2.206 / 2.088 ms | 35 / 34 ms | **−98 %** | 22 → 7 | 116 → 32 |
| Finanzas · Diario | 2.093 / 2.020 ms | 307 / 260 ms | **−86 %** | 22 → 4 | 116 → 21 |
| Finanzas · Mensual | 2.093 / 2.152 ms | 72 / 73 ms | **−97 %** | 22 → 6 | 116 → 32 |
| Finanzas · Configuración | 2.073 / 2.122 ms | 34 / 31 ms | **−98 %** | 22 → 7 | 116 → 34 |
| Elementos enviados (Dashboard) | 212 | 66 | −69 % | | |

## Frontend: primera carga de Finanzas, desktop, caché fría (mediana de 3; dos pasadas en orden inverso)

| Métrica | Antes | Después | Δ |
|---|---:|---:|---:|
| **Contenido estable** | 8,04 / 8,25 s | 6,80 / 6,63 s | **−18 %** |
| TBT | 1.192 / 1.180 ms | 925 / 984 ms | −19 % |
| Requests | 54 | 35 | −35 % |
| Bajado por red (sin comprimir) | 10,07 MB | 8,45 MB | −16 % |
| Frames del websocket | 220 (247 KB) | 74 (203 KB) | −66 % |
| Nodos DOM | 2.774 | 1.324 | −52 % |
| FCP / LCP | 796–928 / 1.196–1.312 ms | 888–1.040 / 1.372–1.708 ms | sin cambio claro (ruido de la PC) |
| CLS | 0,14 | 0,11–0,14 | = |

La primera carga mejora poco porque la domina bajar y compilar el JS de Streamlit y Plotly (el Dashboard tiene gráficos): eso es el frente 2. Lo que cambió de raíz es **cada click** (tabla de backend).

No se repitió el perfil móvil (90 s por corrida): queda para la medición final de la Fase 3.

## Probado en el runtime real

AppTest no ejecuta el Excel diferido (sin runtime, Streamlit ni registra el callable) y puede no aislar los fragmentos. Por eso, con Chrome por CDP contra la app local (`scripts/perf/probar_runtime.py`, la descarga denegada para no escribir a disco):

| Acción | Frames del websocket | Resultado |
|---|---:|---|
| Cargar Finanzas (referencia) | 74–75 | |
| "Agrupar por" → Subcategoría | 9 | la dona se reagrupa: solo corre el fragmento |
| Sacar la media de 90 días | 13 | el gráfico de Caja la pierde: el fragmento leyó la base con el contexto bien puesto |
| Abrir Configuración | 68 | aparece su contenido |
| "Descargar snapshot Excel" | — | 200, `…spreadsheetml.sheet`, 236 KB |

Sin ningún `Traceback` en el log del servidor.

## Tests

986 passed, 0 skipped. Nuevos en `tests/test_smoke_pantallas.py`: cada pestaña abre sola (y lo de Configuración aparece solo con Configuración abierta), los controles de los dos fragmentos andan, los filtros del Dashboard sobreviven a cambiar de pestaña, y el Excel exporta el workspace activo desde otro hilo.

La medición A/B se tomó antes de `FILTROS_QUE_PERSISTEN` (cinco asignaciones a `session_state` por corrida: costo despreciable).
