"""Lugar B — Inversiones / Mercado. Estructura triple (scoring / cartera / vivo).

Fase 2: solo Scoring está activo. Cartera (Fase 3) y Mercado en vivo (Fase 5)
muestran su lugar reservado — encuadre visible del roadmap, sin prometer de más.
"""

from __future__ import annotations

import streamlit as st

from places.inversiones.scoring import view as scoring_view


def render() -> None:
    st.title("📈 Inversiones / Mercado")

    tab_scoring, tab_cartera, tab_vivo = st.tabs(
        ["📊 Análisis y Scoring", "💼 Cartera", "📡 Mercado en vivo"]
    )

    with tab_scoring:
        scoring_view.render()

    with tab_cartera:
        st.info(
            "**Llega en Fase 3.** Dashboard de cartera leyendo `Inversiones.xlsx` "
            "(posiciones, TIR de renta fija, estructura por activo/sector), con "
            "test de reconciliación fila a fila contra el Excel.",
            icon="🚧",
        )

    with tab_vivo:
        st.info(
            "**Llega en Fase 5.** Cotizaciones del mercado argentino en vivo. "
            "Depende de validar la fuente de datos (candidatas ya identificadas: "
            "BCRA, data912, BYMA, MAE).",
            icon="🚧",
        )
