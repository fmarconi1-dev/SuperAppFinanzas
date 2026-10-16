# places/finanzas/core/

<!-- huella: 6fd6d31f4088 -->

Resumen: Lógica de negocio de Finanzas, pura y sin Streamlit: transacciones, categorización, KPIs, presupuesto, libro diario, import de CSV y export a Excel.

## Buscar acá si

- números del dashboard que no cierran → `metrics.py`
- qué se le suma a un briefing de Gemini (finanzas del mes al de la mañana, nada al cierre) → `briefing.py` (usa `comandos.totales_mes`, lo mismo que `resumen`)
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
- **16/10/2026 (Fase B):** `briefing.py` nuevo, puro: `componer` (texto de Gemini + bloque "📊 MIS FINANZAS" al de la mañana; el cierre tal cual). `comandos.totales_mes` extraído de `resumen_mes` para que los dos usen los mismos números. La SuperApp **no** genera ni valida datos de mercado: eso es de Gemini.
- **15/10/2026 (Fase A, sin desplegar):** `comandos.py` nuevo, puro y sin red: carga de gastos/ingresos por WhatsApp, categorías con "¿quisiste decir?" (prefijo único o difflib ≥ 0,75) y confirmación con vencimiento a los 10 min, `resumen` con la fórmula del dashboard (+ renglón "Sin categorizar"), `deshacer` (solo lo de WhatsApp, 24 h) y `ayuda`. Tests: `tests/test_comandos_whatsapp.py`.

## Proximo paso

—
