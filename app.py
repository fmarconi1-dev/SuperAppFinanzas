"""Superapp de Finanzas — entry point y shell unificado (Fase 2).

Flow:
  1. init_db + migraciones (idempotente).
  2. Sin sesión → login (único para toda la superapp).
  3. Con sesión → contextvar de usuario + navegación entre "lugares":
     🏠 Finanzas Personales (places/finanzas) · 📈 Inversiones (places/inversiones).
"""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from core.auth import get_user_by_id, login
from core.auth.current_user import set_current_user_id
from core.auth.session_tokens import QUERY_PARAM, verify_token
from core import workspaces_ui
from core.db import connect, init_db
from core.theme._responsive import apply_responsive_css
from core.theme._styles import apply_design_system_css
from places.finanzas import home as finanzas_home
from places.inversiones import home as inversiones_home

st.set_page_config(
    page_title="Superapp de Finanzas",
    page_icon="💸",  # emoji en page_icon (no SVG): evita el TypeError de MIME
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS del sistema de diseño (Cosmic Slate) — inyectar primero para evitar FOUC.
apply_responsive_css()
apply_design_system_css()


def _try_restore_session_from_token() -> None:
    """Si hay un token de sesión válido en la URL, restaura la sesión."""
    token = st.query_params.get(QUERY_PARAM)
    if not token:
        return
    uid = verify_token(token)
    if uid is None:
        del st.query_params[QUERY_PARAM]
        return
    with connect() as conn:
        user = get_user_by_id(conn, uid)
    if user is None:
        del st.query_params[QUERY_PARAM]
        return
    st.session_state["logged_in"] = True
    st.session_state["current_user_id"] = user["id"]
    st.session_state["current_username"] = user["username"]
    st.session_state["current_user_fullname"] = user["fullname"]


@st.cache_resource
def _inicializar_db() -> bool:
    """Schema + migraciones, **una sola vez por proceso**.

    Antes esto corría dentro de `main()`, o sea en **cada rerun de Streamlit**:
    cada click volvía a ejecutar el schema entero y las 13 migraciones. Son
    idempotentes, así que el resultado era correcto, pero cada interacción
    pedía el lock de escritura para hacer `ALTER TABLE` y `CREATE INDEX` que ya
    estaban hechos.

    El 4/8/2026 eso reventó en producción: cargar un ajuste de tenencia dispara
    un `st.rerun()`, el rerun corrió las migraciones mientras el backup previo
    todavía tenía la base tomada, y la app murió con `database is locked` en
    `_migrate`. Correrlas una vez por proceso saca la colisión de raíz — y de
    paso le quita trabajo a cada click.
    """
    init_db()
    return True


def main() -> None:
    _inicializar_db()

    # Restaurar sesión desde token firmado en la URL (si SESSION_SECRET está
    # configurado). Evita el re-login en cada refresh.
    if not st.session_state.get("logged_in"):
        _try_restore_session_from_token()

    # Auth gate — un solo login para todos los lugares.
    if not st.session_state.get("logged_in"):
        login.render()
        return

    set_current_user_id(st.session_state["current_user_id"])

    # Workspace activo (grupo familiar D2): resolver y bajar al contextvar.
    with connect() as conn:
        workspaces_ui.activar_desde_sesion(conn)

    login.render_logout_button()
    with st.sidebar:
        with connect() as conn:
            workspaces_ui.render_switcher_sidebar(conn)

    # Navegación entre lugares (barra superior).
    paginas = [
        st.Page(
            finanzas_home.render,
            title="Finanzas",
            icon=":material/home:",
            url_path="finanzas",
            default=True,
        ),
        st.Page(
            inversiones_home.render,
            title="Inversiones",
            icon=":material/monitoring:",
            url_path="inversiones",
        ),
    ]
    st.navigation(paginas, position="top").run()


if __name__ == "__main__":
    main()
