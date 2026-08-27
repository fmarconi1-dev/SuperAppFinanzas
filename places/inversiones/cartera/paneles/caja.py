"""Panel "La plata quieta": cauciones, dividendos y cuenta remunerada.

Ojo con la TNA: se pondera **por capital y por tiempo**, no se promedia.
Promediar las TNA de 101 cauciones le daría el mismo peso a una de $20.000 por
un día que a una de $2,7M por cinco.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from places.inversiones.cartera.paneles._comun import (
    _fmt,
    _kpi_card,
)


def _rendimiento_caja(cs, resumen, divs, rem) -> None:
    """Lo que rinde la plata que no está en una posición (Fase 3b, punto 3).

    ⚠️ Es **atribución, no plata nueva**: el interés de las cauciones y la
    cuenta remunerada ya engordaron el efectivo, y los dividendos ya están en
    los flujos de cada instrumento. Esto explica de dónde viene una parte del
    resultado, no lo agranda.
    """
    st.markdown("#### La plata quieta")

    rem_ars, rem_usd, rem_n = rem
    div_bruto = sum(d.bruto for d in divs.values())
    div_ret = sum(d.retencion for d in divs.values())
    div_n = sum(d.n for d in divs.values())

    if not (resumen.n or div_n or rem_n):
        st.caption(
            "Todavía no hay cauciones, dividendos ni cuenta remunerada en tus "
            "movimientos. Cuando los haya, acá vas a ver cuánto rindió la "
            "plata que no está invertida en una posición."
        )
        return

    st.caption(
        "Cauciones, cuenta remunerada y dividendos. **Ya está todo dentro de "
        "tu patrimonio** — el interés engordó el efectivo y los dividendos ya "
        "cuentan en cada instrumento. Esto no suma nada nuevo: muestra de "
        "dónde viene."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        tna = resumen.tna_ponderada
        st.html(_kpi_card(
            "Interés de cauciones", _fmt(resumen.interes, 0, "$"),
            (f"▲ {_fmt(tna * 100, 1)}% anual · {resumen.n} cauciones"
             if tna is not None else f"{resumen.n} cauciones"),
            "positivo" if resumen.interes >= 0 else "negativo"))
    with c2:
        st.html(_kpi_card(
            "Dividendos netos", _fmt(div_bruto + div_ret, 0, "$"),
            f"▲ {_fmt(div_bruto, 0, '$')} brutos − {_fmt(abs(div_ret), 0, '$')} "
            f"de retención · {div_n} cobros", "positivo"))
    with c3:
        st.html(_kpi_card(
            "Cuenta remunerada", _fmt(rem_ars, 0, "$"),
            f"▲ {rem_n} acreditaciones", "positivo" if rem_ars >= 0 else ""))

    st.caption(
        f"**Total de la caja: {_fmt(resumen.interes + rem_ars + div_bruto + div_ret, 0, '$')}**. "
        "La tasa de las cauciones va **ponderada por capital y plazo**: "
        "promediar la tasa de cada una le daría el mismo peso a una de "
        "$20.000 por un día que a una de $2,7 millones por cinco."
    )

    col_izq, col_der = st.columns(2)
    with col_izq:
        st.markdown("**Cauciones por año**")
        if not resumen.por_anio:
            st.caption("Sin cauciones registradas.")
        else:
            st.dataframe(
                pd.DataFrame([
                    {"Año": anio, "Cauciones": n, "Interés": interes,
                     "TNA": (tna * 100) if tna is not None else None}
                    for anio, (n, interes, tna)
                    in sorted(resumen.por_anio.items())
                ]),
                hide_index=True, use_container_width=True,
                column_config={
                    "Año": st.column_config.NumberColumn(format="%d"),
                    "Interés": st.column_config.NumberColumn(format="localized", step=1),
                    "TNA": st.column_config.NumberColumn(
                        format="%.2f%%",
                        help="Ponderada por capital y plazo dentro del año"),
                },
            )
    with col_der:
        st.markdown("**Dividendos por instrumento**")
        if not div_n:
            st.caption("Todavía no cobraste dividendos.")
        else:
            st.dataframe(
                pd.DataFrame([
                    {"Ticker": d.ticker, "Cobros": d.n, "Bruto": d.bruto,
                     "Retención": d.retencion, "Neto": d.neto,
                     "Ret. %": d.retencion_pct}
                    for d in sorted(divs.values(), key=lambda x: -x.bruto)
                    if d.bruto
                ]),
                hide_index=True, use_container_width=True,
                column_config={
                    "Bruto": st.column_config.NumberColumn(format="localized", step=1),
                    "Retención": st.column_config.NumberColumn(format="localized", step=1),
                    "Neto": st.column_config.NumberColumn(format="localized", step=1),
                    "Ret. %": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )

    if not resumen.n:
        return
    with st.expander(f"Ver las {resumen.n} cauciones una por una"):
        if resumen.abiertas:
            st.caption(
                f"{resumen.abiertas} figura(n) como **abierta(s)**: se colocó "
                "pero el vencimiento todavía no aparece en los movimientos. "
                "No se les calcula tasa."
            )
        st.dataframe(
            pd.DataFrame([
                {"Fecha": c.fecha, "Capital": c.capital, "Cobrado": c.cobrado,
                 "Interés": c.interes, "Días": c.dias,
                 "TNA": (c.tna * 100) if c.tna is not None else None,
                 "Estado": "abierta" if c.abierta else ""}
                for c in sorted(cs, key=lambda x: x.fecha, reverse=True)
            ]),
            hide_index=True, use_container_width=True,
            column_config={
                "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Capital": st.column_config.NumberColumn(format="localized", step=1),
                "Cobrado": st.column_config.NumberColumn(format="localized", step=1),
                "Interés": st.column_config.NumberColumn(format="localized", step=0.01),
                "Días": st.column_config.NumberColumn(format="%d"),
                "TNA": st.column_config.NumberColumn(
                    format="%.1f%%",
                    help="En montos chicos y plazos de un día, unos pesos de "
                         "redondeo mueven esta tasa decenas de puntos: la "
                         "representativa es la ponderada de arriba"),
            },
        )
