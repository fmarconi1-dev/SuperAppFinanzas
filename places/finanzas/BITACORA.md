# places/finanzas/

<!-- huella: a683522f388c -->

Resumen: Lugar A — Finanzas Personales (ex Mis-Finanzas-App / Radar Financiero): home con onboarding y las 5 pestañas. La lógica vive en `core/` local, las pantallas en `views/`.

## Buscar acá si

- el onboarding aparece cuando no debería (se evalúa SIEMPRE contra el espacio personal)
- el orden de las pestañas o una pestaña entera caída → `home.py`
- el badge grande del modo familiar

## Qué hay acá

- `home.py` — puerta del lugar: onboarding si faltan categorías, si no las 5 pestañas.
- `core/`, `views/`, `helpers/` — cada una con su propia BITACORA.md.

## Trampas

- El flag de onboarding vive en el workspace **personal** del usuario; en un familiar no hay flag y dispararía onboarding.
- **Corre solo la pestaña abierta** (21/10/2026): `st.tabs(..., key=CLAVE_PESTANA, on_change="rerun")` y cada vista se dibuja si `pestana.open`. Cambiar de pestaña es un rerun de esa sola pestaña. Antes corrían las cinco en cada click (1,2 s contra ~60 ms del Inicio, `docs/perf/`). Una pestaña nueva se agrega en `PESTANAS`, no en el cuerpo de `render()`; para abrir una desde código: `st.session_state[CLAVE_PESTANA] = <etiqueta>` antes del rerun. Desde el frente 2 (21/10) `PESTANAS` guarda el **nombre del módulo** de cada vista y se importa al abrir la pestaña (`import_module`): el Inicio importa este archivo y no tiene por qué traer Plotly ni el export. No volver a importar las vistas arriba (`tests/test_arranque_liviano.py`). **Un filtro nuevo de una vista va en `FILTROS_QUE_PERSISTEN`**: si no, Streamlit lo borra al abrir otra pestaña y vuelve a su default.

## Estado

- **Funciona:** en producción desde Fase 1. La Fase 4 cerró (respaldo + CI); la **Fase 5 (ADR-0006)** reescribe cómo se captura el gasto en este lugar — aprobada, sin arrancar.
- **Smoke test:** `tests/test_smoke_pantallas.py` abre `home.render()` con datos sintéticos (22/9/2026) y, desde el 21/10/2026, cada pestaña por separado.

## Proximo paso

Ver "Próximo paso concreto" en `/ESTADO.md`. La crónica del lugar está en `bitacora_de_trabajo.md`.
