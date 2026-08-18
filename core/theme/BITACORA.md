# core/theme/

<!-- huella: 5e24a27a4248 -->

Resumen: Design system "Cosmic Slate": CSS inyectado en Streamlit, paleta semántica + template Plotly unificado, ajustes responsive y logo.

## Buscar acá si

- estética, colores, tipografía, dark mode, "se ve poco profesional"
- "se ve mal en el celular" → `_responsive.py`
- un gráfico Plotly con colores fuera de paleta → `_theme.py`
- KPI cards, tokens de diseño, flash sin estilos (FOUC)
- el logo → `_logo.py`

## Qué hay acá

- `_styles.py` — el design system entero como CSS injection (portado del proyecto React paralelo).
- `_theme.py` — paleta semántica + template Plotly.
- `_responsive.py` — media queries mobile.
- `_logo.py` — logo SVG inline.

## Trampas

- El CSS se inyecta **primero** en `app.py`, antes de renderizar nada, para evitar FOUC.
- `page_icon` de Streamlit: emoji, no SVG (tira TypeError de MIME).
- Skill `ui-ux-web-moderno` **obligatoria** para tocar esta carpeta (regla de claude.md).

## Estado

- **Funciona:** en producción.

## Proximo paso

—
