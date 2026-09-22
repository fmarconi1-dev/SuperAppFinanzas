"""Lugar B — Inversiones / Mercado.

**Scoring retirado el 5/8/2026** (decisión de Franco): *"es demasiado y no
tiene influjo real de información"*. Era una pestaña que mostraba un ranking de
~20 empresas que no cambiaba nada de lo que él hacía. Con eso, la resolución de
sectores de la cartera pasa a ser **100% Yahoo**, que ya cubría el total de su
renta variable. Detalle y motivo en `docs/decisiones/ADR-0002-...` (marcado
como retirado) y en la bitácora de cartera.

Queda Cartera, y Mercado en vivo con su lugar reservado — encuadre visible del
roadmap, sin prometer de más.
"""

from __future__ import annotations

import streamlit as st

from places.inversiones.cartera import view as cartera_view


def render() -> None:
    st.title("📈 Inversiones / Mercado")

    tab_cartera, tab_vivo = st.tabs(["💼 Cartera", "📡 Mercado en vivo"])

    with tab_cartera:
        cartera_view.render()

    with tab_vivo:
        st.info(
            "**Llega en Fase 6.** Cotizaciones del mercado argentino en vivo. "
            "Depende de validar la fuente de datos (candidatas ya identificadas: "
            "BCRA, data912, BYMA, MAE).",
            icon="🚧",
        )
