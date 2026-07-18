"""Lugar A — Finanzas Personales (ex Mis-Finanzas-App / Radar Financiero).

El contenido es el mismo que la app original: onboarding si faltan categorías
y las cinco pestañas de siempre. Solo cambió la puerta de entrada (el shell).
"""

from __future__ import annotations

import streamlit as st

from core import workspaces_ui
from core.db import connect, get_config
from core.workspaces import ensure_personal_workspace
from places.finanzas.views import (
    configuracion,
    dashboard,
    diario,
    mensual,
    onboarding,
    transacciones,
)


def _user_completo_onboarding(user_id: int) -> bool:
    """¿El usuario ya completó la bienvenida? Se evalúa SIEMPRE contra su
    espacio personal (en un familiar no hay flag y dispararía onboarding)."""
    with connect() as conn:
        ws_personal = ensure_personal_workspace(conn, user_id)
        flag = get_config(conn, "onboarding_completado", "0",
                          user_id=user_id, workspace_id=ws_personal)
        if flag == "1":
            return True
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM categorias WHERE workspace_id = ?",
            (ws_personal,),
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
    if st.session_state.get("active_workspace_kind") == "familiar":
        workspaces_ui.render_badge(grande=True)

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
