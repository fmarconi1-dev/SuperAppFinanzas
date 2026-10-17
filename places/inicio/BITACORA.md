# places/inicio/

<!-- huella: fb175930ef87 -->

Resumen: Lugar Inicio — la pantalla principal de Secretario (Fase C, ADR-0008): saludo, finanzas del mes contra el mismo período del anterior, la semana y las tareas de Google (con tilde para completarlas), últimos movimientos y estado del Secretario.

## Buscar acá si

- la pantalla de Inicio no abre, se ve mal o muestra un número raro → `home.py`
- un KPI del Inicio no coincide con `resumen` por WhatsApp → **no debería poder**: los dos usan `comandos.totales_mes`; ver `core/resumen.py` y el test `test_los_kpis_del_inicio_son_los_de_resumen`
- la semana o las tareas no aparecen, aparecen viejas o un tilde no completa → `home.py` (`_render_agenda`, caché `_semana` de 5 min, callback `_completar`) y `core/semana.py` (agrupar por día, ordenar tareas)
- la variación contra el mes anterior parece mal → `core/resumen.py` (`resumen_del_mes`: compara contra el **mismo período**, del 1 al día de hoy)

## Trampas

- **Comparar contra el mismo período, no contra el mes entero:** el 17/10, octubre lleva 17 días y septiembre tuvo 30. Contra septiembre completo, siempre parecería que se gasta menos. `totales_mes(..., hasta_dia=)` corta el mes.
- **El delta de `st.metric` va con "-" ASCII**, no con el "−" tipográfico: Streamlit decide la flecha y el color por el primer carácter, y con "−" pintaba una baja como suba.
- Gastos usa `delta_color="inverse"`: gastar más es malo.
- Sin categorías todavía (usuario nuevo), el Inicio muestra la bienvenida de Finanzas, igual que antes.
- **La agenda se guarda 5 minutos** (`st.cache_data`): un evento recién creado por WhatsApp aparece al tocar **Actualizar agenda** o a los 5 minutos. Los errores no se cachean.
- **Una tarea se tacha solo si Google confirma.** El tilde llama a `completar_tarea` en el callback; si Google rechaza, el callback vuelve a poner el checkbox en `False` y deja el error para mostrarlo. En el callback no se usan contextvars (premortem #5): el cliente viaja en `args`.
- Un evento que empezó antes de hoy (varios días, o uno que cruzó la medianoche) se muestra **hoy**, con "En curso" en vez de su hora de inicio.
- Las tareas sin fecha quedan en **el orden de Google Tasks** (orden estable), no alfabético.
- `AppTest.from_function` corre la función como un script aparte: no ve variables de afuera. Los datos de prueba viajan por `session_state` (ver `tests/test_inicio.py`).

## Estado

- **17/10/2026 (Fase C, pasos 3–5, sin desplegar):** semana y tareas desde `resumen_semana` (caché 5 min, **Actualizar agenda**, estados de carga, vacío, error con **Reintentar** y sin configurar), tilde para completar en Google Tasks, y renglón de estado del Secretario (mensajes en cola + agenda conectada). Tests: `tests/test_inicio_agenda.py`.
- **17/10/2026 (Fase C, pasos 1–2, sin desplegar):** creado. Inicio es la página default de `app.py`. Tests: `tests/test_inicio.py` (lógica, igualdad con `resumen`, AppTest con y sin movimientos, la app abre en Inicio, marca "Secretario"). **No se miró en un navegador todavía.**

## Proximo paso

Paso 6 del plan: deploy, mirarlo en el navegador (escritorio y celular, 375 px) y pulir contra el checklist de la skill `ui-ux-web-moderno`.
