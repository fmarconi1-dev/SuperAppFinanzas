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
from core.market_data import (
    leer_precio_cache,
    precio_yahoo,
    precios_arg,
    resolver_precio,
    set_override_precio,
)
from core.market_data.mep import mep_para_fecha, serie_mep_con_fallback
from places.inversiones.cartera.ingest import (
    cargar_instrumentos_en_db,
    congelar_tc_mep,
    importar_movimientos,
)
from places.inversiones.cartera.kpis import completar_patrimonio, kpis_de, valuar
from places.inversiones.cartera.parser import Instrumento, parse_archivo_excel
from places.inversiones.cartera.posiciones import (
    capital_aportado,
    flujos_de_capital,
    posiciones_desde_db,
    saldos_efectivo,
)
from places.inversiones.cartera.tenencias import (
    comparar_con_movimientos,
    guardar_foto,
    parse_tenencias,
    set_tenencia_manual,
    tenencias_manuales,
    ultima_foto,
)

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


def _aplicar_tenencia(posiciones: dict, foto, instrumentos: dict) -> dict:
    """Cruza las posiciones derivadas de movimientos con la foto del broker.

    * Ticker **en la tenencia** → manda la cantidad del broker (cubre pagarés
      sin cantidad y ajustes de ratio que no generan movimiento).
    * Ticker **ausente** de la tenencia → se conserva lo derivado de
      movimientos: hay tenencias reales fuera del broker (el **Bitcoin**, que
      no está en inviu). Las posiciones cerradas ya dan 0 por su marca de
      instrumento inactivo, así que no ensucian.
    """
    from places.inversiones.cartera.posiciones import Posicion

    fusionadas = dict(posiciones)
    for t in foto.posiciones:
        p = fusionadas.get(t.ticker)
        if p is None:
            # Posición que los movimientos no conocen (p. ej. el pagaré):
            # se crea con la cantidad del broker. Sin costo derivable: su
            # "resultado" queda en 0 hasta que haya de dónde sacarlo.
            p = Posicion(t.ticker)
            fusionadas[t.ticker] = p
        p.cant_broker = t.cantidad
    return fusionadas


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
        instrumentos = _instrumentos_de_db(conn, uid)
        posiciones = posiciones_desde_db(conn, uid, instrumentos or None)
        hay_movimientos = conn.execute(
            "SELECT 1 FROM cartera_movimientos WHERE user_id = ? LIMIT 1", (uid,)
        ).fetchone() is not None
        foto = ultima_foto(conn, uid)

    with st.expander("Cargar movimientos del broker", expanded=not hay_movimientos):
        archivo = st.file_uploader(
            "Export de movimientos (.xlsx)",
            type=["xlsx", "csv"],
            key="cartera_upload",
            help="inviu → Movimientos → Todos → Exportar. Reimportar el mismo "
                 "archivo no duplica nada.",
        )
        archivo_ten = st.file_uploader(
            "Tenencia del broker (.xlsx) — opcional pero recomendado",
            type=["xlsx"],
            key="cartera_upload_tenencia",
            help="inviu → Tenencias → Exportar. Necesaria para las posiciones "
                 "que los movimientos no permiten derivar: pagarés/cheques (que "
                 "no traen cantidad) y ajustes de ratio de CEDEARs.",
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
            if st.button(
                "Importar tenencia", key="cartera_btn_tenencia",
                disabled=archivo_ten is None, use_container_width=True,
            ):
                try:
                    nueva = parse_tenencias(archivo_ten)
                    with connect() as conn:
                        n = guardar_foto(conn, nueva, uid)
                    st.success(
                        f"Tenencia al {nueva.fecha_valuacion:%d/%m/%Y} importada: "
                        f"{n} posiciones.", icon=":material/check_circle:")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001 — se muestra al usuario
                    st.error(f"No se pudo leer la tenencia: {exc}",
                             icon=":material/error:")
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

    precios_broker = (
        {t.ticker: t.precio for t in foto.posiciones if t.precio}
        if foto is not None else {}
    )

    def _resolver(ticker: str, inst) -> tuple[float | None, str]:
        with connect() as conn:
            # 1) Override manual: siempre gana (incluida la cripto).
            manual = leer_precio_cache(conn, ticker)
            if manual is not None and manual[1]:
                return manual[0], "override"
            # 2) Precio del broker: cuando hay tenencia importada, es el que
            #    usa la valuación oficial de esa fecha. Así los totales de la
            #    app coinciden con lo que muestra el broker, en vez de diferir
            #    por unos pesos según el momento del feed en vivo.
            if ticker in precios_broker:
                return precios_broker[ticker], "broker"
            # 3) Cripto: no cotiza en el mercado local → yahoo (USD) a ARS.
            if inst is not None and inst.categoria_activo == "Cripto":
                btc = _precio_btc_usd()
                if btc and mep:
                    return btc * mep, "proveedor"
            # 4) Mercado en vivo / caché.
            return resolver_precio(
                conn, ticker, precios_proveedor=precios,
                divide_por_100=bool(inst and inst.divide_por_100),
            )

    # La tenencia del broker manda sobre las cantidades: hay posiciones que
    # los movimientos no permiten derivar (pagarés sin cantidad, ajustes de
    # ratio). Los movimientos siguen aportando costos e histórico.
    difs = []
    if foto is not None:
        difs = comparar_con_movimientos(foto, posiciones)
        posiciones = _aplicar_tenencia(posiciones, foto, instrumentos)

    # Tenencias cargadas a mano: activos que no están en el broker (el BTC
    # vive en Binance). Mandan sobre lo derivado de movimientos, que solo
    # conoce el saldo inicial.
    with connect() as conn:
        manuales = tenencias_manuales(conn, uid)
    for tk, cant in manuales.items():
        p = posiciones.get(tk)
        if p is None:
            from places.inversiones.cartera.posiciones import Posicion
            p = posiciones[tk] = Posicion(tk)
        p.cant_broker = cant

    valuadas = valuar(posiciones, _resolver, instrumentos, mep_actual=mep)
    k = kpis_de(valuadas, mep)
    with connect() as conn:
        capital = capital_aportado(conn, uid)
        cash_ars, cash_usd = saldos_efectivo(conn, uid)
        flujos = flujos_de_capital(conn, uid)
    if foto is not None:
        cash_ars, cash_usd = foto.efectivo_ars, foto.efectivo_usd
    fecha_val = (
        foto.fecha_valuacion if foto is not None
        else pd.Timestamp.today().date()
    )
    completar_patrimonio(k, capital, cash_ars, cash_usd, mep, flujos, fecha_val)

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

    if foto is not None:
        st.caption(
            f"Posiciones según la tenencia del broker al "
            f"{foto.fecha_valuacion:%d/%m/%Y}"
            + (f" · {len(difs)} diferencia(s) contra los movimientos" if difs else
               " · coincide con los movimientos")
        )
        if difs:
            with st.expander(f"Reconciliación contra el broker ({len(difs)})"):
                st.caption(
                    "Diferencias entre lo que informa el broker y lo que se "
                    "puede derivar de los movimientos. Son esperables en "
                    "pagarés (el movimiento no trae cantidad), ajustes de "
                    "ratio de CEDEARs y tenencias fuera del broker (Bitcoin)."
                )
                st.dataframe(
                    pd.DataFrame(difs).rename(columns={
                        "ticker": "Ticker", "broker": "Broker",
                        "movimientos": "Movimientos", "diferencia": "Diferencia"}),
                    hide_index=True, use_container_width=True,
                )
    else:
        st.info(
            "Subí también la **tenencia del broker** para que las posiciones "
            "sean exactas: hay activos que los movimientos no permiten "
            "reconstruir (pagarés y cheques no traen cantidad, y los ajustes "
            "de ratio de CEDEARs no generan movimiento).",
            icon=":material/info:",
        )

    if k.posiciones_sin_precio:
        st.warning(
            f"{k.posiciones_sin_precio} posición(es) sin precio de mercado: no "
            "entran en los totales. Podés fijarles un precio manual.",
            icon=":material/warning:",
        )

    # ---- Rendimiento histórico total (incluye lo cobrado y lo vendido) ---
    periodo = (
        f" · {k.meses:.0f} meses ({k.anios:.1f} años)" if k.dias else ""
    )
    st.markdown(f"#### Cómo te fue en total{periodo}")
    st.caption(
        "Lo que hoy vale todo (tenencia + efectivo) contra el capital que "
        "realmente aportaste (depósitos − retiros). Cada aporte se convierte "
        "al MEP del día en que se hizo, así el rendimiento en dólares refleja "
        "el tipo de cambio real de cada movimiento."
    )
    tot_ars, tot_usd = k.resultado_total_ars, k.resultado_total_usd
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.html(_kpi_card("Capital aportado", _fmt(k.aportado_ars, 0, "$"),
                          f"US$ {_fmt(k.aportado_usd, 0)} al TC de cada aporte"))
    with r2:
        st.html(_kpi_card("Patrimonio hoy", _fmt(k.patrimonio_ars, 0, "$"),
                          f"US$ {_fmt(k.patrimonio_usd, 0)} · tenencia + efectivo"))
    with r3:
        st.html(_kpi_card(
            "Resultado en pesos",
            f"{'+' if tot_ars >= 0 else '−'}{_fmt(abs(tot_ars), 0, '$')}",
            f"{'▲' if tot_ars >= 0 else '▼'} {_fmt(k.rendimiento_total_pct, 1)}%",
            "positivo" if tot_ars >= 0 else "negativo"))
    with r4:
        st.html(_kpi_card(
            "Resultado en dólares",
            f"{'+' if tot_usd >= 0 else '−'}US$ {_fmt(abs(tot_usd), 0)}",
            f"{'▲' if tot_usd >= 0 else '▼'} {_fmt(k.rendimiento_total_usd_pct, 1)}%"
            " · el número que importa",
            "positivo" if tot_usd >= 0 else "negativo"))
    if k.tir_usd is not None or k.tir_ars is not None:
        t1, t2 = st.columns(2)
        with t1:
            st.html(_kpi_card(
                "Rendimiento anual en dólares",
                f"{_fmt((k.tir_usd or 0) * 100, 1)}%",
                "TIR: pondera cuánto tiempo estuvo invertido cada aporte",
                "positivo" if (k.tir_usd or 0) >= 0 else "negativo"))
        with t2:
            st.html(_kpi_card(
                "Rendimiento anual en pesos",
                f"{_fmt((k.tir_ars or 0) * 100, 1)}%",
                f"acumulado en {k.meses:.0f} meses",
                "positivo" if (k.tir_ars or 0) >= 0 else "negativo"))

    st.caption(
        f"Cobrado en el camino: {_fmt(k.flujos_ars, 0, '$')} de amortizaciones, "
        f"rentas y dividendos (ya incluido arriba). El resultado por ticker de "
        "la tabla no suma al total: al convertir dólares a pesos, la "
        "devaluación infla los resultados individuales. La tasa anual es la "
        "TIR, no el acumulado dividido por los años: cada aporte estuvo "
        "invertido un plazo distinto."
    )

    # ---- Tabla de posiciones -------------------------------------------
    st.markdown("#### Posiciones")
    ver_cerradas = st.checkbox(
        "Mostrar posiciones cerradas (vencidas o vendidas)",
        value=False, key="cartera_ver_cerradas",
        help="Ya no tienen tenencia, pero su rendimiento cuenta en el total.",
    )
    filas = [p for p in valuadas if ver_cerradas or not p.cerrada]
    df = pd.DataFrame([
        {
            "Ticker": p.ticker,
            "Tipo": p.categoria_activo,
            "Estado": "cerrada" if p.cerrada else "abierta",
            "Cantidad": p.cantidad,
            "PPC": p.ppc_ars,
            "Precio": p.precio,
            "Valor": p.valor_ars,
            "Resultado": p.resultado_ars,
            "Rend. %": p.rendimiento_pct,
            "Rend. US$ %": p.rendimiento_usd_pct,
            "Precio de": p.origen_precio,
        }
        for p in filas
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
            "Resultado": st.column_config.NumberColumn(
                format="$ %.0f",
                help="Ventas + cobros + no realizado, menos el capital que amortizó",
            ),
            "Rend. %": st.column_config.NumberColumn(format="%.1f%%"),
            "Rend. US$ %": st.column_config.NumberColumn(
                format="%.1f%%",
                help="Rendimiento en dólares, al MEP del día de cada operación",
            ),
            "Precio de": st.column_config.TextColumn(
                help="proveedor = precio en vivo · cache = último conocido · "
                     "override = fijado a mano · cerrada = sin tenencia"
            ),
        },
    )

    st.caption(
        "Cuando hay tenencia importada se usan los precios del broker (misma "
        "valuación que ves en tu cuenta); si no, precios de mercado. Costo a "
        "promedio ponderado y dólar congelado a la fecha de cada operación."
    )

    with st.expander("Activos fuera del broker (cripto, otras cuentas)"):
        st.caption(
            "Cantidades que el broker no informa porque el activo está en otro "
            "lado (por ejemplo Bitcoin en Binance). El precio se busca solo; "
            "vos solo mantenés la cantidad."
        )
        e1, e2, e3 = st.columns([2, 2, 1])
        with e1:
            tk_ext = st.text_input("Ticker", value="BITCOIN",
                                   key="cartera_ext_ticker")
        with e2:
            cant_ext = st.number_input(
                "Cantidad", min_value=0.0, step=0.00001, format="%.8f",
                key="cartera_ext_cant")
        with e3:
            st.write("")
            if st.button("Guardar", key="cartera_btn_ext",
                         disabled=not (tk_ext and cant_ext)):
                with connect() as conn:
                    set_tenencia_manual(conn, uid, tk_ext.strip().upper(),
                                        cant_ext)
                    conn.commit()
                st.success(f"Tenencia de {tk_ext.upper()} actualizada.",
                           icon=":material/check_circle:")
                st.rerun()
        if manuales:
            st.caption("Cargadas: " + " · ".join(
                f"{t} {c:g}" for t, c in manuales.items()))

    with st.expander("Corregir un precio a mano"):
        st.caption(
            "Útil para lo que no cotiza en el mercado local (Bitcoin) o si un "
            "precio automático no refleja tu valuación. El precio manual gana "
            "sobre cualquier fuente."
        )
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            tk_ov = st.selectbox(
                "Activo", [p.ticker for p in valuadas], key="cartera_ov_ticker")
        with c2:
            val_ov = st.number_input(
                "Precio (en pesos, por unidad)", min_value=0.0, step=100.0,
                format="%.2f", key="cartera_ov_precio")
        with c3:
            st.write("")
            if st.button("Fijar", key="cartera_btn_override", disabled=not val_ov):
                with connect() as conn:
                    set_override_precio(conn, tk_ov, val_ov)
                    conn.commit()
                st.success(f"Precio de {tk_ov} fijado.",
                           icon=":material/check_circle:")
                st.rerun()

    if st.button("Actualizar precios", key="cartera_btn_refrescar"):
        _precios_cacheados.clear()
        _mep_actual.clear()
        st.rerun()
