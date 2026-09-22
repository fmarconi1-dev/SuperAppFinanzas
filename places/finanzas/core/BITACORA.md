# places/finanzas/core/

<!-- huella: 7b283f9ae67f -->

Resumen: Lógica de negocio de Finanzas, pura y sin Streamlit: transacciones, categorización, KPIs, presupuesto, libro diario, import de CSV y export a Excel.

## Buscar acá si

- números del dashboard que no cierran → `metrics.py`
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
- **El CLI de `ingest.py` se corre solo como `python -m places.finanzas.core.ingest` desde la raíz.** Hasta el 22/9 tenía un `sys.path.insert` heredado de Mis-Finanzas-App que hacía resolver `core` a `places/finanzas/core`: el CLI moría y la suite no lo veía porque importa el `core` bueno antes. `tests/test_importes_ilegibles.py` lo corre como subproceso.

## Estado

- **Funciona:** en producción.

## Proximo paso

—
