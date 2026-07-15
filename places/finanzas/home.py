"""Lugar A — Finanzas Personales (ex Mis-Finanzas-App / Radar Financiero).

El contenido es el mismo que la app original: onboarding si faltan categorías
y las cinco pestañas de siempre. Solo cambió la puerta de entrada (el shell).
"""

from __future__ import annotations

import streamlit as st

from core.db import connect, get_config
from places.finanzas.views import (
    configuracion,
    dashboard,
    diario,
    mensual,
    onboarding,
    transacciones,
)


def _user_completo_onboarding(user_id: int) -> bool:
    """¿El usuario ya completó la pantalla de bienvenida?"""
    with connect() as conn:
        flag = get_config(conn, "onboarding_completado", "0", user_id=user_id)
        if flag == "1":
            return True
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM categorias WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["n"] > 0


def render() -> None:
    user_id = st.session_state["current_user_id"]

    # Onboarding: si todavía no hay categorías para este usuario.
    if not _user_completo_onboarding(user_id):
        onboarding.render(
            user_id=user_id,
            fullname=st.session_state.get("current_user_fullname") or "",
        )
        return

    st.title("💰 Radar Financiero")

    tab_dash, tab_txn, tab_diario, tab_mensual, tab_cfg = st.tabs(
        ["📊 Dashboard", "➕ Transacciones", "📒 Diario", "🎯 Mensual", "⚙️ Configuración"]
    )

    with tab_dash:
        dashboard.render()
    with tab_txn:
        transacciones.render()
    with tab_diario:
        diario.render()
    with tab_mensual:
        mensual.render()
    with tab_cfg:
        configuracion.render()
