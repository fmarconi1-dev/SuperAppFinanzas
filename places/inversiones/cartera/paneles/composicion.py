"""Panel "Cómo está repartida": composición por tipo de renta, sector, industria,
emisor y país.

**Los cuadros van uno debajo del otro, a lo ancho, a propósito** (rehecho el
5/8/2026). Son cortes sobre universos distintos —toda la cartera, solo la renta
variable, solo la renta fija— y ponerlos lado a lado sugería que se comparaban
entre sí.

Y a un bono no le *falta* el sector: no tiene. Por eso la renta fija se corta
por **emisor** (soberano / subsoberano / corporativo), que es lo que define su
riesgo.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.db import connect
from core.market_data.sectores import set_override_sector
from places.inversiones.cartera.analisis import (
    SIN_DATO,
    por_emisor,
    por_pais,
    por_sector,
    por_tipo_de_renta,
)
from places.inversiones.cartera.paneles._comun import _fmt


def _grafico_grupos(grupos, titulo: str = "") -> None:
    """Barras horizontales del peso de cada grupo.

    **Horizontales y no torta**, a propósito: una torta con más de cinco tajos
    se vuelve ilegible, y acá los sectores pueden ser ocho o diez. La barra
    horizontal además deja leer nombres largos ("Financial Services") sin
    rotarlos ni cortarlos, que era justo el problema de la versión anterior.

    `Sin dato` va en gris: es una etiqueta de ignorancia, no una categoría que
    compita con las demás por atención.
    """
    import plotly.graph_objects as go
    from core.theme._theme import COLOR_NEUTRO, COLORES_MA

    visibles = [g for g in grupos if g.valor_ars]
    if not visibles:
        return

    # De menor a mayor: Plotly dibuja el eje Y de abajo hacia arriba, así que
    # el grupo más grande queda arriba.
    visibles = sorted(visibles, key=lambda g: g.valor_ars)
    colores = [
        COLOR_NEUTRO if g.nombre == SIN_DATO
        else COLORES_MA[i % len(COLORES_MA)]
        for i, g in enumerate(visibles)
    ]
    fig = go.Figure(go.Bar(
        x=[g.pct for g in visibles],
        y=[g.nombre for g in visibles],
        orientation="h",
        marker_color=colores,
        text=[f"{_fmt(g.pct, 1)}%" for g in visibles],
        textposition="outside",
        cliponaxis=False,
        customdata=[[g.valor_ars, g.n] for g in visibles],
        hovertemplate=("<b>%{y}</b><br>%{x:.1f}% de la cartera"
                       "<br>$ %{customdata[0]:,.0f}"
                       "<br>%{customdata[1]} posición(es)<extra></extra>"),
    ))
    # El eje X se estira un 18% más allá de la barra más larga. Sin ese aire,
    # el porcentaje que va **por fuera** de la barra se sale del área del
    # gráfico y termina pisando lo que tiene al lado.
    tope = max((g.pct for g in visibles), default=100.0) or 100.0

    # ⚠️ El título **no se pasa** cuando está vacío, en vez de pasarlo en
    # `None`. Con `title=None` Plotly serializa un `null` que el lado JS
    # dibuja como la palabra literal **"undefined"** encima del gráfico,
    # pisando las barras y el texto de arriba. Pasó en producción el 5/8/2026.
    fig.update_layout(
        height=max(160, 46 * len(visibles) + 70),
        margin=dict(l=0, r=16, t=36 if titulo else 12, b=12),
        # `automargin` deja que las etiquetas largas ("Financial Services",
        # "Communication Services") corran el eje en vez de recortarse.
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False,
                   range=[0, tope * 1.18]),
        yaxis=dict(title=None, automargin=True, ticksuffix="  "),
        showlegend=False,
        bargap=0.35,
        uniformtext=dict(mode="hide", minsize=10),
    )
    if titulo:
        fig.update_layout(title=titulo)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _tabla_grupos(grupos, mep, ayuda_pct: str) -> None:
    """Tabla de composición: peso, valor y resultado no realizado por grupo."""
    tope = max((g.pct for g in grupos), default=100.0) or 100.0
    st.dataframe(
        pd.DataFrame([
            {"Grupo": g.nombre, "Peso": g.pct, "Posiciones": g.n,
             "Valor": g.valor_ars,
             "US$": g.valor_usd(mep),
             "No realizado": g.resultado_ars,
             "Rend. %": g.rendimiento_pct}
            for g in grupos
        ]),
        hide_index=True, use_container_width=True,
        column_config={
            "Peso": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0.0, max_value=float(tope),
                help=ayuda_pct),
            "Posiciones": st.column_config.NumberColumn(format="%d"),
            "Valor": st.column_config.NumberColumn(format="localized", step=1),
            "US$": st.column_config.NumberColumn(format="localized", step=1),
            "No realizado": st.column_config.NumberColumn(
                format="localized", step=1,
                help="Lo que vale hoy menos lo que costó. NO es el resultado "
                     "total: ese no se puede sumar por grupo sin que la "
                     "devaluación lo infle"),
            "Rend. %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )


def _composicion(valuadas, efectivo_ars, sectores, industrias, mep,
                 uid) -> None:
    """Cómo está repartida la plata: por tipo de renta, sector e industria.

    El **tipo de renta** sale de la categoría del Excel y cubre todo. El
    **sector** y la **industria** se resuelven solos (Yahoo, con
    caché y override): a un bono, al pagaré o a la cripto no se les asigna
    ninguno, porque no les falta el dato — no lo tienen.
    """
    st.markdown("#### Cómo está repartida")
    por_renta = por_tipo_de_renta(valuadas, efectivo_ars)
    if not por_renta:
        st.caption("Todavía no hay posiciones para repartir.")
        return

    ayuda = "Sobre el patrimonio, con el efectivo adentro"

    # ⚠️ Cada corte va a **ancho completo y uno debajo del otro**, no en dos
    # columnas. Antes iban lado a lado y en pantallas angostas las tablas se
    # cortaban y no se entendían (lo reportó Franco el 5/8/2026). Además son
    # cortes sobre universos distintos —toda la cartera, la renta variable, la
    # renta fija—: ponerlos al lado sugiere que se comparan entre sí, y no.

    st.markdown("**Por tipo de renta**")
    st.caption("Desde la categoría de tu Excel: cubre el 100% de la cartera.")
    _grafico_grupos(por_renta)
    _tabla_grupos(por_renta, mep, ayuda)

    st.divider()

    st.markdown("**Por sector (renta variable)**")
    grupos_sec = por_sector(valuadas, sectores)
    sin_dato = next((g for g in grupos_sec if g.nombre == SIN_DATO), None)
    cubierto = 100.0 - (sin_dato.pct if sin_dato else 0.0)
    st.caption(
        f"Solo acciones y CEDEARs: a un bono, al pagaré o a la cripto no les "
        f"falta el sector, **no lo tienen**. Se resuelve solo y cubre el "
        f"**{_fmt(cubierto, 0)}%**. Los ETF van con su subyacente (*ETF · Oro*): "
        "son una canasta, asignarles un sector sería inventarlo."
    )
    _grafico_grupos(grupos_sec)
    _tabla_grupos(grupos_sec, mep, "Sobre la renta variable")

    grupos_emisor = por_emisor(valuadas)
    if grupos_emisor:
        st.divider()
        st.markdown("**Por emisor (renta fija)**")
        st.caption(
            "A un bono no se le puede preguntar el sector; lo que define su "
            "riesgo es **quién te debe la plata**. *Soberano* es el Tesoro "
            "Nacional, *subsoberano* una provincia, *corporativo* una empresa "
            "— las ON y los pagarés."
        )
        _grafico_grupos(grupos_emisor)
        _tabla_grupos(grupos_emisor, mep, "Sobre la renta fija")

        grupos_pais = por_pais(valuadas)
        if len(grupos_pais) > 1:
            st.markdown("**Por país (renta fija)**")
            _grafico_grupos(grupos_pais)
            _tabla_grupos(grupos_pais, mep, "Sobre la renta fija")
        elif grupos_pais:
            st.caption(
                f"Toda tu renta fija es de **{grupos_pais[0].nombre}**. "
                "El corte por país aparece solo si algún día tenés deuda de "
                "más de un lugar."
            )

    st.divider()

    with st.expander("Ver por industria (el detalle dentro de cada sector)"):
        st.caption(
            "Dos papeles del mismo sector pueden ser negocios muy distintos. "
            "Acá se ve, por ejemplo, cuánto de tu tecnología es realmente "
            "semiconductores."
        )
        _tabla_grupos(por_sector(valuadas, industrias), mep,
                      "Sobre la renta variable")

    with st.expander("Corregir el sector de un papel"):
        st.caption(
            "El sector lo resuelve la app sola. Si no coincide con tu criterio, "
            "fijalo acá: **tu valor gana siempre**, incluso cuando el proveedor "
            "se actualice. Ejemplo real: Yahoo clasifica a **TGNO4** como "
            "*Energy · Oil & Gas Midstream* (el estándar GICS mete el "
            "transporte de gas en Energía), aunque en Argentina se lo piense "
            "como una utility regulada."
        )
        s1, s2, s3 = st.columns([2, 2, 1])
        with s1:
            tk_sec = st.selectbox(
                "Papel", sorted(sectores) or [""], key="cartera_sec_ticker")
        with s2:
            nuevo_sector = st.text_input(
                "Sector", value=sectores.get(tk_sec, ""),
                key="cartera_sec_valor")
        with s3:
            st.write("")
            if st.button("Fijar", key="cartera_btn_sec",
                         disabled=not (tk_sec and nuevo_sector)):
                with connect() as conn:
                    set_override_sector(conn, tk_sec, nuevo_sector.strip())
                    conn.commit()
                st.success(f"{tk_sec} queda como **{nuevo_sector.strip()}**.",
                           icon=":material/check_circle:")
                st.rerun()
