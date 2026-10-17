# places/inicio/

<!-- huella: 5ea900f76b01 -->

Resumen: Lugar Inicio — la pantalla principal de Secretario (Fase C, ADR-0008): saludo, finanzas del mes con variación contra el mismo período del mes anterior y últimos movimientos. Agenda y tareas, en el paso 3.

## Buscar acá si

- la pantalla de Inicio no abre, se ve mal o muestra un número raro → `home.py`
- un KPI del Inicio no coincide con `resumen` por WhatsApp → **no debería poder**: los dos usan `comandos.totales_mes`; ver `core/resumen.py` y el test `test_los_kpis_del_inicio_son_los_de_resumen`
- la variación contra el mes anterior parece mal → `core/resumen.py` (`resumen_del_mes`: compara contra el **mismo período**, del 1 al día de hoy)

## Trampas

- **Comparar contra el mismo período, no contra el mes entero:** el 17/10, octubre lleva 17 días y septiembre tuvo 30. Contra septiembre completo, siempre parecería que se gasta menos. `totales_mes(..., hasta_dia=)` corta el mes.
- **El delta de `st.metric` va con "-" ASCII**, no con el "−" tipográfico: Streamlit decide la flecha y el color por el primer carácter, y con "−" pintaba una baja como suba.
- Gastos usa `delta_color="inverse"`: gastar más es malo.
- Sin categorías todavía (usuario nuevo), el Inicio muestra la bienvenida de Finanzas, igual que antes.
- `AppTest.from_function` corre la función como un script aparte: no ve variables de afuera. Los datos de prueba viajan por `session_state` (ver `tests/test_inicio.py`).

## Estado

- **17/10/2026 (Fase C, pasos 1–2, sin desplegar):** creado. Inicio es la página default de `app.py`. Tests: `tests/test_inicio.py` (lógica, igualdad con `resumen`, AppTest con y sin movimientos, la app abre en Inicio, marca "Secretario"). **No se miró en un navegador todavía.**

## Proximo paso

Paso 3 del plan: semana y tareas desde el Apps Script (`resumen_semana`), con caché de 5 min, Actualizar y estados de carga/vacío/error.
