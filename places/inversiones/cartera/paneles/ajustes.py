"""Panel de ajustes de tenencia (M13): splits, ratios de CEDEAR, papeles
anteriores al registro y cupones recibidos.

**Todo costo cargado a mano genera su aporte sintético de capital**, con su
fecha. El método del patrimonio no mira costos, mira plata que entra y sale:
declarar un costo sin registrar el aporte inventa ganancia (pasó con TXAR).
"""

from __future__ import annotations

import streamlit as st

from core.db import (
    backup_db,
    connect,
)
from places.inversiones.cartera.paneles._comun import _fmt
from places.inversiones.cartera import ajustes as mod_ajustes


def _panel_ajustes(uid: int) -> None:
    """Alta y baja de ajustes de tenencia (ver `ajustes.py`).

    Es el panel donde se tapan los agujeros que el export del broker no puede
    llenar. La ayuda explica *qué* es cada tipo en criollo, porque el error de
    cargar un split como saldo inicial no da error: da un rendimiento mal.
    """
    with st.expander("Ajustar unidades que el broker no informa"):
        st.caption(
            "Hay cosas que el export **no trae**: los splits, los ajustes de "
            "ratio de CEDEAR, los papeles que ya tenías antes de que arrancara "
            "el historial y los cupones que te dieron por tenencia. Sin esto la "
            "app ve ventas de más unidades de las que registró y las cierra "
            "**sin costo**, lo que dispara el rendimiento."
        )

        with connect() as conn:
            existentes = mod_ajustes.listar(conn, uid)
            conocidos = mod_ajustes.tickers_conocidos(conn, uid)

        etiquetas = {v["etiqueta"]: k for k, v in mod_ajustes.TIPOS.items()}
        c1, c2 = st.columns([1, 2])
        with c1:
            tk = st.text_input("Ticker", key="cartera_aj_ticker",
                               placeholder="BYMA").strip().upper()
        with c2:
            tipo = etiquetas[st.selectbox(
                "Qué pasó", list(etiquetas), key="cartera_aj_tipo")]

        meta = mod_ajustes.TIPOS[tipo]
        st.caption(meta["ayuda"])

        # Un ajuste con el ticker mal escrito no falla: **no hace nada**, y eso
        # es peor, porque no deja rastro y el aviso original sigue ahí. Pasó el
        # 4/8/2026 con `CUPONES GGALX` en vez de `GGALX`.
        if tk and conocidos and tk not in conocidos:
            sugerencias = mod_ajustes.parecidos(tk, conocidos)
            extra = (f" ¿Quisiste decir **{'** o **'.join(sugerencias)}**?"
                     if sugerencias else "")
            st.warning(
                f"No hay ningún movimiento de **{tk}** en tu cartera, así que "
                f"este ajuste no va a corregir nada.{extra} El texto "
                f"descriptivo va en **Nota**, no en Ticker.",
                icon=":material/warning:")

        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", key="cartera_aj_fecha",
                                  format="DD/MM/YYYY")
        with c2:
            cant = st.number_input(
                "Unidades (negativo si restan)", value=0.0, step=1.0,
                format="%.4f", key="cartera_aj_cant")

        costo = 0.0
        estimado = False
        if meta["espera_costo"]:
            st.markdown("**Cuánto te costaron**")
            st.caption(
                "Este número es el que evita que vender esas unidades figure "
                "como ganancia pura: la app lo registra como capital que "
                "aportaste a la cartera."
            )
            modo = st.radio(
                "De dónde sale", ["Sé el costo", "Lo despejo del rendimiento"],
                horizontal=True, key="cartera_aj_modo",
                label_visibility="collapsed")

            if modo == "Sé el costo":
                costo = st.number_input(
                    "Costo total en pesos", value=0.0, step=1000.0,
                    format="%.2f", key="cartera_aj_costo")
                estimado = st.checkbox(
                    "Es aproximado", key="cartera_aj_estim",
                    help="Marcalo si el número sale de la memoria y no del "
                         "resumen del broker. La app lo muestra señalado para "
                         "que dentro de un año sepas cuál era cuál.")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    ingreso = st.number_input(
                        "Cuánto cobraste al venderlas", value=0.0, step=1000.0,
                        format="%.2f", key="cartera_aj_ingreso")
                with c2:
                    rend = st.number_input(
                        "Rendimiento en pesos (%)", value=0.0, step=1.0,
                        format="%.2f", key="cartera_aj_rend")
                estimado = True
                if ingreso and rend != -100.0:
                    costo = mod_ajustes.costo_desde_rendimiento(ingreso, rend)
                    st.info(
                        f"Costo despejado: **{_fmt(costo, 2, '$')}**"
                        + (f" ({_fmt(costo / cant, 2, '$')} por unidad)"
                           if cant else "")
                        + " — se guarda marcado como aproximado.",
                        icon=":material/calculate:")

        nota = st.text_input(
            "Nota (opcional)", key="cartera_aj_nota",
            placeholder="De dónde salió el dato")

        if st.button("Agregar ajuste", key="cartera_aj_btn", type="primary"):
            if not tk:
                st.warning("Falta el ticker.", icon=":material/warning:")
            elif abs(cant) < 1e-12 and abs(costo) < 1e-9:
                st.warning("Un ajuste que no mueve unidades ni costo no hace "
                           "nada.", icon=":material/warning:")
            else:
                # El backup va ANTES de abrir la conexión de escritura, no
                # adentro: copiar la base entera teniéndola ya tomada abre una
                # ventana en la que cualquier otro acceso choca. Así fue el
                # `database is locked` del 4/8/2026.
                backup_db()
                with connect() as conn:
                    nuevo = mod_ajustes.agregar(conn, uid, mod_ajustes.Ajuste(
                        fecha=fecha, ticker=tk, tipo=tipo, cantidad=cant,
                        costo_ars=costo, estimado=estimado, nota=nota))
                    conn.commit()
                if nuevo is None:
                    st.info("Ese ajuste ya estaba cargado.",
                            icon=":material/info:")
                else:
                    st.success(f"Ajuste cargado en {tk}.",
                               icon=":material/check_circle:")
                    st.rerun()

        st.divider()
        if not existentes:
            st.caption("Todavía no cargaste ningún ajuste.")
            return

        st.markdown("**Ajustes cargados**")
        for a in existentes:
            c1, c2 = st.columns([6, 1])
            with c1:
                marca = " · *aproximado*" if a.estimado else ""
                costo_txt = (f" · {_fmt(a.costo_ars, 2, '$')}"
                             if a.mueve_capital else "")
                st.markdown(
                    f"`{a.ticker}` {a.fecha.strftime('%d/%m/%Y')} · "
                    f"{a.etiqueta_tipo} · {a.cantidad:+g} u{costo_txt}{marca}"
                    + (f"  \n<small>{a.nota}</small>" if a.nota else ""),
                    unsafe_allow_html=True)
            with c2:
                if st.button("Quitar", key=f"cartera_aj_del_{a.id}"):
                    backup_db()          # fuera de la conexión de escritura
                    with connect() as conn:
                        mod_ajustes.eliminar(conn, uid, a.id)
                        conn.commit()
                    st.rerun()
