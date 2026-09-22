"""Panel "Cuándo cobrás": calendario de cobros, TIR esperada y duration (M15).

Para un bono amortizable el vencimiento dice poco: el AE38 no vence hasta 2038
pero empieza a devolver capital en julio de 2027. Lo que importa es el
cronograma, no la fecha final.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date

from core.db import connect
from places.inversiones.cartera.analisis import tipo_de_renta
from places.inversiones.cartera.paneles._comun import (
    _fmt,
    _kpi_card,
)
from core.market_data import cronogramas as mod_cron
from places.inversiones.cartera import renta_fija as mod_rf


def _precio_por_100_en_moneda_del_bono(p, moneda: str) -> float | None:
    """Precio de 100 nominales, **en la moneda de los flujos del bono**.

    ⚠️ Es el punto donde la TIR se arruina en silencio. `PosicionValuada.precio`
    está **en pesos**, y los flujos de un bono hard-dollar están **en dólares**:
    compararlos da un número plausible y equivocado.

    Para un bono en dólares se usa `valor_usd_actual / cantidad`, que es el
    valor de hoy pasado por el MEP — o sea, lo mismo que cotiza la variante D
    salvo diferencias de arbitraje del día.
    """
    cant = getattr(p, "cantidad", 0) or 0
    if cant <= 0:
        return None
    if moneda == "USD":
        valor = getattr(p, "valor_usd_actual", None)
        return (valor / cant) * 100.0 if valor else None
    valor = getattr(p, "valor_ars", None)
    return (valor / cant) * 100.0 if valor else None


def _renta_fija(valuadas, instrumentos: dict, uid: int) -> None:
    """Cuándo cobrás, cuánto rinde y cuánto riesgo de tasa tenés.

    Todo sale del cronograma cacheado (M15): **no consulta la red** salvo que
    aprietes el botón de refresco. Con 15 consultas por día, cada pedido tiene
    que ser una decisión tuya, no un efecto de abrir la pantalla.
    """
    vivas = [p for p in valuadas
             if not getattr(p, "cerrada", False)
             and (getattr(p, "cantidad", 0) or 0) > 0
             and tipo_de_renta(getattr(p, "categoria_activo", ""), p.ticker)
             == "Renta fija"]
    if not vivas:
        return

    hoy = date.today()
    with connect() as conn:
        cronogramas, tenencias, sin_datos, sin_consultar = {}, {}, [], []
        for p in vivas:
            cron = mod_cron.leer_cronograma(conn, p.ticker)
            if cron is None:
                # "La fuente no lo tiene" ≠ "todavía no se pudo preguntar"
                # (trampa 16): solo lo primero es esperable.
                (sin_datos if mod_cron.ya_consultado(conn, p.ticker)
                 else sin_consultar).append(p.ticker)
                continue
            cronogramas[p.ticker] = cron
            tenencias[p.ticker] = p.cantidad

    st.markdown("#### Cuándo cobrás")

    if not cronogramas:
        st.caption(
            "Todavía no bajaste los cronogramas de tus bonos. Sin ellos no hay "
            "calendario de cobros, ni TIR esperada, ni duration."
        )
        _boton_refrescar_cronogramas(vivas, uid)
        return

    pagos = mod_rf.calendario(cronogramas, tenencias, hoy)
    res = mod_rf.resumen_calendario(pagos, hoy, dias=365)

    st.caption(
        "Cada cupón y cada amortización que viene, **escalados a lo que tenés**. "
        "Para un bono amortizable esta es la pregunta que importa: el AE38 no "
        "vence hasta 2038 pero empieza a devolver capital antes."
    )

    cols = st.columns(max(2, len(res["por_moneda"]) + 1))
    for i, (moneda, m) in enumerate(sorted(res["por_moneda"].items())):
        simbolo = "US$ " if moneda == "USD" else "$"
        with cols[i]:
            st.html(_kpi_card(
                f"COBRÁS EN 12 MESES ({moneda})",
                _fmt(m["total"], 2 if moneda == "USD" else 0, simbolo),
                f"{m['n']} pago(s) · {_fmt(m['capital'], 2 if moneda == 'USD' else 0, simbolo)} "
                f"de capital + {_fmt(m['interes'], 2 if moneda == 'USD' else 0, simbolo)} de renta",
            ))
    prox = res["proximo"]
    with cols[len(res["por_moneda"])]:
        st.html(_kpi_card(
            "EL PRÓXIMO COBRO",
            prox.ticker if prox else "—",
            (f"{prox.fecha.strftime('%d/%m/%Y')} · en {prox.dias(hoy)} días · "
             f"{prox.concepto}") if prox else "no queda nada por cobrar",
        ))

    # ⚠️ **Sin columna de total en una sola moneda.** Sumar dólares y pesos
    # exigiría un TC futuro que no se conoce (trampa #1).
    df = pd.DataFrame([
        {"Fecha": p.fecha, "Ticker": p.ticker, "Concepto": p.concepto,
         "Capital": p.capital, "Renta": p.interes, "Total": p.total,
         "Moneda": p.moneda, "Días": p.dias(hoy)}
        for p in pagos[:40]
    ])
    st.dataframe(
        df, hide_index=True, use_container_width=True,
        column_config={
            "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Capital": st.column_config.NumberColumn(
                format="localized", step=0.01,
                help="Devolución de capital. NO es rendimiento: es tu plata "
                     "volviendo."),
            "Renta": st.column_config.NumberColumn(format="localized", step=0.01),
            "Total": st.column_config.NumberColumn(format="localized", step=0.01),
            "Días": st.column_config.NumberColumn(format="%d"),
        },
    )
    if len(pagos) > 40:
        st.caption(f"Se muestran los primeros 40 de {len(pagos)} pagos futuros.")

    # --- TIR esperada y duration ------------------------------------------
    st.markdown("**Qué rinde y cuánto riesgo de tasa tiene**")
    st.caption(
        "**TIR esperada:** lo que rendiría por año si lo mantenés hasta el "
        "final y cobrás todo. **Duration:** cuántos años tarda en volver la "
        "plata, en promedio ponderado — y por lo tanto cuánto cae el precio si "
        "las tasas suben."
    )

    filas = []
    for p in vivas:
        cron = cronogramas.get(p.ticker)
        if cron is None:
            continue
        moneda = "USD" if (cron.clase or "").upper().startswith("HARD") else "ARS"
        precio = _precio_por_100_en_moneda_del_bono(p, moneda)
        r = mod_rf.riesgo(cron, precio, nominales=100.0, moneda=moneda, hoy=hoy)
        filas.append({
            "Ticker": p.ticker,
            "Moneda": moneda,
            "Precio (100 nom.)": r.precio,
            "TIR anual": r.tir_pct,
            "Duration (años)": r.duration,
            "Si la tasa sube 1 pto": r.variacion_por_100pb(),
        })
    if filas:
        st.dataframe(
            pd.DataFrame(filas), hide_index=True, use_container_width=True,
            column_config={
                "Precio (100 nom.)": st.column_config.NumberColumn(
                    format="localized", step=0.01,
                    help="En la moneda del bono, que es la de sus flujos. "
                         "Mezclarlas daría una TIR plausible y falsa."),
                "TIR anual": st.column_config.NumberColumn(format="%.2f%%"),
                "Duration (años)": st.column_config.NumberColumn(format="%.2f"),
                "Si la tasa sube 1 pto": st.column_config.NumberColumn(
                    format="%.2f%%",
                    help="Cuánto cae el precio ante una suba de 100 puntos "
                         "básicos en el rendimiento. Es la duration modificada."),
            },
        )
        st.caption(
            ":material/info: La TIR supone que el precio incluye los intereses "
            "corridos, que es como se operan los soberanos argentinos. **Es un "
            "supuesto, no un dato verificado**: si el precio viniera limpio, "
            "la TIR quedaría sobreestimada."
        )

    if sin_datos:
        st.info(
            "Sin cronograma: **" + "**, **".join(sin_datos) + "**. "
            "La fuente no los tiene (los pagarés y cheques del MAV no están "
            "en su catálogo) — es esperable y no hay nada que arreglar.",
            icon=":material/info:")
    if sin_consultar:
        st.warning(
            "Todavía sin bajar: **" + "**, **".join(sin_consultar) + "**. "
            "Usá *Bajar los que falten* acá abajo.",
            icon=":material/schedule:")

    _boton_refrescar_cronogramas(vivas, uid)


def _boton_refrescar_cronogramas(vivas, uid: int) -> None:
    """El único lugar que consulta la red. **A pedido, nunca solo.**"""
    with st.expander("Bajar o actualizar los cronogramas"):
        if not mod_cron.hay_credenciales():
            st.caption(
                "No hay credenciales de Docta Capital configuradas. Se cargan "
                "en `DOCTA_CLIENT_ID` y `DOCTA_CLIENT_SECRET` — en tu `.env` "
                "para local, y con `fly secrets set` en producción."
            )
            return

        candidatos = [p.ticker for p in vivas if not p.ticker.startswith("#")]
        st.caption(
            f"Un cronograma **no cambia**: se baja una vez por bono y queda "
            f"guardado. El plan gratuito da **15 consultas por día** y esto "
            f"gasta **hasta {len(candidatos)}** (solo de los que falten). "
            f"Los pagarés no se consultan: no están en el catálogo."
        )
        # El resultado se guarda para mostrarlo **después** del rerun: un
        # `st.success` seguido de `st.rerun()` se borra antes de verse, y un
        # "la fuente no contestó" invisible es tan malo como no avisar.
        aviso = st.session_state.pop("cartera_cron_aviso", None)
        if aviso:
            tipo, texto = aviso
            (st.success if tipo == "ok" else st.warning)(
                texto, icon=(":material/check_circle:" if tipo == "ok"
                             else ":material/cloud_off:"))

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Bajar los que falten", key="cartera_cron_faltantes"):
                _refrescar(candidatos, forzar=False)
        with c2:
            if st.button("Forzar actualización de todos",
                         key="cartera_cron_forzar"):
                _refrescar(candidatos, forzar=True)


def _refrescar(candidatos, forzar: bool) -> None:
    with connect() as conn:
        n, faltan, no_consultados = mod_cron.refrescar_cronogramas(
            conn, candidatos, forzar=forzar)
        conn.commit()
    texto = f"{n} cronograma(s) {'actualizados' if forzar else 'nuevos'}."
    if faltan:
        texto += f" La fuente no tiene: {', '.join(faltan)}."
    if no_consultados:
        texto += (f" **Docta no contestó** (caída o cuota diaria agotada): "
                  f"{', '.join(no_consultados)} quedan para reintentar.")
    st.session_state["cartera_cron_aviso"] = (
        "error" if no_consultados else "ok", texto)
    st.rerun()
