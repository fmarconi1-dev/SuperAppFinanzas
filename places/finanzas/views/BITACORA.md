# places/finanzas/views/

<!-- huella: cae905f01072 -->

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

## Estado

- **Funciona:** en producción.

## Proximo paso

—
