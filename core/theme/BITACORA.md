# core/theme/

<!-- huella: b8c60c3aa3a5 -->

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
- `_logo.py` — `render_logo()` con `st.image` (el SVG inline no sobrevive al sanitizer de `st.html`). `inline_logo()` y `try_set_logo()`, sin uso, se borraron el 22/9/2026.

## Trampas

- El CSS se inyecta **primero** en `app.py`, antes de renderizar nada, para evitar FOUC.
- `page_icon` de Streamlit: emoji, no SVG (tira TypeError de MIME).
- Skill `ui-ux-web-moderno` **obligatoria** para tocar esta carpeta (regla de claude.md).

## Estado

- **18/10/2026:** **ícono de la pestaña = el moño**: `assets/favicon.png` (128 px), generado con Pillow por `scripts/generar_favicon.py` con las mismas formas y colores del SVG. Va como `page_icon` en `app.py` (PNG porque un SVG ahí daba TypeError de MIME). Si cambia el logo, regenerarlo.
- **18/10/2026:** logo nuevo: **un moño de secretario** (elegido por Franco), en `assets/logo.svg` y `logo-horizontal.svg`. `render_logo` ahora lo dibuja como `<img>` con data URI **centrado** (con `st.image` en una columna quedaba corrido a la izquierda). Estilo `.st-key-inicio_saldo` para el saldo grande del Inicio.
- **17/10/2026 (Fase C):** sección **2c. Inicio** en `_styles.py`: tildes de tareas de 44 px de alto (celular) y clases `.cs-dia` / `.cs-evento` (semana y movimientos del Inicio), todo con tokens `--cs-*`. Logo nuevo de **Secretario** en `assets/logo.svg` (globo de chat con tilde; `_logo.py` no cambió).

- **Funciona:** en producción.

## Proximo paso

—
