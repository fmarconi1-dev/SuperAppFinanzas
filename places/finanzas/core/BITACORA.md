# places/finanzas/core/

<!-- huella: 8f77e826c1c8 -->

Resumen: Lógica de negocio de Finanzas, pura y sin Streamlit: transacciones, categorización, KPIs, presupuesto, libro diario, import de CSV y export a Excel.

## Buscar acá si

- números del dashboard que no cierran → `metrics.py`
- un briefing de Gemini que llega distinto de como lo mandó Gemini → `briefing.py` (no le suma nada: los dos tipos salen tal cual)
- `evento:` / `tarea:` / `agenda`: fechas y horas de agenda, formato de la semana → `agenda.py` (puro). Cómo se rutean y qué se contesta si Google falla → `comandos._comando_agenda`
- un mensaje de WhatsApp que no se cargó, se cargó mal o pidió confirmación → `comandos.py` (parser de montos y fechas, "¿quisiste decir?", `resumen`, `deshacer`)
- Previsión vs Realidad por mes → `budget.py`
- categorías, "sin categorizar", mapping Motivo → Grupo/Subcategoría → `categorizer.py`, `categorias.py`
- importar `Diario.csv` / `Mensual.csv` (`ingest.py`, `parsers.py`; env `DIARIO_CSV`/`MENSUAL_CSV`) — por consola: `.venv\Scripts\python.exe -m places.finanzas.core.ingest --force`
- un gasto que entró como $0, o una advertencia de "importe ilegible" al importar → `parsers.parse_currency_estricto` + `ingest._importe`
- alta/edición/borrado de gastos y el backup automático que disparan → `transactions.py`
- exportar todo a Excel → `export.py`

## Qué hay acá

- Un módulo por dominio; nombres autoexplicativos. `metrics.py` es el más usado (11 dependientes).

## Trampas

- Desde el cutover D2, **todas** las queries del dominio filtran por `workspace_id`; `user_id` quedó solo como autor/firma. Una query nueva sin ese filtro mezcla espacios.
- `transactions.py` dispara el hook de backup: tocarlo afecta `tests/test_backup_*`.
- ⚠️ **Un importe ilegible no es cero** (22/9/2026). `parse_currency` devuelve 0.0 por compatibilidad (no corrompe Caja), pero para importar se usa `parse_currency_estricto` (→ `None`), y el ingest anota cada ilegible en `ImportResult.advertencias` con fila y valor. Antes un `1.5OO` entraba como gasto de $0 sin rastro, y el comentario decía que el ingest avisaba — no avisaba.
- ⚠️ **Montos tipeados ≠ montos del CSV** (15/10/2026). `comandos.parsear_monto` es propio y estricto: el punto solo vale como miles en grupos de 3, la coma es el decimal, y `2500.50` se **repregunta**. `parse_currency_estricto` borra todos los puntos (`1.5` → 15): sirve para el Excel, no para el celular.
- `comandos.py` corre en un hilo del servidor HTTP: **`user_id` explícito en toda llamada** (los contextvars arrancan vacíos en cada hilo) y "hoy" en Buenos Aires, nunca en la zona del servidor.
- **El CLI de `ingest.py` se corre solo como `python -m places.finanzas.core.ingest` desde la raíz.** Hasta el 22/9 tenía un `sys.path.insert` heredado de Mis-Finanzas-App que hacía resolver `core` a `places/finanzas/core`: el CLI moría y la suite no lo veía porque importa el `core` bueno antes. `tests/test_importes_ilegibles.py` lo corre como subproceso.

## Estado

- **Funciona:** en producción.
- **17/10/2026 (Fase C):** `totales_mes(..., hasta_dia=)` para comparar contra el mismo período del mes anterior (lo usa el Inicio). **Arreglado:** `totales_mes` en un mes sin movimientos (habiendo movimientos en otros meses) tiraba `KeyError: 'pasivos'`, o sea que `resumen` por WhatsApp se rompía el 1° de cada mes antes de cargar nada. Test: `test_resumen_de_un_mes_sin_movimientos_no_se_rompe`. Las pestañas y los textos de ayuda nombran las pestañas sin emoji (ahora son íconos Material).
- **17/10/2026 (Fase B, paso 3):** `agenda.py` nuevo, puro: `evento: fecha, [hora inicio], [hora fin], título[, descripción]`, `tarea: [fecha], título[, descripción]` y el formato de `agenda`. Las fechas de agenda **sí pueden ser futuras** (al revés que los gastos): `hoy`, `mañana`, `pasado mañana`, días de la semana, `DD/MM` (si ya pasó, es del año que viene), con año (si ya pasó, se rechaza). Horas `15`, `15hs`, `15:30`, `9.30`, rango `9-10:30`. La confirmación muestra el día de la semana. `procesar` recibe el cliente (`agenda`) y el wamid (`id_mensaje`); confirma **solo** si Google dijo `ok: true`.
- **16/10/2026:** **cuentas en el monto** (`100-50`, `3x2.500`, `12.000/3`, con + − × ÷ y la precedencia de siempre). Solo números y signos, nada de texto libre; cada número sigue las reglas estrictas de `_numero`; resultado ≤ 0 o división por cero se rechazan; la confirmación muestra la cuenta. Arreglado: "100 - 50, compras" tomaba $100 y la categoría "- 50" (ahora una categoría necesita una letra y no puede empezar con un signo). `12/3` al principio es fecha solo si después viene un monto; si no, es 12 ÷ 3.
- **16/10/2026 (Fase B):** `briefing.py` nuevo, puro: `componer` valida tipo y texto y lo devuelve **tal cual**. Primero le sumaba un bloque de finanzas al de la mañana; Franco lo sacó el mismo día: *"El briefing es una cosa, mis finanzas son otra"*. `comandos.totales_mes` quedó extraído de `resumen_mes` (lo usa `resumen`). La SuperApp **no** genera ni valida datos de mercado: eso es de Gemini.
- **15/10/2026 (Fase A, sin desplegar):** `comandos.py` nuevo, puro y sin red: carga de gastos/ingresos por WhatsApp, categorías con "¿quisiste decir?" (prefijo único o difflib ≥ 0,75) y confirmación con vencimiento a los 10 min, `resumen` con la fórmula del dashboard (+ renglón "Sin categorizar"), `deshacer` (solo lo de WhatsApp, 24 h) y `ayuda`. Tests: `tests/test_comandos_whatsapp.py`.

## Proximo paso

—
