"""Vista del scoring embebido (Lugar B.2) — solo lectura del snapshot.

El cálculo vive en el batch (GitHub Actions); esta vista jamás recalcula.
Conceptos (fieles a src/scoring.py del repo Scoring-Inversiones):
  - Categoría (excluyentes): Triple corona · Emergente de calidad · Resto.
  - Señal (independiente): qué score superó el corte — Fundamental, Técnico,
    ambos, o ninguna. La señal NO es una categoría.
UI según skill ui-ux-web-moderno: cifras tabulares, símbolo+texto (no solo
color), estados load/empty/error completos, keys explícitas en los filtros
para que el estado sobreviva a los reruns.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from places.inversiones.scoring.snapshot import cargar_snapshot, refrescar

TABLERO_PUBLICO = "https://fmarconi1-dev.github.io/Scoring-Inversiones/"

# Categorías excluyentes (símbolo + texto: legible sin depender del color).
CATEGORIAS = {
    "triple_corona_madura": "★ Triple corona",
    "emergente_calidad": "▲ Emergente de calidad",
    "otros": "· Resto",
}
_ORDEN_CATEGORIA = {v: i for i, v in enumerate(CATEGORIAS.values())}

# Señal: qué score superó su corte (no es una categoría).
SENALES = {
    "triple_corona": "Fundamental + Técnica",
    "fundamental": "Fundamental",
    "tecnico": "Técnica",
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
            "Categoría": CATEGORIAS.get(e.get("categoria"), e.get("categoria") or "· Resto"),
            "Señal": SENALES.get(e.get("sub_veredicto"), e.get("sub_veredicto") or "—"),
            "Yahoo": f"https://finance.yahoo.com/quote/{e.get('yf', e.get('ticker'))}",
        })
    return pd.DataFrame(filas)


def _fecha_corta(generado: str) -> str:
    """'2026-07-14 22:57' → '14/07/2026'. Si no parsea, devuelve tal cual."""
    try:
        from datetime import datetime
        return datetime.strptime(generado.strip(), "%Y-%m-%d %H:%M").strftime("%d/%m/%Y")
    except (ValueError, AttributeError):
        return generado


def _render_metodologia(snapshot: dict) -> None:
    """Popover '?' con la metodología de scores y categorías."""
    cf = snapshot.get("corte_fundamental", 70)
    ct = snapshot.get("corte_tecnico", 70)
    ce = snapshot.get("corte_emergente", 70)
    with st.popover("?", help="Cómo se calculan los puntajes y las categorías"):
        st.markdown(f"""
##### Cómo leer este tablero

**Puntajes (0 a 100)** — los calcula el batch diario, acá solo se muestran:

- **Fundamental** — múltiplos estilo value: P/E, P/B, ROE, Deuda/Equity y
  margen neto, cada uno puntuado contra umbrales "excelente / aceptable".
  En bancos/financieras el D/E no es significativo: se excluye y se
  reponderan las demás métricas.
- **Técnico** — 5 indicadores sumados: precio sobre MM200 (30 pts), cruce
  MM50>MM200 (20), RSI(14) en zona sana 40–65 (20), MACD sobre su señal
  (15) y OBV en alza (15).
- **Emergente** — track para empresas nacientes: crecimiento de ingresos
  (30%), margen bruto (22%), supervivencia/runway (14%), Regla del 40
  (12%), valuación (12%) e insiders (10%).

**Categorías** (excluyentes — cada empresa está en una sola):

- **★ Triple corona** — Fundamental ≥ {cf} **y** Técnico ≥ {ct}, con al
  menos 3 métricas fundamentales disponibles. Lo mejor de ambos mundos.
- **▲ Emergente de calidad** — Emergente ≥ {ce} en empresas nacientes
  (market cap bajo el techo configurado; no mega-caps). Si además logra
  triple corona, prevalece Triple corona.
- **· Resto** — no alcanzó ninguna de las dos anteriores.

