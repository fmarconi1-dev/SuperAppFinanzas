"""Subida e import de archivos, y el estado vacío de la pantalla.

**El orden importa:** los instrumentos (hoja `Config`) van primero, porque el
import de movimientos necesita el mapa de tickers para derivar `ticker_base`.
Sin eso las variantes en dólares quedan sueltas y el dedupe impide que se
autocorrijan después.
"""

from __future__ import annotations

import streamlit as st

from core.db import connect
from core.market_data import guardar_precio_en_cache
from core.market_data.mep import serie_mep_con_fallback
from places.inversiones.cartera.parser import parse_archivo_excel
from places.inversiones.cartera.ingest import (
    TIPO_DESCONOCIDO,
    TIPO_EXCEL_PROPIO,
    TIPO_EXPORT_APP,
    TIPO_MOVIMIENTOS,
    TIPO_TENENCIA,
    cargar_instrumentos_en_db,
    congelar_tc_mep,
    detectar_tipo,
    importar_movimientos,
    remapear_tickers_base,
)
from places.inversiones.cartera.tenencias import (
    guardar_foto,
    parse_tenencias,
)
from places.inversiones.cartera.paneles._datos import (
    _instrumentos_de_db,
    _mep_actual,
    _precios_cacheados,
)


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
