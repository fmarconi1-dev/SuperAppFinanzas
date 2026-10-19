# places/inicio/core/

<!-- huella: a458986a0444 -->

Resumen: La lógica del Inicio, **pura y sin Streamlit**: los números del mes y el saldo (`resumen.py`) y la semana y las tareas de Google, listas para mostrar (`semana.py`). La pantalla está en `../home.py`.

## Buscar acá si

- el saldo grande del Inicio no coincide con el del Dashboard → `resumen.py` (`saldo_cuenta`, que es `metrics.saldo_cuenta_corriente`)
- gastos, ingresos o movimientos del mes no coinciden con `resumen` por WhatsApp → `resumen.py` (`resumen_del_mes` usa `comandos.totales_mes`, la misma función del bot)
- la variación contra el mes anterior da rara, o la flecha apunta al revés → `resumen.py` (`variacion`, `formatear_variacion`, `mes_anterior`)
- "Buen día / Buenas tardes" o la fecha larga en castellano → `resumen.py` (`saludo`, `fecha_larga`)
- el renglón "mensajes en cola" del estado del Secretario → `resumen.py` (`mensajes_en_cola`, tabla `whatsapp_salientes`)
- un evento aparece en el día equivocado, o falta uno que sigue en curso → `semana.py` (`dias_de_la_semana`)
- el orden de las tareas (vencidas, con fecha, sin fecha) → `semana.py` (`tareas_ordenadas`)

## Trampas

- **Se compara contra el mismo período**, del 1 al día de hoy, no contra el mes anterior entero (`totales_mes(..., hasta_dia=)`).
- **`formatear_variacion` usa "-" ASCII:** Streamlit decide la flecha del delta por el primer carácter, y con "−" tipográfico pintaba una baja como suba.
- **Un mes sin movimientos devuelve ceros, no rompe:** el 1° del mes, antes de cargar nada, `totales_mes` tiraba `KeyError: 'pasivos'` (arreglado el 17/10/2026).
- **Un evento que empezó antes de hoy va en hoy**, marcado "En curso". Si no, quedaba en un día que ya no se lista y desaparecía.
- **Las tareas sin fecha conservan el orden de Google Tasks** (orden estable), no alfabético.
- Este paquete no importa Streamlit ni hace red: el cliente de la agenda y la caché viven en `../home.py`. Así se testea sin `AppTest`.

## Estado

- **17–18/10/2026 (Fase C):** creado con el Inicio. Tests: `tests/test_inicio.py` (lógica, igualdad con `resumen`, saldo igual al del Dashboard) y `tests/test_inicio_agenda.py` (agrupado por día y orden de tareas). Franco lo dio por bueno el 18/10/2026.

## Proximo paso

—
