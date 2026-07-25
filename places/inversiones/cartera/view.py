"""Vista de Cartera (Lugar B.1) — Fase 3a, paso 4.

Diseño según la skill `ui-ux-web-moderno`, extendiendo el sistema Cosmic Slate
del proyecto (tokens `--cs-*` de `core/theme/_styles.py`, sin hex ad-hoc):

  * KPI cards con label muted → cifra grande **tabular-nums** → contexto;
    ganancia/pérdida con **signo + flecha + color** (nunca color solo).
  * Tabla densa con cifras a la derecha, formato es-AR y columnas tipadas.
  * Estados completos: **empty** con acción (subir el export), **error**
    con causa y salida, y aviso cuando un precio no se pudo resolver.
  * Scope por usuario: la cartera es personal (ADR-0003).

La carga pesada (precios, MEP) va cacheada para no pegarle a las APIs en cada
rerun de Streamlit.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from core.db import connect
from core.market_data import precio_yahoo, precios_arg, resolver_precio
from core.market_data.mep import mep_para_fecha, serie_mep_con_fallback
from places.inversiones.cartera.ingest import (
    cargar_instrumentos_en_db,
    congelar_tc_mep,
    importar_movimientos,
)
from places.inversiones.cartera.kpis import kpis_de, valuar
from places.inversiones.cartera.parser import Instrumento, parse_archivo_excel
from places.inversiones.cartera.posiciones import posiciones_desde_db

#: Usuarios habilitados a ver Cartera (ADR-0003: "solo Franco por ahora,
#: generalizable"). Cada usuario ve SU cartera; la lista solo controla el
#: acceso a la sección. Configurable por env sin tocar código.
_USUARIOS_HABILITADOS = os.environ.get("CARTERA_USER_IDS", "1")

_TTL_PRECIOS = 300  # segundos: 5 min de caché en memoria para el panel vivo


def _habilitado(user_id: int) -> bool:
    permitidos = {
        int(x) for x in _USUARIOS_HABILITADOS.replace(" ", "").split(",") if x
    }
    return not permitidos or user_id in permitidos


# ---------------------------------------------------------------------------
# Datos (cacheados: no pegarle a las APIs en cada rerun)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_PRECIOS, show_spinner=False)
def _precios_cacheados() -> dict:
    return precios_arg()


@st.cache_data(ttl=_TTL_PRECIOS, show_spinner=False)
def _mep_actual() -> tuple[float | None, str]:
    with connect() as conn:
        serie, origen = serie_mep_con_fallback(conn)
    return mep_para_fecha(serie, pd.Timestamp.today().date()), origen


@st.cache_data(ttl=_TTL_PRECIOS, show_spinner=False)
def _precio_btc_usd() -> float | None:
    """BTC no cotiza en el mercado local: se toma de yahoo, en USD."""
    return precio_yahoo("BTC-USD")


def _instrumentos_de_db(conn, user_id: int) -> dict[str, Instrumento]:
    filas = conn.execute(
        "SELECT ticker, ticker_usd, categoria_activo, moneda_cotiz "
        "FROM cartera_instrumentos WHERE user_id = ?",
        (user_id,),
    )
    return {
        r["ticker"]: Instrumento(
            ticker=r["ticker"],
            ticker_usd=r["ticker_usd"],
            categoria_activo=r["categoria_activo"] or "",
            moneda_cotiz=r["moneda_cotiz"] or "ARS",
        )
        for r in filas
    }


# ---------------------------------------------------------------------------
# Formato (es-AR) y componentes
# ---------------------------------------------------------------------------

def _fmt(n: float | None, dec: int = 2, prefijo: str = "") -> str:
    if n is None:
        return "—"
    s = f"{n:,.{dec}f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"{prefijo}{s}"


def _kpi_card(label: str, valor: str, contexto: str = "", tono: str = "") -> str:
    color = {
        "positivo": "var(--cs-positive)",
        "negativo": "var(--cs-negative)",
    }.get(tono, "var(--cs-text)")
    ctx = (
        f'<div style="font-size:12px;color:{color};margin-top:6px;'
        f'font-variant-numeric:tabular-nums;">{contexto}</div>'
        if contexto else ""
    )
    return f"""
    <div style="background:var(--cs-bg-1);border:1px solid var(--cs-border);
                border-radius:var(--cs-radius-md);padding:16px 18px;height:100%;">
      <div style="font-size:12px;color:var(--cs-text-mid);
                  text-transform:uppercase;letter-spacing:.04em;">{label}</div>
      <div style="font-size:28px;font-weight:700;color:var(--cs-text);
                  font-family:var(--cs-font-mono);font-variant-numeric:tabular-nums;
                  margin-top:8px;line-height:1.15;">{valor}</div>
      {ctx}
    </div>
    """


def _empty_state() -> None:
    st.html(
        """
        <div style="background:var(--cs-bg-1);border:1px dashed var(--cs-border);
                    border-radius:var(--cs-radius-lg);padding:32px;text-align:center;">
          <div style="font-size:17px;font-weight:600;color:var(--cs-text);">
            Todavía no hay movimientos cargados</div>
          <div style="font-size:14px;color:var(--cs-text-mid);margin-top:8px;
                      max-width:520px;margin-inline:auto;line-height:1.5;">
            Subí el export de movimientos de tu broker (inviu → Movimientos →
            Todos) y la cartera se arma sola: posiciones, costo promedio y
            resultado. Podés volver a subir el mismo archivo sin miedo: los
            movimientos repetidos se ignoran.</div>
        </div>
        """
    )


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------

def _procesar_carga(archivo, user_id: int) -> None:
    """Importa el export subido: instrumentos → movimientos → TC congelado."""
    with connect() as conn:
        instrumentos = _instrumentos_de_db(conn, user_id)
        if not instrumentos:
            st.warning(
                "No hay instrumentos configurados todavía: los tickers no se "
                "van a poder mapear a su moneda y categoría. Cargá primero el "
                "mapa de instrumentos desde tu Excel (hoja Config).",
                icon=":material/warning:",
            )
        movimientos = parse_archivo_excel(archivo, instrumentos=instrumentos)
        if not movimientos:
            st.error(
                "El archivo no tiene movimientos reconocibles. ¿Es el export "
                "de movimientos del broker?",
                icon=":material/error:",
            )
            return
        insertados, saltados = importar_movimientos(conn, movimientos, user_id)
        serie, _ = serie_mep_con_fallback(conn)
        congelados, sin_tc = congelar_tc_mep(conn, serie, user_id)

    st.success(
        f"Listo: {insertados} movimientos nuevos"
        + (f" · {saltados} ya estaban (no se duplicaron)" if saltados else "")
        + (f" · TC del día congelado en {congelados} filas" if congelados else ""),
        icon=":material/check_circle:",
    )
    if sin_tc:
        st.info(
            f"{len(sin_tc)} fecha(s) sin cotización de MEP: "
            f"{', '.join(sin_tc[:3])}{'…' if len(sin_tc) > 3 else ''}. "
            "Se pueden cargar a mano más adelante.",
            icon=":material/info:",
        )
    _precios_cacheados.clear()
    _mep_actual.clear()


# ---------------------------------------------------------------------------
# Vista
# ---------------------------------------------------------------------------

def render(user_id: int | None = None) -> None:
    uid = user_id if user_id is not None else st.session_state.get("current_user_id")
    if uid is None:
        st.info("Iniciá sesión para ver tu cartera.", icon=":material/lock:")
        return
    if not _habilitado(uid):
        st.info(
            "La sección Cartera está habilitada solo para tu usuario principal.",
            icon=":material/lock:",
        )
        return

    with connect() as conn:
        posiciones = posiciones_desde_db(conn, uid)
        instrumentos = _instrumentos_de_db(conn, uid)
        hay_movimientos = conn.execute(
            "SELECT 1 FROM cartera_movimientos WHERE user_id = ? LIMIT 1", (uid,)
        ).fetchone() is not None

    with st.expander("Cargar movimientos del broker", expanded=not hay_movimientos):
        archivo = st.file_uploader(
            "Export de movimientos (.xlsx)",
            type=["xlsx", "csv"],
            key="cartera_upload",
            help="inviu → Movimientos → Todos → Exportar. Reimportar el mismo "
                 "archivo no duplica nada.",
        )
        col_a, col_b = st.columns([1, 2])
        with col_a:
            if st.button(
                "Importar movimientos", type="primary", key="cartera_btn_importar",
                disabled=archivo is None, use_container_width=True,
            ):
                with st.spinner("Procesando el export…"):
                    _procesar_carga(archivo, uid)
                st.rerun()
        with col_b:
            excel = st.text_input(
                "Ruta del Excel para el mapa de instrumentos (opcional)",
                key="cartera_ruta_config",
                placeholder=r"C:\...\Inversiones.xlsx",
                help="Lee la hoja Config: ticker base, variante USD, categoría "
                     "y moneda de cotización.",
            )
            if excel and st.button("Cargar instrumentos", key="cartera_btn_config"):
                try:
                    with connect() as conn:
                        n = cargar_instrumentos_en_db(conn, excel, uid)
                        conn.commit()
                    st.success(f"{n} instrumentos actualizados.",
                               icon=":material/check_circle:")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001 — se muestra al usuario
                    st.error(f"No se pudo leer la hoja Config: {exc}",
                             icon=":material/error:")

    if not hay_movimientos:
        _empty_state()
        return

    precios = _precios_cacheados()
    mep, origen_mep = _mep_actual()

    def _resolver(ticker: str, inst) -> tuple[float | None, str]:
        with connect() as conn:
            # Cripto: no cotiza en el mercado local → yahoo (USD) pasado a ARS
            # por el MEP, para que conviva con el resto de la cartera.
            if inst is not None and inst.categoria_activo == "Cripto":
                btc = _precio_btc_usd()
                if btc and mep:
                    return btc * mep, "proveedor"
            return resolver_precio(
                conn, ticker, precios_proveedor=precios,
                divide_por_100=bool(inst and inst.divide_por_100),
            )

    valuadas = valuar(posiciones, _resolver, instrumentos)
    k = kpis_de(valuadas, mep)

    # ---- KPIs -----------------------------------------------------------
    tono = "positivo" if k.resultado_ars >= 0 else "negativo"
    flecha = "▲" if k.resultado_ars >= 0 else "▼"
    signo = "+" if k.resultado_ars >= 0 else "−"
    rend = (
        f"{flecha} {signo}{_fmt(abs(k.rendimiento_pct), 1)}% sobre el costo"
        if k.rendimiento_pct is not None else "—"
    )

    st.container(key="cartera_kpis")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.html(_kpi_card("Valor de cartera", _fmt(k.valor_total_ars, 0, "$"),
                          f"{k.posiciones_valuadas} posiciones valuadas"))
    with c2:
        st.html(_kpi_card("Valor en dólares",
                          _fmt(k.valor_total_usd, 0, "US$") if k.valor_total_usd else "—",
                          f"MEP {_fmt(mep, 2, '$')} · {origen_mep}"))
    with c3:
        st.html(_kpi_card("Resultado no realizado",
                          f"{signo}{_fmt(abs(k.resultado_ars), 0, '$')}",
                          rend, tono))
    with c4:
        st.html(_kpi_card("Costo invertido", _fmt(k.costo_total_ars, 0, "$"),
                          "costo promedio ponderado"))

    if k.posiciones_sin_precio:
        st.warning(
            f"{k.posiciones_sin_precio} posición(es) sin precio de mercado: no "
            "entran en los totales. Podés fijarles un precio manual.",
            icon=":material/warning:",
        )

    # ---- Tabla de posiciones -------------------------------------------
    st.markdown("#### Posiciones")
    df = pd.DataFrame([
        {
            "Ticker": p.ticker,
            "Tipo": p.categoria_activo,
            "Cantidad": p.cantidad,
            "PPC": p.ppc_ars,
            "Precio": p.precio,
            "Valor": p.valor_ars,
            "Resultado": p.resultado_ars,
            "Rend. %": p.rendimiento_pct,
            "Precio de": p.origen_precio,
        }
        for p in valuadas
    ])
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Cantidad": st.column_config.NumberColumn(format="%.2f"),
            "PPC": st.column_config.NumberColumn(format="$ %.2f"),
            "Precio": st.column_config.NumberColumn(format="$ %.2f"),
            "Valor": st.column_config.NumberColumn(format="$ %.0f"),
            "Resultado": st.column_config.NumberColumn(format="$ %.0f"),
            "Rend. %": st.column_config.NumberColumn(format="%.1f%%"),
            "Precio de": st.column_config.TextColumn(
                help="proveedor = precio en vivo · cache = último conocido · "
                     "override = fijado a mano"
            ),
        },
    )

    st.caption(
        "Valuación a precio de mercado; costo a promedio ponderado. El dólar de "
        "cada operación queda congelado a la fecha en que se hizo."
    )
    if st.button("Actualizar precios", key="cartera_btn_refrescar"):
        _precios_cacheados.clear()
        _mep_actual.clear()
        st.rerun()
