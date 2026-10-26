# places/finanzas/views/

<!-- huella: 52961b75d2c7 -->

Resumen: Las 5 pestañas de Finanzas + onboarding, en Streamlit puro; la lógica de negocio vive en `../core/`.

## Buscar acá si

- Dashboard, gráficos, editor de Fondo USD → `dashboard.py`
- alta rápida vs. detallada de gastos, "Firmar como" → `transacciones.py`
- Libro Diario → `diario.py` · Previsión vs Realidad → `mensual.py`
- editor de categorías y sección "Espacio compartido" → `configuracion.py`
- pantalla de bienvenida → `onboarding.py`

## Trampas

- **El bug del 4/8/2026**: el form de transacciones se bifurca en modo rápido/detallado y las dos ramas caen al mismo guardado; una variable definida en una sola rama tumba la app **al enviar** (así murió `firma_val`). `tests/test_transacciones_formulario.py` caza la forma del problema por AST: si agregás una variable a un modo, definila **antes** del `if`.
- El modo rápido es el que se usa desde el celular: probá ahí.
- Desde el 22/9/2026 `tests/test_smoke_pantallas.py` **abre** las 5 pestañas con `AppTest` y datos sintéticos: una pestaña que tire excepción al renderizar ya no llega a producción. No reemplaza probar un formulario enviándolo. Desde el 21/10/2026 corre solo la pestaña abierta, así que el test abre **cada una** (`test_cada_pestana_de_finanzas_abre`).
- **Código que corre sin los contextvars del script** (21/10/2026, frente 1 de rendimiento): el generador del Excel de `configuracion.py` (`_generador_excel`, lo corre Streamlit en otro hilo al tocar "Descargar") y el fragmento `_grafico_caja` de `dashboard.py` (se rerunnea solo, sin pasar por `app.py`). Los dos reciben el usuario y el workspace y los ponen ellos mismos. Un fragmento nuevo que lea la base tiene que hacer lo mismo: si no, en un espacio familiar lee el personal.
- **Dashboard y Diario cachean por versión de la base** (21/10/2026, frente 3): `_datos_base`, `_calculos_del_periodo` y `_caja` en `dashboard.py`, `_libro` en `diario.py`, con `core.db.version_datos()` en la clave. **Todo lo que cambie el resultado va en la clave como escalar** (fechas del período, días, `hoy`, ventanas); nunca un DataFrame (lento de hashear). Dentro de una función cacheada se ponen el usuario y el workspace en el contexto: en una corrida que no pasa por `app.py` (fragmento) no están.
- **No volver a armar el Excel (ni nada caro) en el cuerpo de `render()`**: corre en cada click de la pestaña. Lo caro y a pedido va en un callable o detrás de un botón.

## Estado

- **Funciona:** en producción.
- **17/10/2026 (Fase C, rebranding):** los textos que nombran pestañas ya no llevan emojis (`➕ Transacciones` → **Transacciones**, `⚙️ Configuración` → **Configuración**), porque las pestañas ahora usan íconos Material (skill `ui-ux-web-moderno`: nada de emojis como ícono estructural). Toca `dashboard.py`, `diario.py`, `mensual.py` y `onboarding.py`. Sin cambios de lógica.

- **21/10/2026 (rendimiento, frente 1):** el Excel de Configuración se arma al descargar; en el Dashboard, las medias móviles y "Agrupar por" son fragmentos y redibujan solo su gráfico. Medición en `docs/perf/FRENTE-1-RENDERS.md`.

- **21/10/2026 (rendimiento, frente 3):** caché por versión en Dashboard y Diario. Click sin cambios: Dashboard ~155 → ~51 ms, Diario ~205 → ~21 ms (`docs/perf/FRENTE-3-CACHE.md`).

## Proximo paso

—
