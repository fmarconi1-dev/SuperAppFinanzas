"""Panel "Contra el mercado": la cartera contra SPY o Merval, money-weighted.

La aritmética vive en `cartera/benchmark.py` y la serie del índice en
`core/market_data/indices.py`; acá solo está la pantalla. El porqué de que la
comparación NO sea contra el acumulado del índice está documentado allá.
"""

from __future__ import annotations

import streamlit as st
from datetime import date

from core.db import connect
from places.inversiones.cartera.paneles._comun import (
    _TTL_PRECIOS,
    _fmt,
    _kpi_card,
)
from places.inversiones.cartera import benchmark as mod_bench
from core.market_data import indices as mod_indices


@st.cache_data(ttl=_TTL_PRECIOS, show_spinner=False)
def _serie_indice(clave: str) -> tuple[dict, str]:
    """Serie histórica del índice, cacheada. Una request por índice, no una
    por rerun: la serie de 10 años entra en una sola respuesta."""
    with connect() as conn:
        serie, origen = mod_indices.serie_con_fallback(conn, clave)
        conn.commit()
    return serie, origen


def _benchmark(flujos, k, uid: int) -> None:
    """¿Te fue mejor o peor que si hubieras comprado el índice?

    **Money-weighted, no acumulado.** Franco aportó en decenas de momentos
    distintos y el índice no: comparar su rendimiento contra el del índice
    mediría dos cosas distintas. Acá se simulan **sus** aportes, en **sus**
    fechas, puestos en el índice. Detalle en `benchmark.py`.
    """
    if not flujos:
        return

    st.markdown("#### Contra el mercado")
    st.caption(
        "Si hubieras puesto **la misma plata, en las mismas fechas**, en el "
        "índice en vez de en tus papeles: cuánto tendrías hoy. No es comparar "
        "tu rendimiento contra el del índice — eso sería tramposo, porque vos "
        "fuiste aportando de a poco y el índice no."
    )

    cual = st.radio(
        "Índice", list(mod_indices.INDICES.keys()), horizontal=True,
        key="cartera_benchmark_indice",
        format_func=lambda c: {"SPY": "S&P 500 (SPY, en US$)",
                               "MERVAL": "Merval (en $)"}.get(c, c),
        label_visibility="collapsed",
    )
    moneda = mod_indices.INDICES[cual][1]

    serie, origen = _serie_indice(cual)
    if not serie:
        st.info("No se pudo traer la serie del índice y no hay nada en caché. "
                "Se reintenta solo en el próximo refresco.", icon=":material/cloud_off:")
        return

    sim = mod_bench.simular(
        mod_bench.flujos_en(flujos, moneda), serie, date.today(),
        indice=cual, moneda=moneda)
    real = k.patrimonio_usd if moneda == "USD" else k.patrimonio_ars
    aportado = k.aportado_usd if moneda == "USD" else k.aportado_ars
    comp = mod_bench.comparar(sim, real, aportado)
    if comp is None:
        st.caption("Todavía no hay aportes que se puedan comparar con este índice.")
        return

    pref = "US$ " if moneda == "USD" else "$"
    dec = 0
    dif = comp["diferencia"]
    gano = comp["ganaste"]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.html(_kpi_card(
            "TU CARTERA HOY", f"{pref}{_fmt(comp['valor_real'], dec)}",
            f"sobre {pref}{_fmt(comp['aportado'], dec)} aportados"))
    with c2:
        st.html(_kpi_card(
            f"SI HUBIERAS COMPRADO {cual}",
            f"{pref}{_fmt(comp['valor_indice'], dec)}",
            (f"TIR {_fmt((comp['tir_indice'] or 0) * 100, 1)}% anual"
             if comp["tir_indice"] is not None else "mismos aportes, mismas fechas")))
    with c3:
        st.html(_kpi_card(
            "DIFERENCIA",
            f"{'+' if gano else '−'}{pref}{_fmt(abs(dif), dec)}",
            "le ganaste al índice" if gano else "el índice te ganó",
            "positivo" if gano else "negativo"))

    if not comp["completa"]:
        n = len(comp["sin_precio"])
        st.caption(
            f"⚠️ {n} aporte(s) quedaron afuera de la comparación: su fecha es "
            "anterior al arranque de la serie del índice. **No se estimó un "
            "precio para ellos** — la comparación usa solo los que sí se "
            "pudieron mapear, así que el número de arriba es parcial."
        )
    if origen == "cache":
        st.caption("Serie del índice servida desde la caché (la fuente no "
                   "respondió); puede no incluir los últimos días.")
