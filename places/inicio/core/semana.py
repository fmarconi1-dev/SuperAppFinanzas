"""La semana y las tareas del Inicio (Fase C, paso 3). **Puro, sin Streamlit.**

Toma la respuesta de `resumen_semana` del Apps Script (la misma que usa el
comando `agenda` por WhatsApp) y la deja lista para mostrar:

* **Eventos agrupados por día**, con "Hoy" y "Mañana" marcados. Un evento que
  empezó antes de hoy y sigue (varios días, o uno que cruzó la medianoche) se
  muestra en **hoy**, no en un día que ya pasó y no aparece en la lista.
* **Tareas ordenadas:** las vencidas primero, después las que tienen fecha
  (la más próxima arriba) y al final las sin fecha. Una vencida lo dice con
  texto, no solo con color.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from places.finanzas.core.agenda import dia_corto


@dataclass
class Evento:
    hora: str               # "15:00" o "Todo el día"
    titulo: str
    ubicacion: str = ""
    hasta: Optional[date] = None   # último día, si dura más de uno


@dataclass
class Dia:
    fecha: date
    etiqueta: str           # "Hoy", "Mañana" o ""
    titulo: str             # "vie 17/10"
    eventos: list[Evento] = field(default_factory=list)


@dataclass
class Tarea:
    id: str
    lista_id: str
    titulo: str
    vence: Optional[date]
    vencida: bool
    detalle: str            # "vencida mié 14/10" · "vence dom 25/10" · ""


def _fecha(valor: str) -> date:
    return date.fromisoformat(str(valor)[:10])


def dias_de_la_semana(eventos: list[dict], hoy: date) -> list[Dia]:
    """Eventos del Apps Script → días con sus eventos, en orden."""
    por_dia: dict[date, Dia] = {}
    for ev in eventos:
        inicio = _fecha(ev.get("inicio", ""))
        fin = _fecha(ev.get("fin") or ev.get("inicio", ""))
        dia = max(inicio, hoy)
        if dia not in por_dia:
            etiqueta = "Hoy" if dia == hoy else ("Mañana" if dia == hoy + timedelta(days=1) else "")
            por_dia[dia] = Dia(fecha=dia, etiqueta=etiqueta, titulo=dia_corto(dia, hoy))
        todo_el_dia = bool(ev.get("todo_el_dia"))
        if todo_el_dia:
            hora = "Todo el día"
        elif inicio < dia:
            hora = "En curso"   # empezó antes de hoy: su hora de inicio confundiría
        else:
            hora = str(ev.get("inicio", ""))[11:16]
        por_dia[dia].eventos.append(Evento(
            hora=hora,
            titulo=str(ev.get("titulo") or "(sin título)"),
            ubicacion=str(ev.get("ubicacion") or ""),
            hasta=fin if fin > dia else None,
        ))
    return [por_dia[d] for d in sorted(por_dia)]


def tareas_ordenadas(tareas: list[dict], hoy: date) -> list[Tarea]:
    """Tareas pendientes: vencidas, con fecha, sin fecha."""
    salida = []
    for t in tareas:
        vence = _fecha(t["vence"]) if t.get("vence") else None
        vencida = vence is not None and vence < hoy
        if vence is None:
            detalle = ""
        elif vencida:
            detalle = f"vencida {dia_corto(vence, hoy)}"
        elif vence == hoy:
            detalle = "vence hoy"
        else:
            detalle = f"vence {dia_corto(vence, hoy)}"
        salida.append(Tarea(id=str(t.get("id", "")), lista_id=str(t.get("lista_id", "")),
                            titulo=str(t.get("titulo") or "(sin título)"),
                            vence=vence, vencida=vencida, detalle=detalle))
    # Orden estable: a igual grupo y fecha queda el orden de Google Tasks (el
    # que Franco arma a mano), no el alfabético.
    salida.sort(key=lambda t: (0 if t.vencida else 1 if t.vence else 2, t.vence or date.max))
    return salida
