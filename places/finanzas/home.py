"""Lugar A — Finanzas Personales (ex Mis-Finanzas-App / Radar Financiero, hoy dentro de Secretario).

El contenido es el mismo que la app original: onboarding si faltan categorías
y las cinco pestañas de siempre. Solo cambió la puerta de entrada (el shell).
"""

from __future__ import annotations

from importlib import import_module

import streamlit as st

from core import workspaces_ui
from core.db import connect, get_config
from core.workspaces import ensure_personal_workspace
from places.finanzas.views import onboarding


#: Etiqueta de cada pestaña → el módulo de su vista, en el orden en que se
#: muestran. La vista se importa recién al abrir su pestaña: el Inicio (la
#: pantalla principal) importa este módulo, y antes eso traía las cinco vistas
#: con Plotly y todo en cada arranque en frío, aunque nadie abriera Finanzas
#: (frente 2 de rendimiento, 21/10/2026).
PESTANAS = {
    ":material/dashboard: Dashboard": "places.finanzas.views.dashboard",
    ":material/add_circle: Transacciones": "places.finanzas.views.transacciones",
    ":material/menu_book: Diario": "places.finanzas.views.diario",
    ":material/target: Mensual": "places.finanzas.views.mensual",
    ":material/settings: Configuración": "places.finanzas.views.configuracion",
}

#: En `st.session_state[CLAVE_PESTANA]` queda la etiqueta de la pestaña abierta.
CLAVE_PESTANA = "finanzas_pestana"

#: Filtros de las vistas que sobreviven a cambiar de pestaña. Streamlit borra el
#: estado de un widget que no se dibujó en una corrida, y con las pestañas
#: diferidas eso pasa en cuanto abrís otra: volvías al Dashboard y estaba otra
#: vez en "Este mes". Reasignarlos al principio de cada corrida corta esa
#: limpieza (lo documenta Streamlit). Solo filtros: un botón no se puede
#: asignar, y un formulario a medio llenar se pierde a propósito.
FILTROS_QUE_PERSISTEN = ("dash_periodo", "dash_anio", "ma_ventanas",
                         "donut_agrupar_por", "diario_dias")


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

    st.title(":material/account_balance_wallet: Finanzas")
    if st.session_state.get("active_workspace_kind") == "familiar":
        workspaces_ui.render_badge(grande=True)

    # Solo corre la pestaña abierta (`on_change="rerun"` + `.open`). Antes
    # corrían las cinco en cada click, se viera la que se viera: 1,2 s por
    # rerun contra ~60 ms del Inicio (`docs/perf/LINEA-BASE.md`). El costo:
    # cambiar de pestaña ahora es un rerun, de esa sola pestaña.
    for clave in FILTROS_QUE_PERSISTEN:
        if clave in st.session_state:
            st.session_state[clave] = st.session_state[clave]
    pestanas = st.tabs(list(PESTANAS), key=CLAVE_PESTANA, on_change="rerun")
    for pestana, vista in zip(pestanas, PESTANAS.values()):
        if pestana.open:
            with pestana:
                import_module(vista).render()
