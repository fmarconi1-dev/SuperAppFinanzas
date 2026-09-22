# places/finanzas/helpers/

<!-- huella: 8bd938f46a52 -->

Resumen: Utilidades de las vistas: formateo es-AR de montos, inyección de HTML y el tour guiado de bienvenida.

## Buscar acá si

- "$ mal formateado", separador de miles, un NaN visible en pantalla → `_format.py`
- HTML que se muestra como texto crudo → `_html.render_html`
- el tour guiado para usuarios nuevos → `_tour.py`

## Trampas

- `fmt_ars`/`fmt_usd` toleran NaN a propósito (`_is_nan`): no reemplazar por f-strings directos.
- `fmt_pct`/`fmt_pct_signed` se borraron el 22/9/2026 (no las usaba nadie). Para un porcentaje nuevo, agregalo acá con la misma tolerancia a NaN.

## Estado

- **Funciona:** en producción.

## Proximo paso

—
