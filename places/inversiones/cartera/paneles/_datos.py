"""Carga de datos de la Cartera: lo cacheado y lo que arma la foto de posiciones.

**Por qué está cacheado.** Streamlit vuelve a ejecutar el script entero en cada
click. Sin `@st.cache_data` cada interacción le pegaría de nuevo a data912, a
Yahoo y a la serie MEP.
"""

from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from core.db import connect
from core.market_data import (
    precio_yahoo,
    precios_arg,
)
from core.market_data.mep import (
    mep_para_fecha,
    serie_mep_con_fallback,
)
from core.market_data.sectores import (
    refrescar_sectores,
    sectores_para,
)
from places.inversiones.cartera.analisis import tipo_de_renta
from places.inversiones.cartera.parser import Instrumento
from places.inversiones.cartera.paneles._comun import _TTL_PRECIOS


@st.cache_data(ttl=_TTL_PRECIOS, show_spinner=False)
def _precios_cacheados() -> dict:
    return precios_arg()


@st.cache_data(ttl=_TTL_PRECIOS, show_spinner=False)
def _mep_actual() -> tuple[float | None, str]:
    with connect() as conn:
        serie, origen = serie_mep_con_fallback(conn)
    return mep_para_fecha(serie, pd.Timestamp.today().date()), origen


@st.cache_data(ttl=_TTL_PRECIOS, show_spinner=False)
def _resolver_sectores(valuadas) -> tuple[dict, dict]:
    """``(sectores, industrias)`` de la renta variable, resueltos y cacheados.

    Solo se consultan los papeles de **renta variable**: a un bono, al pagaré
    o a la cripto no les falta el sector, no tienen. La primera corrida pega
    una vez por ticker contra Yahoo; después sale todo de la caché en DB
    (incluidos los que no resolvieron, para no reintentar en cada carga).
    """
    tickers = [
        p.ticker for p in valuadas
        if not p.cerrada
        and tipo_de_renta(p.categoria_activo, p.ticker) == "Renta variable"
    ]
    with connect() as conn:
        try:
            # No lanza por la red (una falla de Yahoo no se cachea: se
            # reintenta en la próxima carga). Lo único que se tolera acá es
            # la base ocupada; un bug tiene que verse.
            refrescar_sectores(conn, tickers)
            conn.commit()
        except sqlite3.OperationalError:
            pass          # la composición se muestra igual con lo que haya
        sectores = sectores_para(conn)
        industrias = sectores_para(conn, "industria")
    # Un ETF no tiene industria: su etiqueta ("ETF · Oro") sirve para los dos
    # cortes. Si no, todos los ETF caerían juntos en "Sin dato".
    industrias = {t: industrias.get(t) or sectores.get(t) for t in sectores}
    return sectores, industrias


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
        "SELECT ticker, ticker_usd, descripcion, categoria_activo, moneda_cotiz, "
        "       tasa_anual_usd, activo "
        "FROM cartera_instrumentos WHERE user_id = ?",
        (user_id,),
    )
    return {
        r["ticker"]: Instrumento(
            ticker=r["ticker"],
            ticker_usd=r["ticker_usd"],
            # La descripción trae la fecha de vencimiento de bonos, letras y
            # ON ("Vto. 30/11/2029"): la lee `vencimientos.py`.
            descripcion=r["descripcion"] or "",
            categoria_activo=r["categoria_activo"] or "",
            moneda_cotiz=r["moneda_cotiz"] or "ARS",
            # ¡Imprescindible! Sin `activo` todo queda como vigente y las
            # letras/bonos vencidos siguen figurando con su cantidad residual
            # (el vencimiento entra como AMORTIZACION y no descuenta unidades).
            activo=bool(r["activo"]) if r["activo"] is not None else True,
        )
        for r in filas
    }
