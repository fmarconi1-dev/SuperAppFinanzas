"""Superapp de Finanzas — entry point.

Fase 0: "hola mundo" sin lógica, solo para validar el deploy en Fly.io.
En Fase 1 este archivo se convierte en el auth gate + navegación entre lugares.
"""

import streamlit as st

st.set_page_config(page_title="Superapp de Finanzas", page_icon="💸", layout="centered")

st.title("💸 Superapp de Finanzas")
st.caption("Fase 0 — Cimientos · deploy de prueba")

st.markdown(
    """
    **Hola mundo.** Si estás viendo esto, el deploy funciona.

    - 🏠 Lugar A — Finanzas Personales *(llega en Fase 1)*
    - 📈 Lugar B — Inversiones / Mercado *(llega en Fases 2-5)*
    """
)
