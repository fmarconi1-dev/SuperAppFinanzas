"""Inicio — la pantalla principal de Secretario (Fase C, pasos 1–2).

Hoy muestra el saludo, las finanzas del mes y los últimos movimientos. La
agenda de la semana y las tareas pendientes llegan en el paso 3
(`docs/PLAN-FASE-C.md`).

Criterios (skill `ui-ux-web-moderno`): un número "rey" (ingresos − gastos),
cifras tabulares, el color nunca solo (siempre con signo), tokens `--cs-*` y
estados vacíos con qué hacer.
"""

from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from core.db import connect
from places.finanzas import home as finanzas_home
from places.finanzas.core.comandos import ZONA, pesos
from places.finanzas.helpers._html import render_html
from places.inicio.core import resumen as rs


def _con_signo(valor: float) -> str:
    """+$1.234 / -$1.234: el signo explícito acompaña al color."""
    return ("+" if valor > 0 else "") + pesos(valor)


def _render_kpis(r: rs.ResumenMes) -> None:
    a, p = r.actual, r.previo
    with st.container(key="kpi_hero", border=True):
        # La primera columna es el KPI "rey": el CSS de kpi_hero la agranda.
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"Ingresos − gastos · {r.mes}", _con_signo(r.balance))
        c2.metric("Gastos", pesos(a.gastos),
                  delta=rs.formatear_variacion(rs.variacion(a.gastos, p.gastos if p else None)),
                  delta_color="inverse")  # gastar más es malo
        c3.metric("Ingresos", pesos(a.ingresos),
                  delta=rs.formatear_variacion(rs.variacion(a.ingresos, p.ingresos if p else None)))
        c4.metric("Movimientos", f"{a.movimientos}")
    contexto = (f"Variaciones contra el mismo período del mes anterior ({r.periodo_previo()})."
                if p else f"Sin movimientos del {r.periodo_previo()} para comparar.")
    if a.sin_categorizar:
        contexto += (f" Hay {pesos(a.sin_categorizar)} sin categorizar que no entran en los gastos: "
                     "asignales grupo en **Finanzas → Configuración**.")
    st.caption(contexto)


def _render_movimientos(filas: list[dict]) -> None:
    st.subheader("Últimos movimientos")
    if not filas:
        st.caption("Todavía no cargaste ningún movimiento.")
        return
    renglones = []
    for f in filas:
        color = "var(--cs-positive)" if f["monto"] > 0 else "var(--cs-negative)"
        detalle = f" · {html.escape(f['comentario'])}" if f["comentario"] else ""
        renglones.append(
            '<div style="display:flex;gap:1rem;align-items:baseline;padding:0.55rem 0;'
            'border-bottom:1px solid var(--cs-border-soft);">'
            f'<span style="color:var(--cs-text-mid);font-family:var(--cs-font-mono);'
            f'font-variant-numeric:tabular-nums;min-width:3.2rem;">{f["fecha"]:%d/%m}</span>'
            f'<span style="flex:1;color:var(--cs-text);">{html.escape(f["motivo"])}'
            f'<span style="color:var(--cs-text-dim);">{detalle}</span></span>'
            f'<span style="color:{color};font-family:var(--cs-font-mono);'
            f'font-variant-numeric:tabular-nums;text-align:right;">{html.escape(_con_signo(f["monto"]))}</span>'
            "</div>"
        )
    render_html('<div role="list" aria-label="Últimos movimientos">' + "".join(renglones) + "</div>")
    st.caption("El detalle completo está en **Finanzas**.")


def render() -> None:
    user_id = st.session_state["current_user_id"]

    # Sin categorías todavía: la bienvenida de Finanzas va primero, igual que antes.
    if not finanzas_home._user_completo_onboarding(user_id):
        finanzas_home.render()
        return

    ahora = datetime.now(ZONA)
    nombre = (st.session_state.get("current_user_fullname")
              or st.session_state.get("current_username") or "").split(" ")[0]
    st.title(f"{rs.saludo(ahora.hour)}, {nombre}" if nombre else rs.saludo(ahora.hour))
    st.caption(rs.fecha_larga(ahora.date()).capitalize())

    with connect() as conn:
        r = rs.resumen_del_mes(conn, user_id=user_id, hoy=ahora.date())
        filas = rs.ultimos_movimientos(conn, user_id=user_id)

    if r is None or r.actual.movimientos == 0:
        st.info("Todavía no hay movimientos este mes. Cargalos en **Finanzas → Transacciones** "
                "o mandándole un gasto al Secretario por WhatsApp (por ejemplo, `2500, super`).")
    else:
        _render_kpis(r)
    _render_movimientos(filas)
