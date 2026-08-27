"""Panel "Qué se te vence": renta fija viva ordenada por fecha, con su valor.

Las fechas salen de `cartera/vencimientos.py` (cronograma de Docta → descripción
del instrumento → override manual). Acá también se fija a mano lo que ninguna
fuente resuelve, y se avisa cuando dos fuentes exactas se contradicen.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date

from core.db import connect
from places.inversiones.cartera.paneles._comun import (
    _fmt,
    _kpi_card,
)
from places.inversiones.cartera import vencimientos as mod_venc


def _vencimientos(valuadas: dict, instrumentos: dict, uid: int) -> None:
    """Qué se te vence, cuándo y cuánta plata es.

    Las fechas salen del **cronograma de pagos** (Docta, M15) cuando está
    cacheado, y de la descripción del instrumento cuando no (`vencimientos.py`).
    Ninguna de las dos hay que cargarla. Lo que no trae fecha por ningún lado
    se fija a mano acá abajo.
    """
    with connect() as conn:
        vencs = mod_venc.resolver(instrumentos, conn)
    if not vencs:
        return

    hoy = date.today()
    res = mod_venc.resumen(vencs, valuadas, hoy)
    filas = mod_venc.proximos(vencs, valuadas, hoy)

    st.markdown("#### Qué se te vence")
    st.caption(
        "Bonos, letras, ON y pagarés que todavía tenés, del que vence antes al "
        "que vence después. **Las fechas se leen solas**: del cronograma de "
        "pagos del bono cuando lo tenemos bajado, y si no de la descripción "
        "del instrumento. Lo ya vencido no aparece: no te vence nada."
    )

    prox = res["proximo"]
    c1, c2 = st.columns(2)
    with c1:
        st.html(_kpi_card(
            "VENCE EN LOS PRÓXIMOS 90 DÍAS",
            _fmt(res["ars_proximos"], 0, "$") if res["n_proximos"] else "—",
            (f"{res['n_proximos']} instrumento(s) · "
             f"{_fmt(res['usd_proximos'], 0, 'US$ ')}")
            if res["n_proximos"] else "nada en el corto plazo",
        ))
    with c2:
        st.html(_kpi_card(
            "EL PRÓXIMO",
            f"{prox['Ticker']}" if prox else "—",
            (f"{prox['Vence']} · en {prox['Días']} días" if prox
             else "el más cercano está a más de 90 días"),
        ))

    if not filas:
        st.caption("No te queda nada de renta fija por vencer.")
        return

    df = pd.DataFrame([
        {k: f[k] for k in ("Ticker", "Vence", "Días", "Valor", "US$", "Fuente")}
        for f in filas
    ])
    st.dataframe(
        df, hide_index=True, use_container_width=True,
        column_config={
            "Vence": st.column_config.TextColumn(
                help="Solo el año cuando la descripción no dice el día."),
            "Días": st.column_config.NumberColumn(
                format="%d", help="Vacío cuando la fecha no es exacta: contar "
                                  "días contra un año redondeado sería "
                                  "inventar precisión."),
            "Valor": st.column_config.NumberColumn(format="localized", step=1),
            "US$": st.column_config.NumberColumn(format="localized", step=0.01),
            "Fuente": st.column_config.TextColumn(
                help="Vacío = salió de la descripción del instrumento. "
                     "'cronograma' = del calendario de pagos del bono, que es "
                     "el dato del emisor. 'a mano' = la fijaste vos."),
        },
    )

    # Dos fuentes exactas que no coinciden: una de las dos está mal. Se avisa
    # en vez de mostrar solo la ganadora, que sería indistinguible de un dato
    # sin conflicto.
    for d in res.get("discrepancias", []):
        st.warning(
            f"**{d['Ticker']}**: el cronograma del bono dice que vence el "
            f"**{d['cronograma'].strftime('%d/%m/%Y')}**, pero la descripción "
            f"del Excel dice **{d['descripcion'].strftime('%d/%m/%Y')}**. "
            "Se muestra la del cronograma (es el dato del emisor). Si la del "
            "Excel es la correcta, fijala a mano acá abajo.",
            icon=":material/warning:",
        )

    if res["sin_fecha"]:
        st.info(
            "Sin fecha: **" + "**, **".join(res["sin_fecha"]) + "**. "
            "Sus descripciones tienen el año en el *nombre* del bono "
            "(«Bono USD 2038»), que no es lo mismo que decir cuándo vence. "
            "Fijalas abajo si las necesitás.",
            icon=":material/info:")

    with st.expander("Fijar un vencimiento a mano"):
        st.caption(
            "Para lo que el Excel no informa. La fecha que pongas acá **gana** "
            "sobre la descripción, y se puede quitar para volver a la automática."
        )
        candidatos = sorted(vencs)
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            tk = st.selectbox("Instrumento", candidatos, key="cartera_venc_tk")
        with c2:
            f = st.date_input("Vence el", key="cartera_venc_fecha",
                              format="DD/MM/YYYY")
        with c3:
            st.write("")
            if st.button("Fijar", key="cartera_venc_set"):
                with connect() as conn:
                    mod_venc.set_override(conn, tk, f)
                    conn.commit()
                st.success(f"{tk} vence el {f.strftime('%d/%m/%Y')}.",
                           icon=":material/check_circle:")
                st.rerun()

        manuales = [t for t, x in vencs.items() if x.fuente == "manual"]
        if manuales:
            st.caption("Fijados a mano: " + ", ".join(manuales))
            quitar = st.selectbox("Volver a la fecha automática", manuales,
                                  key="cartera_venc_quitar")
            if st.button("Quitar", key="cartera_venc_del"):
                with connect() as conn:
                    mod_venc.quitar_override(conn, quitar)
                    conn.commit()
                st.rerun()
