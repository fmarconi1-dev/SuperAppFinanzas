"""Secretario — entry point y shell unificado.

La app se llamó "Radar Financiero" / "Superapp de Finanzas" hasta el
17/10/2026, cuando pasó a ser el secretario personal de Franco (ADR-0008,
Fase C). La app de Fly sigue siendo `superapp-finanzas`: Fly no deja renombrar.

Flow:
  1. init_db + migraciones (idempotente).
  2. Sin sesión → login (único para toda la app).
  3. Con sesión → contextvar de usuario + navegación entre "lugares":
     Inicio (places/inicio, la pantalla principal) y Finanzas
     (places/finanzas). Inversiones se retiró el 14/10/2026 (ADR-0007).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from core.auth import get_user_by_id, login
from core.context import set_current_user_id
from core.auth.session_tokens import QUERY_PARAM, verify_token
from core import workspaces_ui
from core.db import connect, init_db
from core.theme._responsive import apply_responsive_css
from core.theme._styles import apply_design_system_css
from places.finanzas import home as finanzas_home
from places.inicio import home as inicio_home

st.set_page_config(
    page_title="Secretario",
    # El moño en PNG (`assets/favicon.png`, lo genera scripts/generar_favicon.py):
    # un SVG en page_icon daba un TypeError de MIME.
    page_icon=str(Path(__file__).resolve().parent / "assets" / "favicon.png"),
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
            inicio_home.render,
            title="Inicio",
            icon=":material/today:",
            url_path="inicio",
            default=True,
        ),
        st.Page(
            finanzas_home.render,
            title="Finanzas",
            icon=":material/account_balance_wallet:",
            url_path="finanzas",
        ),
    ]
    st.navigation(paginas, position="top").run()


if __name__ == "__main__":
    main()
