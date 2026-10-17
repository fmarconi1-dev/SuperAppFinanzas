"""Comandos de agenda por WhatsApp (Fase B, ADR-0008): `evento:`, `tarea:`, `agenda`.

**Puro y sin red**: interpreta el texto y arma las respuestas. Quien habla con
Google es `core/api/google.py` (vía el Apps Script), y quien junta las dos
cosas es `comandos.procesar`.

Formatos:

    evento: fecha, [hora inicio], [hora fin], título[, descripción]
    tarea: [fecha], título[, descripción]
    agenda

Las fechas de agenda **pueden ser futuras** (al revés que en un gasto):
``hoy``, ``mañana``, ``pasado mañana``, un día de la semana (``viernes`` = el
próximo viernes, o hoy si es viernes), ``DD/MM``, ``DD/MM/AAAA``,
``AAAA-MM-DD``. Un ``DD/MM`` sin año que ya pasó es del año que viene; uno con
año que ya pasó se rechaza. La confirmación siempre muestra el día de la
semana, así un error de fecha salta a la vista.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Optional

DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
_DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4,
         "sabado": 5, "domingo": 6}
_RE_SEPARADOR = re.compile(r"\s*[,;|]\s*")
_RE_HORA = re.compile(r"^(\d{1,2})(?:[:.h](\d{2}))?\s*(?:hs|h|hrs)?\.?$", re.IGNORECASE)
_RE_RANGO = re.compile(r"^(.+?)\s*(?:-|–|a)\s*(.+)$", re.IGNORECASE)
_RE_FECHA = re.compile(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$")
_RE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")

FORMATO_EVENTO = "evento: fecha, [hora inicio], [hora fin], título[, descripción]"
FORMATO_TAREA = "tarea: [fecha], título[, descripción]"


class AgendaInvalida(ValueError):
    """El comando no se puede mandar a Google tal como está. El texto va a Franco."""


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c)).lower().strip()


def dia_corto(d: date, hoy: date) -> str:
    """"vie 17/10", o "vie 17/10/2027" si no es de este año."""
    base = f"{DIAS_CORTOS[d.weekday()]} {d:%d/%m}"
    return base if d.year == hoy.year else f"{base}/{d:%Y}"


# ---------------------------------------------------------------------------
# Fechas y horas
# ---------------------------------------------------------------------------

def parsear_fecha_agenda(crudo: str, hoy: date) -> Optional[date]:
    """La fecha, o None si el texto no es una fecha. `AgendaInvalida` si es una fecha imposible."""
    s = _sin_acentos(crudo)
    if s == "hoy":
        return hoy
    if s in {"manana"}:
        return hoy + timedelta(days=1)
    if s in {"pasado manana", "pasado"}:
        return hoy + timedelta(days=2)
    if s in _DIAS:
        return hoy + timedelta(days=(_DIAS[s] - hoy.weekday()) % 7)

    if m := _RE_ISO.match(s):
        a, mes, d = (int(x) for x in m.groups())
        con_anio = True
    elif m := _RE_FECHA.match(s):
        d, mes = int(m.group(1)), int(m.group(2))
        con_anio = m.group(3) is not None
        a = int(m.group(3)) if con_anio else hoy.year
        if a < 100:
            a += 2000
    else:
        return None
    try:
        f = date(a, mes, d)
    except ValueError:
        raise AgendaInvalida(f"La fecha «{crudo.strip()}» no existe.") from None
    if f < hoy:
        if con_anio:
            raise AgendaInvalida(f"La fecha {f:%d/%m/%Y} ya pasó.")
        f = date(a + 1, mes, d)
    return f


def parsear_hora(crudo: str) -> Optional[str]:
    """"15", "15hs", "15:30", "9.30", "15h30" → "HH:MM". None si no es una hora."""
    m = _RE_HORA.match(crudo.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h > 23 or mi > 59:
        raise AgendaInvalida(f"La hora «{crudo.strip()}» no existe.")
    return f"{h:02d}:{mi:02d}"


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def parsear_evento(cuerpo: str, hoy: date) -> dict:
    """Lo que va después de `evento:` → campos para `crear_evento`."""
    partes = [p for p in _RE_SEPARADOR.split(cuerpo.strip()) if p]
    if len(partes) < 2:
        raise AgendaInvalida(f"Faltan datos. Formato: {FORMATO_EVENTO}")
    fecha = parsear_fecha_agenda(partes[0], hoy)
    if fecha is None:
        raise AgendaInvalida(f"«{partes[0]}» no es una fecha. Formato: {FORMATO_EVENTO}")

    i, hora_inicio, hora_fin = 1, None, None
    # "15:00-16:00" en un solo bloque.
    if (m := _RE_RANGO.match(partes[1])) and parsear_hora(m.group(1)) and parsear_hora(m.group(2)):
        hora_inicio, hora_fin, i = parsear_hora(m.group(1)), parsear_hora(m.group(2)), 2
    elif (hi := parsear_hora(partes[1])) is not None:
        hora_inicio, i = hi, 2
        if len(partes) > 2 and (hf := parsear_hora(partes[2])) is not None:
            hora_fin, i = hf, 3
    if hora_fin and hora_fin <= hora_inicio:
        raise AgendaInvalida(f"La hora de fin ({hora_fin}) tiene que ser después de la de inicio ({hora_inicio}).")
    if len(partes) <= i:
        raise AgendaInvalida(f"Falta el título. Formato: {FORMATO_EVENTO}")
    return {
        "fecha": fecha.isoformat(),
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "titulo": partes[i],
        "descripcion": ", ".join(partes[i + 1:]) or None,
    }


def parsear_tarea(cuerpo: str, hoy: date) -> dict:
    """Lo que va después de `tarea:` → campos para `crear_tarea`."""
    partes = [p for p in _RE_SEPARADOR.split(cuerpo.strip()) if p]
    if not partes:
        raise AgendaInvalida(f"Falta el título. Formato: {FORMATO_TAREA}")
    fecha = parsear_fecha_agenda(partes[0], hoy) if len(partes) > 1 else None
    if fecha is not None:
        partes = partes[1:]
    return {
        "fecha": fecha.isoformat() if fecha else None,
        "titulo": partes[0],
        "descripcion": ", ".join(partes[1:]) or None,
    }


def confirmar_evento(ev: dict, hoy: date) -> str:
    cuando = dia_corto(date.fromisoformat(ev["fecha"]), hoy)
    if ev["hora_inicio"]:
        cuando += f", {ev['hora_inicio']}" + (f"–{ev['hora_fin']}" if ev["hora_fin"] else "")
    else:
        cuando += ", todo el día"
    return f"✅ Evento agendado: {ev['titulo']} ({cuando})"


def confirmar_tarea(t: dict, hoy: date) -> str:
    linea = f"✅ Tarea creada: {t['titulo']}"
    if t["fecha"]:
        linea += f" (vence {dia_corto(date.fromisoformat(t['fecha']), hoy)})"
    return linea


def formatear_semana(datos: dict, hoy: date) -> str:
    """La respuesta de `resumen_semana` del Apps Script → texto para WhatsApp."""
    lineas = ["*🗓️ Agenda de la semana*"]
    eventos = datos.get("eventos") or []
    if not eventos:
        lineas.append("Sin eventos de hoy a 7 días.")
    dia_actual = None
    for ev in eventos:
        inicio = str(ev.get("inicio", ""))
        d = date.fromisoformat(inicio[:10])
        if d != dia_actual:
            dia_actual = d
            etiqueta = "Hoy" if d == hoy else ("Mañana" if d == hoy + timedelta(days=1) else "")
            lineas.append(f"\n*{dia_corto(d, hoy)}*" + (f" · {etiqueta}" if etiqueta else ""))
        hora = "Todo el día" if ev.get("todo_el_dia") else inicio[11:16]
        lineas.append(f"  {hora} {ev.get('titulo', '(sin título)')}")

    tareas = datos.get("tareas") or []
    lineas.append("\n*✅ Tareas pendientes*")
    if not tareas:
        lineas.append("Ninguna.")
    for t in tareas:
        vence = t.get("vence")
        sufijo = ""
        if vence:
            v = date.fromisoformat(vence)
            sufijo = f" (vence {dia_corto(v, hoy)}{' — vencida' if v < hoy else ''})"
        lineas.append(f"  • {t.get('titulo', '(sin título)')}{sufijo}")
    return "\n".join(lineas)
