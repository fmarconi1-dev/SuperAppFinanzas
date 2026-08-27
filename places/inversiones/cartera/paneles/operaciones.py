"""Panel "Operaciones cerradas": el resultado realizado, operación por operación.

Sale de `ledger.py`, que recorre los movimientos en orden cronológico con PPC
móvil: el costo de una venta es el vigente **ese día**, no el promedio de toda
la historia (ADR-0005).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from places.inversiones.cartera.paneles._comun import (
    _fmt,
    _kpi_card,
)


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
                format="localized", step=0.01,
                help="Costo promedio ponderado vigente al momento de vender"),
            "Precio venta": st.column_config.NumberColumn(format="localized", step=0.01),
            "Resultado": st.column_config.NumberColumn(format="localized", step=1),
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
