# places/finanzas/core/

<!-- huella: 2eb264ca52f0 -->

Resumen: Lógica de negocio de Finanzas, pura y sin Streamlit: transacciones, categorización, KPIs, presupuesto, libro diario, import de CSV y export a Excel.

## Buscar acá si

- números del dashboard que no cierran → `metrics.py`
- Previsión vs Realidad por mes → `budget.py`
- categorías, "sin categorizar", mapping Motivo → Grupo/Subcategoría → `categorizer.py`, `categorias.py`
- importar `Diario.csv` / `Mensual.csv` (`ingest.py`, `parsers.py`; env `DIARIO_CSV`/`MENSUAL_CSV`)
- alta/edición/borrado de gastos y el backup automático que disparan → `transactions.py`
- exportar todo a Excel → `export.py`

## Qué hay acá

- Un módulo por dominio; nombres autoexplicativos. `metrics.py` es el más usado (11 dependientes).

## Trampas

- Desde el cutover D2, **todas** las queries del dominio filtran por `workspace_id`; `user_id` quedó solo como autor/firma. Una query nueva sin ese filtro mezcla espacios.
- `transactions.py` dispara el hook de backup: tocarlo afecta `tests/test_backup_*`.

## Estado

- **Funciona:** en producción.

## Proximo paso

—
