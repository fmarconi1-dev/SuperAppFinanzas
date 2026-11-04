"""Lenguaje natural en el Secretario (Fase E, ADR-0012): Gemini traduce, el código decide.

Cuando `comandos.procesar` no entiende un mensaje (o lo entiende con una
categoría nueva, la señal medida de que leyó mal: «5000 en el chino»), se le
pide a Gemini **la orden en la gramática de siempre**. Esa orden:

* se valida contra los mismos parsers (`clasificar`): si no es una orden que
  el bot entiende, se descarta y Franco recibe la respuesta de siempre;
* si **escribe** algo (un gasto, un `ok`, un `deshacer`, un evento), no corre:
  se le muestra a Franco («Entendí: …») y corre solo con su *sí* (un
  `pendiente` de tipo `traduccion`, que vence a los 10 minutos);
* si solo **consulta** (`resumen`, `agenda`, `ayuda`), corre directo.

Gemini también puede repreguntar (falta un dato) o contestar una duda sobre la
propuesta abierta, solo con lo que dice el contexto. Si no contesta, se dice.
El cliente llega inyectado (`traductor`): acá no hay red.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Any, Callable, Optional

from core.api.gemini import GeminiNoDisponible
from places.finanzas.core import agenda as ag
from places.finanzas.core import lotes, saldos
from places.finanzas.core.comandos import (
    AYUDA,
    EntradaInvalida,
    Respuesta,
    _RE_COMANDO_AGENDA,
    _borrar_pendiente,
    _cantidad,
    _leer_respuesta_lote,
    _texto_propuesta,
    guardar_estado,
    normalizar,
    parsear_gasto,
)
from places.finanzas.core.transactions import all_motivos

#: Órdenes que solo leen: corren sin pedir el *sí*.
CONSULTAS = {"resumen", "saldo", "agenda", "semana", "ayuda", "help", "comandos",
             "balances todas", "balances todos"}

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

_CORRECCIONES = (
    "Correcciones a una propuesta abierta (por número de renglón, separadas por coma): "
    "N categoría · N no (no se carga) · N es ID (es ese gasto ya cargado) · "
    "N efectivo / N tarjeta (para lo que sobra) · ok (acepta) · cancelar (descarta)."
)


def contexto(conn: sqlite3.Connection, *, user_id: int, wid: int, hoy: date,
             ahora: datetime) -> str:
    """Lo que Gemini necesita para traducir: hoy, la gramática, las categorías y la
    propuesta abierta tal como la ve Franco (ADR-0012: renglones incluidos)."""
    partes = [
        f"Hoy: {_DIAS[hoy.weekday()]} {hoy:%d/%m/%Y} (Buenos Aires).",
        "GRAMÁTICA DEL BOT\n" + AYUDA + "\n" + _CORRECCIONES,
        "CATEGORÍAS EXISTENTES\n" + ", ".join(sorted(set(all_motivos(conn, user_id=user_id)))),
    ]
    lote = lotes.vigente(conn, workspace_id=wid, ahora=ahora)
    if lote:
        partes.append("PROPUESTA ABIERTA (lo que Franco tiene en pantalla)\n"
                      + _texto_de_propuesta(lote.propuesta, hoy))
    return "\n\n".join(partes)


def _texto_de_propuesta(prop: dict, hoy: date) -> str:
    from places.finanzas.core import conciliacion, fotos, tarjetas  # diferido: usan comandos

    tipo = prop.get("tipo")
    if tipo == "extracto":
        return conciliacion.texto_propuesta(prop, nuevo_ancla=bool(prop.get("ancla")))
    if tipo == "resumen":
        return tarjetas.texto(prop)
    if tipo == "foto":
        return fotos.texto(prop)
    if tipo == "saldos":
        return saldos.texto(prop)
    return _texto_propuesta(prop["items"], hoy)


def clasificar(orden: str, *, hoy: date, cantidad: int) -> Optional[str]:
    """'consulta' (solo lee), 'escribe' (pide el *sí*), 'propone' (pide el *sí* y arma
    una propuesta nueva: varios gastos o saldos) o None si el bot no la entiende.

    `cantidad`: los renglones de la propuesta abierta (0 si no hay). Se valida
    con los mismos parsers que usa `procesar`, sin tocar la base.
    """
    clave = normalizar(orden).strip(" .!¡?¿")
    if not clave:
        return None
    if clave in CONSULTAS:
        return "consulta"
    if clave in {"deshacer", "borrar ultimo", "borra ultimo"}:
        return "escribe"
    if clave == "balances" or clave.startswith("balances "):
        return "escribe"
    if m := _RE_COMANDO_AGENDA.match(orden):
        comando = m.group(1).lower()
        try:
            if comando == "evento":
                ag.parsear_evento(m.group(2), hoy)
            else:
                ag.parsear_tarea(m.group(2), hoy)
        except ag.AgendaInvalida:
            return None
        return "escribe"
    if cantidad and _leer_respuesta_lote(orden, cantidad):
        return "escribe"
    try:
        if saldos.parsear(orden, hoy):
            return "propone"
    except EntradaInvalida:
        return None
    # Un gasto traducido va con coma ("5000, compras"). Sin coma, "9 salidas" es
    # una corrección a un renglón que no existe, no un gasto de $9.
    renglones = [r.strip() for r in orden.splitlines() if r.strip()]
    try:
        for renglon in renglones:
            if "," not in renglon:
                return None
            parsear_gasto(renglon, hoy)
    except EntradaInvalida:
        return None
    return "propone" if len(renglones) >= 2 else "escribe"


def _misma_carga(orden: str, texto: str, hoy: date) -> bool:
    """¿La orden es lo mismo que ya había leído el parser? Entonces Gemini no ayudó."""
    if normalizar(orden) == normalizar(texto):
        return True
    try:
        a, b = parsear_gasto(orden, hoy), parsear_gasto(texto, hoy)
    except EntradaInvalida:
        return False
    return (a.fecha, a.monto, a.es_ingreso, normalizar(a.categoria)) == \
        (b.fecha, b.monto, b.es_ingreso, normalizar(b.categoria))


def entender(
    conn: sqlite3.Connection,
    texto: str,
    traductor: Any,
    *,
    respaldo: Respuesta,
    ejecutar: Callable[[str], Respuesta],
    user_id: int,
    wid: int,
    hoy: date,
    ahora: datetime,
) -> Respuesta:
    """Lo que se contesta cuando el parser no entendió `texto` (`respaldo` es su respuesta).

    `ejecutar(orden)` corre una orden con `procesar`, sin traductor (las
    consultas, que no piden *sí*). Si Gemini no ayuda, vuelve `respaldo` tal cual.
    """
    try:
        t = traductor.traducir(texto, contexto(conn, user_id=user_id, wid=wid, hoy=hoy,
                                               ahora=ahora))
    except GeminiNoDisponible as e:
        return Respuesta(respaldo.texto + f"\n\n(Quise entenderlo con Gemini y no pude: {e}.)",
                         respaldo.resultado, respaldo.transaccion_id)

    if t.tipo in ("pregunta", "respuesta") and t.texto:
        # Lo que el parser dejó pendiente («¿La creo?») ya no es la pregunta.
        if respaldo.resultado == "pendiente":
            _borrar_pendiente(conn)
        return Respuesta("🤖 " + t.texto, "consulta")
    if t.tipo != "orden" or not t.orden or _misma_carga(t.orden, texto, hoy):
        return respaldo

    lote = lotes.vigente(conn, workspace_id=wid, ahora=ahora)
    clase = clasificar(t.orden, hoy=hoy, cantidad=_cantidad(lote.propuesta) if lote else 0)
    if clase is None:
        return respaldo
    if clase == "propone" and lote:
        # Varios gastos o saldos arman una propuesta nueva y tirarían la abierta (la
        # conciliación que Franco está revisando). Eso no se hace por una traducción.
        if respaldo.resultado == "pendiente":
            _borrar_pendiente(conn)
        return Respuesta(f"🤖 Entendí:\n{t.orden}\n\nPero eso reemplazaría la propuesta que "
                         "tenés abierta. Terminala (*ok*) o descartala (*cancelar*) y "
                         "mandalo de nuevo.", "rechazado")
    if clase == "consulta":
        if respaldo.resultado == "pendiente":
            _borrar_pendiente(conn)
        r = ejecutar(t.orden)
        return Respuesta(f"🤖 Entendí: *{t.orden}*\n\n{r.texto}", r.resultado, r.transaccion_id)

    guardar_estado(conn, "pendiente", json.dumps({
        "tipo": "traduccion", "orden": t.orden, "mensaje": texto,
        "creado_en": ahora.isoformat(),
    }), ahora)
    return Respuesta(f"🤖 Entendí:\n{t.orden}\n\n¿Va? Respondé *sí* o *no*.", "pendiente")
