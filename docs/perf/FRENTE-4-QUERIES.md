# Fase 2 · Frente 4 — Queries lentas y N+1 (21/10/2026)

Anteriores: `LINEA-BASE.md`, `FRENTE-1-RENDERS.md`, `FRENTE-2-CARGA-DIFERIDA.md`, `FRENTE-3-CACHE.md`. Datos crudos: `frente-4/`.

## Qué se buscó y qué apareció

No hay ORM: las consultas son SQL a mano con `sqlite3`. Se buscó (con un recorrido del AST) toda llamada a la base adentro de un `for`, los `SELECT *`, los planes de las consultas más pesadas y los loops de pandas fila por fila.

| Hallazgo | Costo medido | Qué se hizo |
|---|---|---|
| **`iterrows` sobre toda la historia** en `metrics._aplicar_grupo_efectivo` (KPIs, tablas del mes, gasto por categoría, `resumen`), `diario.libro_diario` y `budget.realidad_mensual_efectiva`. Es el "N+1" de esta app: una Series de pandas por fila | ~33 µs por fila: **~175 ms con 5.300 movimientos**, en cada recálculo | `categorizer.grupos_efectivos`: la misma `efective_grupo`, sobre las columnas crudas |
| `libro_diario` clasificaba **toda** la historia para mostrar 7 días | ~180 ms aunque se pidieran 7 días | clasifica solo las filas de la ventana; el saldo sigue usando toda la historia |
| `ORDER BY fecha, id` con índice solo por `workspace_id`: **B-tree temporal en cada lectura** | últimos 5 movimientos 2,7 ms; lectura entera 9,3 ms | **M25**: índice `(workspace_id, fecha, id)`, aditivo |
| Búsquedas por fila en el bot (`reglas_comercio` en fotos, conciliación y tarjetas) | consultas puntuales sobre `UNIQUE (workspace_id, tipo, comercio)`, una vez por archivo, decenas de filas | **no se tocó**: ya tienen índice y no valen el riesgo |
| `SELECT *` (3, en balances y lotes) | por `id` o sobre tablas chicas | no se tocó |

El SQL nunca fue el problema grande: después de los frentes 1–3 era el 15–25 % de un click. Lo caro era pandas.

## Que dé exactamente lo mismo

- `grupos_efectivos` llama a la misma `efective_grupo` con `float(...)` como hacía cada llamador: **es el mismo cálculo, sin `iterrows`**.
- Comparado afuera de los tests sobre los 5.300 movimientos sintéticos, código viejo y nuevo en procesos separados, con `assert_frame_equal(check_exact=True)`: `_aplicar_grupo_efectivo`, `compute_kpis` (todo y el mes), `ingresos_vs_gastos_mensual`, `gasto_por_categoria`, `libro_diario` a 7 y a 180 días y `realidad_mensual_efectiva`: **idénticos**, columnas y tipos incluidos.
- Los datos sintéticos no tienen "Inversiones" como ingreso (la regla dual): la cubren los tests nuevos, igual que la ventana vacía del Diario y el plan de M25.
- Los tests-oráculo contra los CSV de Franco corrieron (0 skipped).

## Resultado (AppTest, mediana de 5 reruns, dos pasadas A/B intercaladas)

A = frentes 1–3; B = + frente 4. A y B difieren solo en `core/db.py` (M25), `categorizer.py`, `metrics.py`, `diario.py` y `budget.py` (verificado con `diff`).

**Ojo con los números absolutos**: durante esta medición la PC estaba ~3× más cargada que en el frente 3 (43 % de CPU de otros programas; `compute_kpis` en A dio 570 ms contra ~150 en el frente 3). Lo que vale es la comparación A/B, tomada en el mismo momento.

| | A | B | Δ |
|---|---:|---:|---:|
| `compute_kpis` de toda la historia | 570 / 574 ms | 42 / 44 ms | **−92 %** |
| Diario, primer render | 987 / 939 ms | 166 / 181 ms | **−82 %** |
| Diario, click después de una escritura | 815 / 804 ms | 166 / 164 ms | **−80 %** |
| Dashboard, primer render | 607 / 604 ms | 408 / 439 ms | −30 % |
| Dashboard, click después de una escritura | 625 / 611 ms | 442 / 431 ms | −29 % |
| Inicio, primer render (incluye arrancar la app) | 2.805 / 2.676 ms | 2.362 / 2.351 ms | −14 % |
| Inicio, click después de una escritura | 309 / 289 ms | 249 / 255 ms | −16 % |
| Transacciones, click | 118 / 116 ms | 86 / 93 ms | −23 % (los últimos movimientos, por M25) |
| `load_transactions` | 62 / 63 ms | 52 / 55 ms | −15 % |
| Bot, `resumen` | 107 / 97 ms | 98 / 89 ms | −9 % |
| Mensual, Configuración | = | = | |

- Los clicks **sin cambios** no se mueven: ya los resolvía la caché del frente 3.
- El Dashboard mejora menos que el Diario porque calcula sobre el período (el mes), no sobre toda la historia; lo que le queda es armar las tres figuras de Plotly.

## Tests

999 passed, 0 skipped. Nuevo: `tests/test_consultas_rapidas.py` (`grupos_efectivos` igual a `efective_grupo` fila por fila con la regla dual, sin categoría y enteros; el plan con M25 sin B-tree temporal; el Diario con la ventana vacía y con el saldo de toda la historia).
