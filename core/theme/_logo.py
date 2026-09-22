"""El logo de la app (`assets/logo.svg`).

Nota: `st.html()` (Streamlit ≥1.33) sanitiza el HTML con DOMPurify y elimina
los `<svg>` inline. Por eso `render_logo()` dibuja el SVG con `st.image()`
nativo en una columna centrada (Streamlit sirve la imagen como recurso).
`inline_logo()` y `try_set_logo()`, que no usaba nadie, se borraron el
22/9/2026.
"""

from __future__ import annotations

import os

import streamlit as st


_LOGO_PATH = "assets/logo.svg"


def render_logo(size: int = 64) -> None:
    """Dibuja el logo centrado usando st.image (resiste el sanitizer de st.html).

    Si por algún motivo no se encuentra el SVG, no rompe — solo no muestra
    el logo. Llamar dentro de un hero block, ANTES del título.
    """
    if not os.path.exists(_LOGO_PATH):
        return
    # Centrado con 3 columnas: la del medio aloja el logo.
    _, c, _ = st.columns([1, 1, 1])
    with c:
        try:
            st.image(_LOGO_PATH, width=size)
        except Exception:
            # Si Streamlit no puede renderizar el SVG (versiones viejas),
            # mostramos un emoji como fallback.
            st.markdown("### 🎯")


