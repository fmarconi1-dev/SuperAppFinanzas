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

---

**Este archivo es el orquestador, no la pantalla entera** (split del 27/8/2026).
Tenía 1.990 líneas y lo tocaba el **28% de los commits del repo** — cualquier
cambio en un panel obligaba a abrirlo completo, y así se coló el `backup_db`
sin importar que atajó `tests/test_nombres_definidos.py`.

Ahora cada panel vive en `paneles/`:

    _comun.py      formato es-AR, KPI card, TTL de caché
    _datos.py      lo cacheado (precios, MEP, sectores) y la foto de posiciones
    composicion.py "Cómo está repartida"
    mercado.py     "Contra el mercado" (benchmark money-weighted)
    vencimientos.py "Qué se te vence"
    renta_fija.py  "Cuándo cobrás" (cronogramas, TIR, duration)
    operaciones.py "Operaciones cerradas"
    caja.py        "La plata quieta"
    ajustes.py     ajustes de tenencia (M13)
    importar.py    subida de archivos y estado vacío

Acá quedan el gate de acceso y `render()`: resolver datos, los KPIs de arriba,
la tabla de posiciones y el orden en que se llaman los paneles. **El split movió
código, no lo cambió**: los paneles se reimportan con el mismo nombre, así que
`render()` quedó igual.
"""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
import streamlit as st

from core.db import backup_db, connect
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
from core.market_data.sectores import (
    refrescar_sectores,
    sectores_para,
    set_override_sector,
)
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
from places.inversiones.cartera.analisis import (
    SIN_DATO,
    por_emisor,
    por_pais,
    por_sector,
    por_tipo_de_renta,
    tipo_de_renta,
)
from places.inversiones.cartera import ajustes as mod_ajustes
from places.inversiones.cartera import renta_fija as mod_rf
from places.inversiones.cartera import vencimientos as mod_venc
from places.inversiones.cartera import benchmark as mod_bench
from core.market_data import indices as mod_indices
from core.market_data import cronogramas as mod_cron
from places.inversiones.cartera.export import exportar_cartera
from places.inversiones.cartera.ledger import eventos_desde_db, recorrer
from places.inversiones.cartera.parser import Instrumento, parse_archivo_excel
from places.inversiones.cartera.rendimientos import (
    cauciones_desde_db,
    flujos_caja_desde_db,
    resumir_cauciones,
)
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

# --- Los paneles ------------------------------------------------------------
# Cada uno vive en su archivo desde el split del 27/8/2026. Se importan con el
# MISMO nombre que tenían acá adentro, así `render()` no cambió una línea.
from places.inversiones.cartera.paneles._comun import _TTL_PRECIOS, _fmt, _kpi_card
from places.inversiones.cartera.paneles._datos import (
    _aplicar_tenencia,
    _instrumentos_de_db,
    _mep_actual,
    _precio_btc_usd,
    _precios_cacheados,
    _resolver_sectores,
)
from places.inversiones.cartera.paneles.ajustes import _panel_ajustes
from places.inversiones.cartera.paneles.caja import _rendimiento_caja
from places.inversiones.cartera.paneles.composicion import _composicion
from places.inversiones.cartera.paneles.importar import (
    _empty_state,
    _importar_todo,
    _procesar_carga,
)
from places.inversiones.cartera.paneles.mercado import _benchmark
from places.inversiones.cartera.paneles.operaciones import _operaciones_cerradas
from places.inversiones.cartera.paneles.renta_fija import _renta_fija
from places.inversiones.cartera.paneles.vencimientos import _vencimientos

#: Usuarios habilitados a ver Cartera (ADR-0003: "solo Franco por ahora,
#: generalizable"). Cada usuario ve SU cartera; la lista solo controla el
#: acceso a la sección. Configurable por env sin tocar código.
_USUARIOS_HABILITADOS = os.environ.get("CARTERA_USER_IDS", "1")


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


# ---------------------------------------------------------------------------
# Formato (es-AR) y componentes
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------


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
        # Rendimiento de la plata que no está en una posición (punto 3 de 3b).
        cs_caucion = cauciones_desde_db(conn, uid)
        divs, rem = flujos_caja_desde_db(conn, uid)
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
            f"{'▲' if tot_usd >= 0 else '▼'} {_fmt(k.rendimiento_total_usd_pct, 1)}%",
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

    _benchmark(flujos, k, uid)

    # ---- Tabla de posiciones -------------------------------------------
    st.markdown("#### Posiciones")
    ver_cerradas = st.checkbox(
        "Mostrar posiciones cerradas (vencidas o vendidas)",
        value=False, key="cartera_ver_cerradas",
        help="Ya no tienen tenencia, pero su rendimiento cuenta en el total.",
    )
    st.caption(
        "**Esta tabla es tu posición viva**: lo que vale hoy contra lo que te "
        "costó lo que todavía tenés. Es el mismo número que ves en el broker. "
        "Los trades ya cerrados **no se mezclan acá** — cada uno tiene su "
        "propio rendimiento en *Operaciones cerradas*, más abajo."
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
            "US$": p.valor_usd_actual,
            "No realizado": None if p.cerrada else p.no_realizado_ars,
            "Rend. %": None if p.cerrada else p.rendimiento_vivo_pct,
            "Rend. US$ %": None if p.cerrada else p.rendimiento_vivo_usd_pct,
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
            "PPC": st.column_config.NumberColumn(
                format="localized", step=0.01,
                help="Costo promedio ponderado de lo que tenés hoy"),
            "Precio": st.column_config.NumberColumn(format="localized", step=0.01),
            "Valor": st.column_config.NumberColumn(format="localized", step=1),
            "US$": st.column_config.NumberColumn(format="localized", step=1),
            "No realizado": st.column_config.NumberColumn(
                format="localized", step=1,
                help="Valor de hoy menos el costo de lo que tenés. NO incluye "
                     "ventas pasadas ni dividendos: eso vive en Operaciones "
                     "cerradas y en el bloque de arriba",
            ),
            "Rend. %": st.column_config.NumberColumn(format="%.1f%%"),
            "Rend. US$ %": st.column_config.NumberColumn(
                format="%.1f%%",
                help="En dólares, contra el costo de la tenencia al MEP del día "
                     "de cada compra. Es el comparable con la pantalla del "
                     "broker: si no coincide, hay un problema real",
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

    sectores, industrias = _resolver_sectores(valuadas)
    _composicion(valuadas, cash_ars + (cash_usd * mep if mep else 0.0),
                 sectores, industrias, mep, uid)

    _vencimientos(valuadas, instrumentos, uid)

    _renta_fija(valuadas, instrumentos, uid)

    _operaciones_cerradas(ledger)

    _rendimiento_caja(cs_caucion, resumir_cauciones(cs_caucion), divs, rem)

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

    _panel_ajustes(uid)

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
