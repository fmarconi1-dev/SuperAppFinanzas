"""El logo de la app (`assets/logo.svg`, el moño de Secretario).

Nota: `st.html()` (Streamlit ≥1.33) sanitiza el HTML con DOMPurify y elimina
los `<svg>` inline. Hasta el 18/10/2026 `render_logo()` lo dibujaba con
`st.image()` en la columna del medio de tres, pero `st.image` alinea a la
izquierda dentro de su columna y el logo quedaba corrido (lo vio Franco en el
login). Ahora va como `<img>` con el SVG en un data URI, centrado con CSS:
DOMPurify sí deja pasar `<img src="data:image/...">`.
"""

from __future__ import annotations

import base64
import os

from places.finanzas.helpers._html import render_html

_LOGO_PATH = "assets/logo.svg"


def logo_data_uri() -> str | None:
    """El SVG del logo como data URI, o None si no está el archivo."""
    if not os.path.exists(_LOGO_PATH):
        return None
    with open(_LOGO_PATH, "rb") as f:
        return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode("ascii")


def render_logo(size: int = 64) -> None:
    """Dibuja el logo centrado. Llamar dentro de un hero block, ANTES del título.

    Si no se encuentra el SVG, no rompe: solo no muestra el logo.
    """
    uri = logo_data_uri()
    if uri is None:
        return
    render_html(
        f'<div style="display:flex;justify-content:center;padding-top:0.5rem;">'
        f'<img src="{uri}" width="{size}" height="{size}" alt="Secretario"></div>'
    )
