# places/inversiones/cartera/paneles/

<!-- huella: 8b324f0342be -->

Resumen: Los paneles de la pantalla de Cartera, uno por archivo. Salieron de `view.py` en el split del 27/8/2026, que movió código sin cambiarlo.

## Buscar acá si

- "Cómo está repartida" (tipo de renta, sector, industria, emisor, país) → `composicion.py`
- "Contra el mercado" (benchmark money-weighted vs SPY/Merval) → `mercado.py`
- "Qué se te vence" y el alta manual de una fecha → `vencimientos.py`
- "Cuándo cobrás" (cronogramas, TIR esperada, duration) → `renta_fija.py`
- "Operaciones cerradas" (resultado realizado) → `operaciones.py`
- "La plata quieta" (cauciones, dividendos, cuenta remunerada) → `caja.py`
- ajustes de tenencia: splits, ratios de CEDEAR, papeles pre-registro → `ajustes.py`
- la subida del export del broker, el orden del import, el estado vacío → `importar.py`
- un precio o el MEP que llega raro a un panel, la foto de posiciones → `_datos.py`
- "$ mal formateado" o una KPI card → `_comun.py`

## Qué hay acá

- `_comun.py` — `_fmt` (es-AR), `_kpi_card` (Cosmic Slate) y `_TTL_PRECIOS`.
- `_datos.py` — lo cacheado (`@st.cache_data`): precios, MEP, sectores, BTC; más `_aplicar_tenencia` e `_instrumentos_de_db`.
- Un archivo por panel; cada uno expone una función `_<panel>(...)` que `view.py` llama en orden.

## Trampas

- **Los nombres tienen guion bajo y se importan igual.** El split movió código, no lo renombró: `view.py` reimporta `_composicion`, `_benchmark`, etc. con el mismo nombre, por eso `render()` no cambió. Renombrarlos ahora sería un segundo cambio disfrazado del primero.
- `_TTL_PRECIOS` vive en `_comun.py`, no en `view.py`: los decoradores `@st.cache_data` de varios paneles lo necesitan y al revés sería un import circular.
- **Hay tests que leen el código fuente por AST**, no que importan el módulo (`view.py` arrastra Streamlit entero). Si movés una función de archivo, mirá `tests/test_cartera_renta_fija.py`: busca en `paneles/renta_fija.py` **y** en `view.py`, a propósito, para que lo que se afirme sea qué hace la función y no dónde vive.
- Un panel no debe importar `view.py`. La dirección es siempre `view.py → paneles/`.
- **`st.success(...)` seguido de `st.rerun()` no se ve**: el rerun lo borra antes. `renta_fija._refrescar` guarda el aviso en `session_state` y lo muestra en la vuelta siguiente — así se ve también "Docta no contestó".
- `renta_fija` distingue "la fuente no lo tiene" (`ya_consultado`, cartel informativo) de "todavía no se pudo bajar" (warning con la acción). Antes del 22/9/2026 los dos decían "es esperable, no hay nada que arreglar".
- `mercado.py` avisa con un `st.warning` si la serie del índice llegó **sin dividendos** (`origen == "sin_ajustar"`): esa comparación favorece a la cartera.
- `_datos._resolver_sectores` solo tolera `sqlite3.OperationalError` (base ocupada); una falla de Yahoo ya no llega hasta acá y un bug se ve.
- `_procesar_carga` (el import de un solo archivo, anterior a *Importar todo*) se borró el 22/9/2026: `view.py` lo importaba pero nadie lo llamaba.

## Estado

- **Funciona:** split verificado por AST contra la versión anterior (27/8). Desde el 22/9/2026 `tests/test_db_concurrencia.py` revisa también estos paneles (antes miraba solo `view.py` y pasaba en blanco) y `tests/test_smoke_pantallas.py` abre la pantalla completa.

## Proximo paso

—

La crónica vive en `../bitacora_de_trabajo.md`.
