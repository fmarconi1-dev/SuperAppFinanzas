"""Vista del scoring embebido (Lugar B.2) — solo lectura del snapshot.

Muestra KPIs, filtros y tabla del universo clasificado. El cálculo vive en
el batch (GitHub Actions); esta vista jamás toca yfinance ni recalcula.
UI según skill ui-ux-web-moderno: cifras tabulares, estados load/empty/error
completos, categoría codificada por texto (no solo color).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from places.inversiones.scoring.snapshot import SNAPSHOT_URL, cargar_snapshot, refrescar

TABLERO_PUBLICO = "https://fmarconi1-dev.github.io/Scoring-Inversiones/"

# Etiquetas legibles por categoría (texto, no solo color — accesibilidad).
CATEGORIAS = {
    "triple_corona_madura": "Triple corona (madura)",
    "emergente_calidad": "Emergente de calidad",
    "otros": "Sin señal",
}
SUB_VEREDICTOS = {
    "triple_corona": "Fundamental + Técnico",
    "fundamental": "Fundamental",
    "tecnico": "Técnico",
    "ninguna": "—",
}


def _df_empresas(snapshot: dict) -> pd.DataFrame:
    filas = []
    for e in snapshot.get("empresas", []):
        filas.append({
            "Ticker": e.get("ticker"),
            "Nombre": e.get("nombre"),
            "Grupo": e.get("grupo"),
            "Sector": e.get("sector"),
            "Precio": e.get("precio"),
            "Fundamental": e.get("score_fundamental"),
            "Técnico": e.get("score_tecnico"),
            "Emergente": e.get("score_emergente"),
            "Categoría": CATEGORIAS.get(e.get("categoria"), e.get("categoria") or "—"),
            "Señal": SUB_VEREDICTOS.get(e.get("sub_veredicto"), e.get("sub_veredicto") or "—"),
            "Yahoo": f"https://finance.yahoo.com/quote/{e.get('yf', e.get('ticker'))}",
        })
    return pd.DataFrame(filas)


def _render_error() -> None:
    st.error(
        "No pude traer el snapshot del scoring (sin red y sin copia local). "
        "El tablero público puede seguir disponible.",
        icon="⚠️",
    )
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Reintentar", type="primary"):
            refrescar()
            st.rerun()
    with col2:
        st.link_button("Abrir tablero público", TABLERO_PUBLICO)


def render() -> None:
    snapshot, origen = cargar_snapshot()

    if snapshot is None:
        _render_error()
        return

    # --- Encabezado: procedencia de los datos ---
    generado = snapshot.get("generado", "¿?")
    izq, der = st.columns([3, 1])
    with izq:
        if origen == "cache_local":
            st.warning(
                f"Sin conexión con el tablero — mostrando la última copia local "
                f"(generada {generado}).",
                icon="📴",
            )
        else:
            st.caption(
                f"Snapshot generado {generado} · batch diario en GitHub Actions · "
                f"[tablero público]({TABLERO_PUBLICO})"
            )
    with der:
        if st.button("↻ Actualizar", help="Vuelve a leer el snapshot publicado"):
            refrescar()
            st.rerun()

    df = _df_empresas(snapshot)
    if df.empty:
        st.info("El snapshot no trae empresas. Revisá el batch en GitHub Actions.")
        return

    # --- KPIs ---
    n_triple = int((df["Categoría"] == CATEGORIAS["triple_corona_madura"]).sum())
    n_emerg = int((df["Categoría"] == CATEGORIAS["emergente_calidad"]).sum())
    n_cambios = len(snapshot.get("cambios", []))
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Universo", f"{len(df)}")
    k2.metric("Triple corona", f"{n_triple}")
    k3.metric("Emergentes de calidad", f"{n_emerg}")
    k4.metric("Cambios recientes", f"{n_cambios}")

    # --- Filtros ---
    f1, f2, f3 = st.columns([1, 2, 2])
    with f1:
        grupo = st.selectbox("Mercado", ["Todos"] + sorted(df["Grupo"].dropna().unique()))
    with f2:
        cats = st.multiselect("Categoría", sorted(df["Categoría"].unique()), placeholder="Todas")
    with f3:
        buscar = st.text_input("Buscar", placeholder="Ticker, nombre o sector…")

    vista = df
    if grupo != "Todos":
        vista = vista[vista["Grupo"] == grupo]
    if cats:
        vista = vista[vista["Categoría"].isin(cats)]
    if buscar:
        b = buscar.strip().lower()
        mask = (
            vista["Ticker"].str.lower().str.contains(b, na=False)
            | vista["Nombre"].str.lower().str.contains(b, na=False)
            | vista["Sector"].str.lower().str.contains(b, na=False)
        )
        vista = vista[mask]

    if vista.empty:
        st.info("Ningún papel coincide con esos filtros. Probá limpiarlos.")
        return

    # --- Tabla (orden: mejores señales primero) ---
    vista = vista.sort_values(["Fundamental", "Técnico"], ascending=False)
    st.dataframe(
        vista,
        hide_index=True,
        width="stretch",
        column_config={
            "Precio": st.column_config.NumberColumn(format="$ %.2f"),
            "Fundamental": st.column_config.ProgressColumn(
                format="%.0f", min_value=0, max_value=100),
            "Técnico": st.column_config.ProgressColumn(
                format="%.0f", min_value=0, max_value=100),
            "Emergente": st.column_config.ProgressColumn(
                format="%.0f", min_value=0, max_value=100),
            "Yahoo": st.column_config.LinkColumn(display_text="Ver ↗"),
        },
    )

    # --- Cambios recientes ---
    cambios = snapshot.get("cambios", [])
    if cambios:
        with st.expander(f"Cambios de categoría en la última corrida ({len(cambios)})"):
            for c in cambios:
                desde = CATEGORIAS.get(c.get("desde"), c.get("desde"))
                hacia = CATEGORIAS.get(c.get("hacia"), c.get("hacia"))
                st.markdown(f"- **{c.get('ticker')}**: {desde} → {hacia}")

    st.caption(
        "El scoring se calcula en batch (GitHub Actions), la app solo lee el "
        "snapshot. No es recomendación de inversión."
    )
