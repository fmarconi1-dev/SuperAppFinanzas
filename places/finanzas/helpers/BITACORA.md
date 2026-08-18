# places/finanzas/helpers/

<!-- huella: 7bf3e12a0214 -->

Resumen: Utilidades de las vistas: formateo es-AR de montos, inyección de HTML y el tour guiado de bienvenida.

## Buscar acá si

- "$ mal formateado", separador de miles, un NaN visible en pantalla → `_format.py`
- HTML que se muestra como texto crudo → `_html.render_html`
- el tour guiado para usuarios nuevos → `_tour.py`

## Trampas

- `fmt_ars`/`fmt_usd` toleran NaN a propósito (`_is_nan`): no reemplazar por f-strings directos.

## Estado

- **Funciona:** en producción.

## Proximo paso

—
