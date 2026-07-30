"""Lugar B — Inversiones / Mercado. Estructura triple (scoring / cartera / vivo).

Fase 3a: Scoring y **Cartera** activos. Mercado en vivo (Fase 5) muestra su
lugar reservado — encuadre visible del roadmap, sin prometer de más.
"""

from __future__ import annotations

import streamlit as st

from places.inversiones.cartera import view as cartera_view
from places.inversiones.scoring import view as scoring_view


def render() -> None:
    st.title("📈 Inversiones / Mercado")

    tab_scoring, tab_cartera, tab_vivo = st.tabs(
        ["📊 Análisis y Scoring", "💼 Cartera", "📡 Mercado en vivo"]
    )

    with tab_scoring:
        scoring_view.render()

    with tab_cartera:
        cartera_view.render()

    with tab_vivo:
        st.info(
            "**Llega en Fase 5.** Cotizaciones del mercado argentino en vivo. "
            "Depende de validar la fuente de datos (candidatas ya identificadas: "
            "BCRA, data912, BYMA, MAE).",
            icon="🚧",
        )
