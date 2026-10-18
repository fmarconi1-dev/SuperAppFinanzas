"""Inicio — la pantalla principal de Secretario (Fase C, ADR-0008).

Saludo, finanzas del mes, la semana, las tareas pendientes (con tilde para
completarlas en Google Tasks), los últimos movimientos y una línea de estado
del Secretario. Plan: `docs/PLAN-FASE-C.md`.

Criterios (skill `ui-ux-web-moderno`): un número "rey" (el saldo de la cuenta, solo y en grande),
cifras tabulares, el color nunca solo (siempre con signo o texto), tokens
`--cs-*`, y cada bloque con sus estados de carga, vacío y error.

La agenda viene del Apps Script (`core/api/google.py`), que tarda 1–3 s: se
guarda **5 minutos** en caché y hay un botón para actualizarla. Una tarea se
tacha recién cuando Google confirma (`ok: true`).
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Optional

import streamlit as st

from core.api.google import AgendaNoDisponible, AgendaRechazo, ClienteAgenda
from core.db import connect
from places.finanzas import home as finanzas_home
from places.finanzas.core.comandos import ZONA, pesos
from places.finanzas.helpers._html import render_html
from places.inicio.core import resumen as rs
from places.inicio.core import semana as sm

#: Cuánto se guarda la agenda antes de volver a pedírsela a Google.
TTL_AGENDA = 300


def _con_signo(valor: float) -> str:
    """+$1.234 / -$1.234: el signo explícito acompaña al color."""
    return ("+" if valor > 0 else "") + pesos(valor)


# ---------------------------------------------------------------------------
# Finanzas
# ---------------------------------------------------------------------------

def _render_saldo(saldo: float) -> None:
    """El número "rey": el saldo de la cuenta, solo y en grande."""
    with st.container(key="inicio_saldo"):
        st.metric("Saldo de la cuenta", pesos(saldo))
        st.caption("Lo que tenés hoy: saldo inicial + todo lo que entró − todo lo que salió. "
                   "Es el mismo saldo del Dashboard de Finanzas.")


def _render_mes(r: rs.ResumenMes) -> None:
    """Debajo del saldo: gastos, ingresos y movimientos del mes."""
    a, p = r.actual, r.previo
    with st.container(key="inicio_mes"):
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Gastos de {r.mes}", pesos(a.gastos),
                  delta=rs.formatear_variacion(rs.variacion(a.gastos, p.gastos if p else None)),
                  delta_color="inverse")  # gastar más es malo
        c2.metric(f"Ingresos de {r.mes}", pesos(a.ingresos),
                  delta=rs.formatear_variacion(rs.variacion(a.ingresos, p.ingresos if p else None)))
        c3.metric("Movimientos", f"{a.movimientos}")
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
            '<div class="cs-evento">'
            f'<span class="cs-hora" style="min-width:3.2rem;">{f["fecha"]:%d/%m}</span>'
            f'<span class="cs-titulo" style="flex:1;">{html.escape(f["motivo"])}'
            f'<span class="cs-extra">{detalle}</span></span>'
            f'<span style="color:{color};font-family:var(--cs-font-mono);'
            f'font-variant-numeric:tabular-nums;text-align:right;">{html.escape(_con_signo(f["monto"]))}</span>'
            "</div>"
        )
    render_html('<div role="list" aria-label="Últimos movimientos">' + "".join(renglones) + "</div>")
    st.caption("El detalle completo está en **Finanzas**.")


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------

@st.cache_data(ttl=TTL_AGENDA, show_spinner=False)
def _semana(url: str, secreto: str) -> dict:
    """`resumen_semana` del Apps Script, con caché. Los errores no se cachean."""
    return ClienteAgenda(url=url, secreto=secreto).resumen_semana()


def _completar(cliente: ClienteAgenda, tarea: sm.Tarea, clave: str) -> None:
    """Callback del tilde: completa en Google y, solo si confirma, la saca de la lista."""
    try:
        cliente.completar_tarea(lista_id=tarea.lista_id, tarea_id=tarea.id)
    except (AgendaRechazo, AgendaNoDisponible) as e:
        st.session_state[clave] = False   # vuelve a destildarse: no se completó
        st.session_state["_inicio_error_tarea"] = f"No pude completar «{tarea.titulo}»: {e}"
        return
    _semana.clear()
    st.session_state.pop(clave, None)
    st.session_state["_inicio_tarea_hecha"] = tarea.titulo


def _render_semana(dias: list[sm.Dia]) -> None:
    if not dias:
        st.caption("Sin eventos de hoy a 7 días.")
        return
    partes = []
    for d in dias:
        etiqueta = f' <span class="cs-hoy">· {d.etiqueta}</span>' if d.etiqueta else ""
        partes.append(f'<div class="cs-dia">{html.escape(d.titulo)}{etiqueta}</div>')
        for ev in d.eventos:
            extra = []
            if ev.hasta:
                extra.append(f"hasta {ev.hasta:%d/%m}")
            if ev.ubicacion:
                extra.append(html.escape(ev.ubicacion))
            extra_txt = f'<span class="cs-extra"> · {" · ".join(extra)}</span>' if extra else ""
            partes.append(
                '<div class="cs-evento">'
                f'<span class="cs-hora">{html.escape(ev.hora)}</span>'
                f'<span class="cs-titulo">{html.escape(ev.titulo)}{extra_txt}</span>'
                "</div>"
            )
    render_html('<div role="list" aria-label="Eventos de la semana">' + "".join(partes) + "</div>")


def _render_tareas(tareas: list[sm.Tarea], cliente: ClienteAgenda) -> None:
    if hecha := st.session_state.pop("_inicio_tarea_hecha", None):
        st.toast(f"Tarea completada: {hecha}", icon="✅")
    if error := st.session_state.pop("_inicio_error_tarea", None):
        st.error(error)
    if not tareas:
        st.caption("Nada pendiente.")
        return
    with st.container(key="inicio_tareas"):
        for t in tareas:
            if t.vencida:
                detalle = f"  :orange[⚠ {t.detalle}]"
            elif t.detalle:
                detalle = f"  :gray[{t.detalle}]"
            else:
                detalle = ""
            clave = f"tarea_{t.lista_id}_{t.id}"
            st.checkbox(f"{t.titulo}{detalle}", key=clave, value=False,
                        on_change=_completar, args=(cliente, t, clave),
                        help="Tildala para marcarla como hecha en Google Tasks.")


def _render_agenda(hoy) -> Optional[bool]:
    """Semana + tareas. Devuelve si la agenda está conectada (para la línea de estado)."""
    cliente = ClienteAgenda.desde_entorno()
    col_semana, col_tareas = st.columns([3, 2], gap="large")
    with col_semana:
        st.subheader("Esta semana")
    with col_tareas:
        st.subheader("Tareas pendientes")

    if cliente is None:
        st.info("La agenda todavía no está conectada: faltan `GOOGLE_WORKSPACE_WEBHOOK_URL` y "
                "`GOOGLE_WORKSPACE_SECRET` en Fly. El resto del Inicio anda igual.")
        return False

    espera = st.empty()
    espera.caption("Trayendo tu agenda de Google…")
    try:
        datos = _semana(cliente.url, cliente.secreto)
    except (AgendaNoDisponible, AgendaRechazo) as e:
        espera.empty()
        st.warning(f"No pude traer tu agenda: {e}")
        if st.button("Reintentar", key="inicio_reintentar_agenda", icon=":material/refresh:"):
            _semana.clear()
            st.rerun()
        return True
    espera.empty()

    with col_semana:
        with st.container(key="inicio_semana"):
            _render_semana(sm.dias_de_la_semana(datos.get("eventos") or [], hoy))
    with col_tareas:
        _render_tareas(sm.tareas_ordenadas(datos.get("tareas") or [], hoy), cliente)
    if st.button("Actualizar agenda", key="inicio_actualizar_agenda", icon=":material/refresh:",
                 help=f"La agenda se guarda {TTL_AGENDA // 60} minutos; esto la vuelve a pedir ya."):
        _semana.clear()
        st.rerun()
    return True


def _render_estado(conn_ok_agenda: Optional[bool]) -> None:
    with connect() as conn:
        en_cola = rs.mensajes_en_cola(conn)
    partes = []
    if en_cola:
        partes.append(f"{en_cola} mensaje{'s' if en_cola > 1 else ''} esperando a que le escribas al Secretario")
    else:
        partes.append("sin mensajes esperando")
    partes.append("agenda conectada" if conn_ok_agenda else "agenda sin conectar")
    st.caption(":material/smart_toy: Secretario: " + " · ".join(partes))


# ---------------------------------------------------------------------------
# Pantalla
# ---------------------------------------------------------------------------

def render() -> None:
    user_id = st.session_state["current_user_id"]

    # Sin categorías todavía: la bienvenida de Finanzas va primero, igual que antes.
    if not finanzas_home._user_completo_onboarding(user_id):
        finanzas_home.render()
        return

    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    nombre = (st.session_state.get("current_user_fullname")
              or st.session_state.get("current_username") or "").split(" ")[0]
    st.title(f"{rs.saludo(ahora.hour)}, {nombre}" if nombre else rs.saludo(ahora.hour))
    st.caption(rs.fecha_larga(hoy).capitalize())

    with connect() as conn:
        saldo = rs.saldo_cuenta(conn, user_id=user_id)
        r = rs.resumen_del_mes(conn, user_id=user_id, hoy=hoy)
        filas = rs.ultimos_movimientos(conn, user_id=user_id)

    _render_saldo(saldo)
    if r is None or r.actual.movimientos == 0:
        st.info("Todavía no hay movimientos este mes. Cargalos en **Finanzas → Transacciones** "
                "o mandándole un gasto al Secretario por WhatsApp (por ejemplo, `2500, super`).")
    else:
        _render_mes(r)

    agenda_ok = _render_agenda(hoy)
    _render_movimientos(filas)
    _render_estado(agenda_ok)
