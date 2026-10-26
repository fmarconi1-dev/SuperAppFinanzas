# Fase 2 · Frente 3 — Requests y caché (21/10/2026)

Anteriores: `LINEA-BASE.md`, `FRENTE-1-RENDERS.md`, `FRENTE-2-CARGA-DIFERIDA.md`. Datos crudos: `frente-3/`.

## Qué había (después de los frentes 1 y 2)

Cada click releía de la base lo mismo que el click anterior y lo recalculaba con pandas, aunque nada hubiera cambiado. El Inicio y el Dashboard leían **todas las transacciones dos veces por click**. El SQL ya era solo el 15–25 % del click: lo caro era volver a calcular KPIs, tablas del mes y el libro diario.

No hay Redis ni hace falta: un solo proceso de Streamlit, y `st.cache_data` es la caché en memoria. **El problema de fondo era cuándo invalidarla**, porque el bot de WhatsApp escribe en la misma base desde **otro proceso**: una caché por tiempo (TTL) mostraría un gasto recién mandado por WhatsApp recién minutos después.

## Cómo se resolvió

- **`core.db.version_datos()`**: `PRAGMA data_version` sobre una conexión "vigía" que vive lo que el proceso y nunca escribe. Cambia con cualquier commit de cualquier otra conexión, **también de otro proceso**. Leer no la mueve. Devuelve `(generación, versión)` para que un vigía nuevo (si cambia la ruta) no repita números viejos.
- Probado antes de usarlo: ve el commit de otro proceso y de otra conexión del mismo proceso; no frena los checkpoints del WAL (`busy = 0`, el WAL queda en 0 bytes); un checkpoint sí la mueve (un recálculo de más, nunca un número viejo); ninguna pantalla escribe en un click sin cambios (la versión no se movió en 5 reruns de ninguna de las 6 pantallas); el `mv` de `restaurar_backup.ps1` va seguido de un reinicio de la máquina.
- **Cachés por versión** (`@st.cache_data`, claves escalares, nunca DataFrames):

| Pantalla | Función | Clave |
|---|---|---|
| Inicio | `_numeros_del_inicio` (saldo, mes, últimos movimientos) | ruta, usuario, workspace, versión, hoy |
| Dashboard | `_datos_base` (transacciones, categorías, saldo, fondo) | ruta, usuario, workspace, versión |
| Dashboard | `_calculos_del_periodo` (KPIs, ingresos vs gastos, por categoría) | + las fechas del período y el año |
| Dashboard | `_caja` (serie de Caja con medias) | + las ventanas |
| Diario | `_libro` | + días, hoy (`libro_diario` cuenta desde hoy) |

Transacciones, Mensual y Configuración no se cachearon: sus clicks ya cuestan 20–55 ms y casi todos escriben.

## Resultado (AppTest, mediana de 5 reruns, dos pasadas A/B intercaladas)

A = frentes 1 y 2; B = + frente 3. A y B difieren solo en `core/db.py`, `places/inicio/home.py`, `views/dashboard.py` y `views/diario.py` (verificado con `diff`).

| Pantalla | Click sin cambios A | B | Δ | Click justo después de una escritura A | B |
|---|---:|---:|---:|---:|---:|
| Inicio | 104 / 78 ms | 16 / 18 ms | **−80 %** | 112 / 76 ms | 74 / 76 ms |
| Dashboard | 150 / 159 ms | 51 / 52 ms | **−67 %** | 153 / 156 ms | 146 / 162 ms |
| Diario | 200 / 210 ms | 21 / 21 ms | **−90 %** | 198 / 208 ms | 214 / 197 ms |
| Transacciones, Mensual, Configuración | = | = | sin caché | = | = |

Sentencias SQL por click sin cambios: Inicio 30 → 21, Dashboard 28 → 17, Diario 21 → 16. Conexiones: 5 → 4, 5 → 3, 4 → 3.

- "Sin cambios" es lo más común: cambiar de pestaña y volver, tocar un filtro y volverlo atrás, cualquier fragmento, recargar la página (la caché es de todo el proceso, no de la sesión).
- **Después de una escritura cuesta lo mismo que antes**: tiene que recalcular. Lo que queda ahí es el cálculo con pandas (`_aplicar_grupo_efectivo` con `iterrows`): es el frente 4.
- Lo que queda en el Dashboard con caché (51 ms) es armar las tres figuras de Plotly y mandarlas.

## Probado en el runtime real

- `scripts/perf/probar_cache_runtime.py`: con la app abierta, recargar sin cambios muestra "Gastos de octubre $3.183.518"; un gasto de $50.000 escrito **desde otro proceso** aparece en la recarga siguiente: $3.233.518.
- `scripts/perf/probar_runtime.py`: pestañas, fragmentos y Excel igual que antes. Sin `Traceback` en el log.

## Tests

994 passed, 0 skipped. Nuevos en `tests/test_cache_versionada.py`: la versión no se mueve si nadie escribe, ve lo que escribe otro proceso, el vigía no frena los checkpoints, el Inicio no recalcula sin cambios, y el Inicio, el Dashboard y el Diario muestran lo que cargó otro proceso en el click siguiente. **Con la versión congelada a mano, los dos tests de "muestra lo del bot" fallan**: detectan una caché vieja.
