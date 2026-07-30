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
    guardar_precio_en_cache,
    leer_precio_cache,
    leer_precio_mas_reciente,
    precio_yahoo,
    precios_arg,
    resolver_precio,
    set_override_precio,
)
from core.market_data.mep import mep_para_fecha, serie_mep_con_fallback
from places.inversiones.cartera.ingest import (
    TIPO_DESCONOCIDO,
    TIPO_EXCEL_PROPIO,
    TIPO_EXPORT_APP,
    TIPO_MOVIMIENTOS,
    TIPO_TENENCIA,
    cargar_instrumentos_en_db,
    congelar_tc_mep,
    corregir_movimiento,
    detectar_tipo,
    importar_movimientos,
    movimientos_de_ticker,
    remapear_tickers_base,
)
from places.inversiones.cartera.kpis import (
    completar_patrimonio,
    kpis_de,
    precio_devengado,
    valuar,
)
from places.inversiones.cartera.export import exportar_cartera
from places.inversiones.cartera.ledger import eventos_desde_db, recorrer
from places.inversiones.cartera.parser import Instrumento, parse_archivo_excel
from places.inversiones.cartera.posiciones import (
    capital_aportado,
    fecha_primera_compra,
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

#: Días que los precios de una tenencia importada siguen siendo preferibles al
#: mercado en vivo. Con la foto del día coinciden con lo que muestra el broker;
#: pasado ese margen (cubre un fin de semana largo) **caducan** y manda el
#: mercado, si no la cartera quedaría congelada en la fecha del archivo.
#: Las CANTIDADES de la tenencia no caducan: solo cambian si se opera, y eso
#: ya lo reflejan los movimientos.
_DIAS_PRECIOS_BROKER = 3


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
        "SELECT ticker, ticker_usd, categoria_activo, moneda_cotiz, "
        "       tasa_anual_usd, activo "
        "FROM cartera_instrumentos WHERE user_id = ?",
        (user_id,),
    )
    return {
        r["ticker"]: Instrumento(
            ticker=r["ticker"],
            ticker_usd=r["ticker_usd"],
            categoria_activo=r["categoria_activo"] or "",
            moneda_cotiz=r["moneda_cotiz"] or "ARS",
            # ¡Imprescindible! Sin `activo` todo queda como vigente y las
            # letras/bonos vencidos siguen figurando con su cantidad residual
            # (el vencimiento entra como AMORTIZACION y no descuenta unidades).
            activo=bool(r["activo"]) if r["activo"] is not None else True,
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


def _operaciones_cerradas(ledger) -> None:
    """Una fila por venta, con el resultado medido al PPC de ESE día (ADR-0005).

    El resultado agregado no dice qué operación salió bien: acá cada venta
    tiene su costo real del día, su plazo y su rendimiento en los dos planos
    (pesos y dólares al MEP de cada fecha).
    """
    st.markdown("#### Operaciones cerradas")
    if not ledger.realizaciones:
        st.caption("Todavía no vendiste nada: cuando lo hagas, cada venta "
                   "aparece acá con su resultado y su plazo.")
        return

    st.caption(
        "Cada venta con el costo que **realmente** tenías ese día. Es distinto "
        "del promedio de toda la historia: una compra posterior no puede "
        "cambiar lo que ganaste en una venta anterior (ver `ADR-0005`)."
    )

    res = ledger.resumen_operaciones()

    def _tono(v: float) -> tuple[str, str, str]:
        return ("positivo", "▲", "+") if v >= 0 else ("negativo", "▼", "−")

    t_ars, f_ars, s_ars = _tono(res["total_ars"])
    t_usd, f_usd, s_usd = _tono(res["total_usd"])
    mejor = res["mejor"]
    o1, o2, o3 = st.columns(3)
    with o1:
        st.html(_kpi_card(
            "Realizado en pesos", f"{s_ars}{_fmt(abs(res['total_ars']), 0, '$')}",
            f"{f_ars} {res['n']} operaciones cerradas", t_ars))
    with o2:
        st.html(_kpi_card(
            "Realizado en dólares", f"{s_usd}US$ {_fmt(abs(res['total_usd']), 0)}",
            f"{f_usd} al MEP del día de cada operación", t_usd))
    with o3:
        ctx = (f"la mejor: {mejor.ticker} {_fmt(mejor.rendimiento_pct, 1)}%"
               if mejor is not None else "—")
        if res["a_revisar"]:
            ctx += f" · {res['a_revisar']} a revisar"
        st.html(_kpi_card("Aciertos", f"{res['ganadoras']} de {res['n']}", ctx))

    st.dataframe(
        pd.DataFrame(ledger.tabla_operaciones()),
        hide_index=True, use_container_width=True,
        column_config={
            "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Unidades": st.column_config.NumberColumn(format="%.2f"),
            "PPC del día": st.column_config.NumberColumn(
                format="$ %.2f",
                help="Costo promedio ponderado vigente al momento de vender"),
            "Precio venta": st.column_config.NumberColumn(format="$ %.2f"),
            "Resultado": st.column_config.NumberColumn(format="$ %.0f"),
            "Rend. %": st.column_config.NumberColumn(format="%.1f%%"),
            "Rend. US$ %": st.column_config.NumberColumn(
                format="%.1f%%",
                help="En dólares, al MEP del día de la compra y de la venta"),
            "Días": st.column_config.NumberColumn(
                format="%d",
                help="Plazo contra la fecha de compra promedio ponderada"),
            "Aviso": st.column_config.TextColumn(
                help="revisar = se vendieron más unidades de las registradas "
                     "en los movimientos; el excedente se cerró sin costo"),
        },
    )

    if ledger.advertencias:
        with st.expander(
            f"Operaciones a revisar ({len(ledger.advertencias)})"
        ):
            st.caption(
                "El motor nunca inventa costo: cuando los movimientos no "
                "alcanzan (ajustes de ratio de CEDEAR, pagarés sin cantidad), "
                "lo dice en vez de completar el número."
            )
            for a in ledger.advertencias:
                st.markdown(f"- {a}")


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


def _importar_todo(archivos, user_id: int) -> None:
    """Carga completa en un paso: detecta cada archivo y lo procesa en orden.

    El **orden importa** y por eso lo decide la app, no el usuario:

    1. **Config** del Excel propio → los instrumentos, que el parser necesita
       para clasificar tickers y saber qué bonos cotizan por cada 100.
    2. **Crudo del Excel propio** → trae los **saldos iniciales sintéticos**,
       que el export del broker NO tiene. Sin esto el capital aportado queda
       subvaluado (US$4.941 en vez de US$11.534 — ver ESTADO.md).
    3. **Movimientos del broker** → lo nuevo desde entonces (el dedupe evita
       duplicar lo que ya estaba).
    4. **Tenencia** → cantidades y precios de referencia + su caché.
    5. **TC MEP** congelado en las filas que falten.
    """
    clasificados: dict[str, list] = {}
    for a in archivos:
        clasificados.setdefault(detectar_tipo(a), []).append(a)

    # El export de la propia app se confunde con el Excel propio (mismo
    # nombre inicial, misma carpeta): avisar cuál es el que hace falta.
    del_app = clasificados.get(TIPO_EXPORT_APP, [])
    if del_app:
        st.warning(
            "**"
            + ", ".join(getattr(a, "name", "?") for a in del_app)
            + "** es un resumen que generó esta app, no tu planilla. El que "
            "hace falta es tu **Inversiones.xlsx** (el que tiene las hojas "
            "Config y Movimientos Crudo).",
            icon=":material/info:")
    desconocidos = clasificados.get(TIPO_DESCONOCIDO, [])
    if desconocidos:
        st.warning(
            "No pude reconocer: "
            + ", ".join(getattr(a, "name", "?") for a in desconocidos)
            + ". Se ignoran. Los archivos esperados son tu **Inversiones.xlsx**, "
            "el export de **movimientos** y el de **tenencias** de inviu.",
            icon=":material/warning:")

    resumen: list[str] = []
    with connect() as conn:
        # 1 y 2 — el Excel propio: instrumentos + base histórica.
        for a in clasificados.get(TIPO_EXCEL_PROPIO, []):
            n_inst = cargar_instrumentos_en_db(conn, a, user_id)
            conn.commit()
            resumen.append(f"{n_inst} instrumentos")
            instrumentos = _instrumentos_de_db(conn, user_id)
            movs = parse_archivo_excel(
                a, hoja="Movimientos Crudo", instrumentos=instrumentos)
            if movs:
                ins, _ = importar_movimientos(conn, movs, user_id)
                resumen.append(f"{ins} movimientos históricos (con saldos iniciales)")

        instrumentos = _instrumentos_de_db(conn, user_id)
        # Reparación: si antes se importó sin el mapa, las variantes USD
        # quedaron sin plegar (SPYD aparte de SPY). El dedupe no lo corrige
        # solo, así que se recalcula acá.
        if instrumentos:
            arregladas = remapear_tickers_base(conn, instrumentos, user_id)
            if arregladas:
                resumen.append(f"{arregladas} tickers reagrupados")
        if not instrumentos:
            st.warning(
                "Falta tu **Inversiones.xlsx** (el que tiene las hojas Config y "
                "Movimientos Crudo). Sin él: los tickers no se clasifican, no "
                "se sabe qué bonos cotizan por cada 100 nominales, y **faltan "
                "tus tenencias iniciales** — el capital aportado va a quedar "
                "subvaluado. Subilo y volvé a apretar *Importar todo*: no se "
                "duplica nada.", icon=":material/warning:")

        # 3 — movimientos del broker.
        for a in clasificados.get(TIPO_MOVIMIENTOS, []):
            movs = parse_archivo_excel(a, instrumentos=instrumentos)
            if movs:
                ins, skip = importar_movimientos(conn, movs, user_id)
                resumen.append(
                    f"{ins} movimientos nuevos del broker"
                    + (f" ({skip} ya estaban)" if skip else ""))

        # 4 — tenencia + caché de sus precios.
        for a in clasificados.get(TIPO_TENENCIA, []):
            foto_nueva = parse_tenencias(a)
            n_pos = guardar_foto(conn, foto_nueva, user_id)
            for t in foto_nueva.posiciones:
                if t.precio:
                    guardar_precio_en_cache(
                        conn, t.ticker, t.precio, foto_nueva.fecha_valuacion,
                        fuente="broker")
            conn.commit()
            resumen.append(
                f"tenencia al {foto_nueva.fecha_valuacion:%d/%m/%Y} "
                f"({n_pos} posiciones)")

        # 5 — congelar el TC de cada operación.
        serie, _ = serie_mep_con_fallback(conn)
        congelados, sin_tc = congelar_tc_mep(conn, serie, user_id)
        if congelados:
            resumen.append(f"TC del día congelado en {congelados} filas")

    st.success("Listo: " + " · ".join(resumen), icon=":material/check_circle:")
    if sin_tc:
        st.info(
            f"{len(sin_tc)} fecha(s) sin cotización de MEP: "
            f"{', '.join(sin_tc[:3])}{'…' if len(sin_tc) > 3 else ''}.",
            icon=":material/info:")
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
        # Línea de tiempo: el resultado de cada venta se mide con el PPC
        # vigente ESE día, no con el promedio de toda la historia (ADR-0005).
        ledger = recorrer(eventos_desde_db(conn, uid))
        hay_movimientos = conn.execute(
            "SELECT 1 FROM cartera_movimientos WHERE user_id = ? LIMIT 1", (uid,)
        ).fetchone() is not None
        foto = ultima_foto(conn, uid)

    with st.expander("Cargar archivos", expanded=not hay_movimientos):
        st.caption(
            "Arrastrá los tres juntos y listo — la app reconoce cada uno por su "
            "contenido y los procesa en el orden correcto: tu **Excel** "
            "(instrumentos + histórico con los saldos iniciales), los "
            "**movimientos** del broker (inviu → Movimientos → Todos) y la "
            "**tenencia** (inviu → Tenencias). Subir el mismo archivo dos veces "
            "no duplica nada."
        )
        archivos = st.file_uploader(
            "Tus archivos (.xlsx)",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="cartera_upload_todo",
        )
        if archivos:
            detectados = {}
            for a in archivos:
                detectados.setdefault(detectar_tipo(a), []).append(
                    getattr(a, "name", "?"))
            etiquetas = {
                TIPO_EXCEL_PROPIO: "Excel propio (Config + histórico)",
                TIPO_MOVIMIENTOS: "Movimientos del broker",
                TIPO_TENENCIA: "Tenencia del broker",
                TIPO_EXPORT_APP: "Resumen generado por la app (no hace falta)",
                TIPO_DESCONOCIDO: "No reconocido",
            }
            st.caption("Reconocí: " + " · ".join(
                f"**{etiquetas.get(t, t)}**" for t in detectados))
        if st.button(
            "Importar todo", type="primary", key="cartera_btn_importar_todo",
            disabled=not archivos, use_container_width=False,
        ):
            with st.spinner("Procesando…"):
                _importar_todo(archivos, uid)
            st.rerun()

    if not hay_movimientos:
        _empty_state()
        return

    precios = _precios_cacheados()
    mep, origen_mep = _mep_actual()

    with connect() as conn:
        tasas_devengadas = {
            r["ticker"]: r["tasa_anual_usd"]
            for r in conn.execute(
                "SELECT ticker, tasa_anual_usd FROM cartera_instrumentos "
                "WHERE user_id = ? AND tasa_anual_usd IS NOT NULL", (uid,))
        }

    # Los precios de la foto solo valen mientras esté fresca (ver
    # _DIAS_PRECIOS_BROKER); si no, la cartera quedaría clavada en la fecha
    # del archivo y no reflejaría el mercado de hoy.
    dias_foto = (
        (pd.Timestamp.today().date() - foto.fecha_valuacion).days
        if foto is not None and foto.fecha_valuacion else None
    )
    foto_fresca = dias_foto is not None and dias_foto <= _DIAS_PRECIOS_BROKER
    precios_broker = (
        {t.ticker: t.precio for t in foto.posiciones if t.precio}
        if foto is not None and foto_fresca else {}
    )

    def _resolver(ticker: str, inst) -> tuple[float | None, str]:
        with connect() as conn:
            # 1) Override manual: siempre gana (incluida la cripto).
            manual = leer_precio_cache(conn, ticker)
            if manual is not None and manual[1]:
                return manual[0], "override"
            # 2) Instrumentos sin mercado cuyo precio el broker NO informa:
            #    se devenga la tasa pactada. Solo aplica si se cargó una tasa.
            #    OJO: si el broker informa precio, ESE manda — un pagaré se
            #    compra a descuento y su precio converge al nominal, así que el
            #    valor del custodio ya refleja la ganancia devengada.
            tasa = tasas_devengadas.get(ticker)
            if tasa:
                p = posiciones.get(ticker)
                f_compra = fecha_primera_compra(conn, uid, ticker)
                if p is not None and f_compra is not None:
                    pd_ = precio_devengado(
                        p.costo_usd_hist, p.cant_actual, f_compra, fecha_val,
                        tasa, mep or 0.0,
                    )
                    if pd_:
                        return pd_, "devengado"
            # 3) Precio del broker: cuando hay tenencia importada, es el que
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
            # 4) Mercado en vivo / caché de hoy.
            precio, origen = resolver_precio(
                conn, ticker, precios_proveedor=precios,
                divide_por_100=bool(inst and inst.divide_por_100),
            )
            if precio is not None:
                return precio, origen
            # 5) Último precio conocido (instrumentos ilíquidos: el pagaré no
            #    cotiza en ningún panel, su precio solo viene de la tenencia).
            ultimo = leer_precio_mas_reciente(conn, ticker)
            if ultimo is not None:
                return ultimo[0], "última tenencia"
            return None, "sin_dato"

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

    valuadas = valuar(posiciones, _resolver, instrumentos, mep_actual=mep,
                      cronologico=ledger.plano_por_ticker())
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

    if foto is None:
        fuente_precios = "Precios de mercado en vivo (data912 · yahoo para cripto)."
    elif foto_fresca:
        fuente_precios = (
            f"Precios de tu tenencia del {foto.fecha_valuacion:%d/%m} — misma "
            "valuación que ves en el broker."
        )
    else:
        fuente_precios = (
            f"Tu tenencia es del {foto.fecha_valuacion:%d/%m} ({dias_foto} días): "
            "sus precios caducaron, se usan los de **mercado en vivo**. Las "
            "cantidades siguen siendo las del broker."
        )
    st.caption(
        f"{fuente_precios} Costo a promedio ponderado y dólar congelado a la "
        "fecha de cada operación."
    )

    _operaciones_cerradas(ledger)

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
            # Precargado con la última cantidad informada por Franco, para que
            # sea confirmar en vez de tipear. Se cambia cuando compra o vende.
            cant_ext = st.number_input(
                "Cantidad", min_value=0.0, step=0.00001, format="%.8f",
                value=float(manuales.get(tk_ext.strip().upper() if tk_ext else "",
                                         0.00316847)),
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

    with st.expander("Instrumentos que devengan una tasa (pagarés, cheques)"):
        st.caption(
            "Los pagarés y cheques de pago diferido no cotizan: rinden la tasa "
            "que pactaste. Cargá esa tasa y la app los valúa devengando desde "
            "la compra, en vez de usar el precio de referencia del broker "
            "(que puede no reflejarla)."
        )
        d1, d2, d3 = st.columns([2, 2, 1])
        with d1:
            tk_dev = st.selectbox(
                "Instrumento",
                [p.ticker for p in valuadas] or [""],
                key="cartera_dev_ticker")
        with d2:
            tasa_dev = st.number_input(
                "Tasa anual en dólares (%)", min_value=0.0, max_value=200.0,
                step=0.5, value=10.0, format="%.2f", key="cartera_dev_tasa")
        with d3:
            st.write("")
            if st.button("Aplicar", key="cartera_btn_dev", disabled=not tk_dev):
                with connect() as conn:
                    conn.execute(
                        "INSERT INTO cartera_instrumentos "
                        "(ticker, user_id, categoria_activo, moneda_cotiz, "
                        " tasa_anual_usd) VALUES (?, ?, 'Pagares', 'ARS', ?) "
                        "ON CONFLICT(ticker, user_id) DO UPDATE SET "
                        "  tasa_anual_usd = excluded.tasa_anual_usd",
                        (tk_dev, uid, tasa_dev / 100.0),
                    )
                    conn.commit()
                st.success(f"{tk_dev} devenga {tasa_dev:.2f}% anual en dólares.",
                           icon=":material/check_circle:")
                st.rerun()
        if tasas_devengadas:
            st.caption("Configurados: " + " · ".join(
                f"{t} {v * 100:.2f}% anual" for t, v in tasas_devengadas.items()))

    with st.expander("Corregir un movimiento mal informado por el broker"):
        st.caption(
            "El broker se equivoca: la compra de ASML del 16/5/2025 vino con "
            "**dos ceros de menos** (9 unidades a $60,10 en vez de $6.010). "
            "Corregilo acá y **corregí también la misma fila en tu Excel, con "
            "los mismos valores**: la app recalcula la huella del movimiento "
            "para que al reimportar el Excel lo reconozca en vez de cargarlo "
            "de nuevo. Si solo arreglás el Excel, la compra queda **duplicada**."
        )
        tk_corr = st.text_input("Ticker", key="cartera_corr_ticker",
                                placeholder="ASML")
        if tk_corr:
            with connect() as conn:
                movs_tk = movimientos_de_ticker(conn, uid, tk_corr)
            if not movs_tk:
                st.caption(f"No hay movimientos de {tk_corr.strip().upper()}.")
            else:
                etiquetas = {
                    f"{m['fecha_concertacion'][:10]} · {m['categoria']} · "
                    f"{m['cantidad']:g} u · {_fmt(m['monto'], 2, '$')}": m
                    for m in movs_tk
                }
                elegido = etiquetas[st.selectbox(
                    "Movimiento", list(etiquetas), key="cartera_corr_mov")]
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    nuevo_monto = st.number_input(
                        "Monto (con su signo)", value=float(elegido["monto"]),
                        step=1.0, format="%.2f", key="cartera_corr_monto")
                with c2:
                    nuevo_precio = st.number_input(
                        "Precio por unidad", value=float(elegido["precio"]),
                        step=1.0, format="%.4f", key="cartera_corr_precio")
                with c3:
                    st.write("")
                    if st.button("Corregir", key="cartera_btn_corr"):
                        with connect() as conn:
                            ok = corregir_movimiento(
                                conn, uid, elegido["id"],
                                monto=nuevo_monto, precio=nuevo_precio)
                            conn.commit()
                        if ok:
                            st.success(
                                "Movimiento corregido. **Poné los mismos "
                                f"valores en tu Excel** (monto "
                                f"{_fmt(nuevo_monto, 2, '$')}, precio "
                                f"{_fmt(nuevo_precio, 2, '$')}) para que la "
                                "próxima importación no lo duplique.",
                                icon=":material/check_circle:")
                            st.rerun()
                        else:
                            st.info("No había nada que cambiar.",
                                    icon=":material/info:")

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

    # ---- Export a Excel --------------------------------------------------
    col_exp, col_ref = st.columns([1, 3])
    with col_exp:
        import io
        from datetime import date as _date
        buf = io.BytesIO()
        nombres = {t.ticker: t.nombre for t in foto.posiciones} if foto else {}
        tipos = {
            t.ticker: ("Pagarés" if t.ticker.startswith("#") else t.tipo_activo)
            for t in (foto.posiciones if foto else [])
        }
        for tk in manuales:
            inst_m = instrumentos.get(tk)
            tipos.setdefault(tk, getattr(inst_m, "categoria_activo", "") or "Externo")
        exportar_cartera(
            buf, valuadas, k, fecha_val, mep,
            fuente_precios, nombres=nombres, tipos=tipos,
            efectivo_ars=cash_ars, efectivo_usd=cash_usd,
        )
        st.download_button(
            "Descargar Excel", data=buf.getvalue(),
            file_name=f"Cartera - Resumen {fecha_val:%Y-%m-%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="cartera_btn_export", use_container_width=True,
            help="Resumen con KPIs, posiciones por tipo, subtotales y "
                 "rendimiento anualizado. Con fórmulas: si cambiás el MEP, "
                 "la planilla recalcula.",
        )
    with col_ref:
        pass

    if st.button("Actualizar precios", key="cartera_btn_refrescar"):
        _precios_cacheados.clear()
        _mep_actual.clear()
        st.rerun()