**Señal** (independiente de la categoría): indica qué puntaje superó su
corte — *Fundamental*, *Técnica*, ambas, o ninguna (—). Una empresa del
Resto puede tener señal técnica, por ejemplo: pasó el corte técnico pero
no el fundamental.

Con menos de 3 métricas fundamentales la empresa **no se clasifica** (se
muestra igual, sin forzar veredicto). Umbrales y cortes viven en la config
del repo Scoring-Inversiones. *No es recomendación de inversión.*
""")


def _render_error() -> None:
    st.error(
        "No pude traer el snapshot del scoring (sin red y sin copia local). "
        "El tablero público puede seguir disponible.",
        icon="⚠️",
    )
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Reintentar", type="primary", key="sc_retry"):
            refrescar()
            st.rerun()
    with col2:
        st.link_button("Abrir tablero público", TABLERO_PUBLICO)


def render() -> None:
    snapshot, origen = cargar_snapshot()

    if snapshot is None:
        _render_error()
        return

    # --- Encabezado: procedencia + metodología + refresh ---
    generado = snapshot.get("generado", "¿?")
    izq, ayuda, der = st.columns([5, 1, 2])
    with izq:
        if origen == "cache_local":
            st.warning(
                f"Sin conexión con el tablero — mostrando la última copia local "
                f"(generada {generado}).",
                icon="📴",
            )
        else:
            st.caption(
                f"Actualización al día {_fecha_corta(generado)} · "
                f"[tablero público]({TABLERO_PUBLICO})"
            )
    with ayuda:
        _render_metodologia(snapshot)
    with der:
        if st.button("↻ Actualizar", help="Vuelve a leer el snapshot publicado", key="sc_refresh"):
            refrescar()
            st.rerun()

    df = _df_empresas(snapshot)
    if df.empty:
        st.info("El snapshot no trae empresas. Revisá el batch en GitHub Actions.")
        return

    # --- KPIs por categoría ---
    n_triple = int((df["Categoría"] == CATEGORIAS["triple_corona_madura"]).sum())
    n_emerg = int((df["Categoría"] == CATEGORIAS["emergente_calidad"]).sum())
    n_resto = int((df["Categoría"] == CATEGORIAS["otros"]).sum())
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Universo", f"{len(df)}")
    k2.metric("★ Triple corona", f"{n_triple}")
    k3.metric("▲ Emergentes de calidad", f"{n_emerg}")
    k4.metric("· Resto", f"{n_resto}")

    # --- Filtro principal: categoría (chips, selección persistente) ---
    cat_sel = st.segmented_control(
        "Categoría",
        options=list(CATEGORIAS.values()),
        selection_mode="multi",
        key="sc_categorias",
    )

    f1, f2 = st.columns([1, 3])
    with f1:
        grupo = st.selectbox(
            "Mercado",
            ["Todos"] + sorted(df["Grupo"].dropna().unique()),
            key="sc_grupo",
        )
    with f2:
        buscar = st.text_input(
            "Buscar",
            placeholder="Ticker, nombre o sector…",
            key="sc_buscar",
        )

    vista = df
    if cat_sel:
        vista = vista[vista["Categoría"].isin(cat_sel)]
    if grupo != "Todos":
        vista = vista[vista["Grupo"] == grupo]
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

    # --- Tabla: agrupada por categoría (★ → ▲ → Resto), mejores scores primero ---
    vista = vista.assign(_orden=vista["Categoría"].map(_ORDEN_CATEGORIA)).sort_values(
        ["_orden", "Fundamental", "Técnico"], ascending=[True, False, False]
    ).drop(columns="_orden")
    # Categoría primero: que se vea de un vistazo quién está en cuál.
    columnas = ["Categoría", "Ticker", "Nombre", "Señal", "Fundamental", "Técnico",
                "Emergente", "Precio", "Grupo", "Sector", "Yahoo"]
    st.dataframe(
        vista[columnas],
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
