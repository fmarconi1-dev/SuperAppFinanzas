# places/finanzas/views/

<!-- huella: eb82a09ccd84 -->

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
- Desde el 22/9/2026 `tests/test_smoke_pantallas.py` **abre** las 5 pestañas con `AppTest` y datos sintéticos: una pestaña que tire excepción al renderizar ya no llega a producción. No reemplaza probar un formulario enviándolo.

## Estado

- **Funciona:** en producción.
- **17/10/2026 (Fase C, rebranding):** los textos que nombran pestañas ya no llevan emojis (`➕ Transacciones` → **Transacciones**, `⚙️ Configuración` → **Configuración**), porque las pestañas ahora usan íconos Material (skill `ui-ux-web-moderno`: nada de emojis como ícono estructural). Toca `dashboard.py`, `diario.py`, `mensual.py` y `onboarding.py`. Sin cambios de lógica.

## Proximo paso

—
