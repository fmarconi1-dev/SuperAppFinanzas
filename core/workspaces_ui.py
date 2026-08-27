"""UI compartida del grupo familiar: badge de modo, switcher y activación.

Mitigaciones del premortem #5 aplicadas acá:
  - Badge grande y de color distinto por modo (Personal violeta / Familiar
    esmeralda) para no cargar en el espacio equivocado.
  - El workspace activo viaja por `st.session_state` y se baja al contextvar
    en cada rerun (`activar_desde_sesion`); los callbacks usan session_state
    explícito, nunca el contextvar.
  - `member_label` es etiqueta cosmética (se aclara en la UI), no auth.
"""

from __future__ import annotations

import sqlite3

import streamlit as st

from core.context import set_current_workspace_id
from core.workspaces import list_user_workspaces

# Tokens Cosmic Slate (ver core/theme): violeta = acento, esmeralda = positivo.
_COLOR_PERSONAL = "#8B5CF6"
_COLOR_FAMILIAR = "#10B981"


def activar_desde_sesion(conn: sqlite3.Connection) -> dict:
    """Resuelve el workspace activo desde session_state y setea el contextvar.

    Llamar en cada rerun (app.py), después del login. Si el workspace
    guardado ya no existe (p. ej. saliste del espacio), cae al personal.
    """
    uid = st.session_state["current_user_id"]
    lista = list_user_workspaces(conn, uid)  # personal primero, lo asegura
    activo_id = st.session_state.get("active_workspace_id")
    activo = next((w for w in lista if w["id"] == activo_id), None)
    if activo is None:
        activo = lista[0]  # el personal
    st.session_state["active_workspace_id"] = activo["id"]
    st.session_state["active_workspace_kind"] = activo["kind"]
    st.session_state["active_workspace_nombre"] = activo["nombre"]
    st.session_state["active_member_label"] = activo["member_label"]
    set_current_workspace_id(activo["id"])
    return activo


def _chip(kind: str, nombre: str, label: str, grande: bool) -> str:
    color = _COLOR_FAMILIAR if kind == "familiar" else _COLOR_PERSONAL
    texto = f"Espacio compartido · {nombre}" if kind == "familiar" else "Espacio personal"
    quien = f" — cargás como <b>{label}</b>" if kind == "familiar" else ""
    fs = "0.95rem" if grande else "0.8rem"
    pad = "8px 14px" if grande else "4px 10px"
    return (
        f'<div style="display:inline-flex;align-items:center;gap:8px;'
        f'background:{color}1A;border:1px solid {color};border-radius:999px;'
        f'padding:{pad};font-size:{fs};color:#E4E4E7;">'
        f'<span style="width:9px;height:9px;border-radius:50%;background:{color};"></span>'
        f'{texto}{quien}</div>'
    )


def render_badge(grande: bool = False) -> None:
    """Badge del modo activo. `grande=True` para el encabezado de página."""
    kind = st.session_state.get("active_workspace_kind", "personal")
    if not grande and kind == "personal":
        # En sidebar el personal se muestra chico; en página solo si familiar.
        pass
    st.html(_chip(
        kind,
        st.session_state.get("active_workspace_nombre", ""),
        st.session_state.get("active_member_label", ""),
        grande,
    ))


def render_switcher_sidebar(conn: sqlite3.Connection) -> None:
    """Badge + selector de espacio en la sidebar (bajo el usuario)."""
    uid = st.session_state["current_user_id"]
    lista = list_user_workspaces(conn, uid)
    render_badge(grande=False)
    if len(lista) <= 1:
        return
    por_id = {w["id"]: w for w in lista}

    def _nombre(ws_id: int) -> str:
        w = por_id[ws_id]
        return "Personal" if w["kind"] == "personal" else f"{w['nombre']} ({w['miembros']})"

    ids = list(por_id)
    actual = st.session_state.get("active_workspace_id", ids[0])
    sel = st.selectbox(
        "Espacio",
        ids,
        index=ids.index(actual) if actual in ids else 0,
        format_func=_nombre,
        key="ws_switcher",
        help="Elegí dónde mirar y cargar gastos: tu espacio personal o uno compartido.",
    )
    if sel != actual:
        st.session_state["active_workspace_id"] = sel
        st.rerun()
