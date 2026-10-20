"""Una foto o captura → una propuesta (Fase D, paso 6, ADR-0009 §8).

Gemini (`core/api/gemini.py`) solo devuelve filas crudas. Acá todo es
determinístico:

1. **Validar** cada fila: fecha real y no futura (sin año, la más cercana
   hacia atrás), monto positivo y descripción. Lo que no pasa se descarta y
   se dice cuántas.
2. **Sin duplicar:** si ya hay algo cargado con ese monto (±$1) en la
   ventana de siempre (5 días antes a 2 después), se muestra como "ya lo
   tenías" y no se carga.
3. Lo demás se **propone** con la categoría aprendida para esa descripción, o
   preguntando. Con el `ok` se carga como si Franco lo hubiera mandado por
   WhatsApp (un gasto a mano: después lo empareja el extracto o el resumen).
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from places.finanzas.core import conciliacion as conc
from places.finanzas.core import lotes
from places.finanzas.core.lotes import Actualizar, Insertar, InsertarMovimiento, Movimiento

TIPO_REGLA = "FOTO"
_RE_FECHA = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")


def _fecha(texto: str, hoy: date) -> Optional[date]:
    m = _RE_FECHA.match(str(texto or "").strip())
    if not m:
        return None
    a, mes, d = (int(x) for x in m.groups())
    try:
        f = date(a if a else hoy.year, mes, d)
    except ValueError:
        return None
    if not a and f > hoy:
        f = f.replace(year=hoy.year - 1)
    return f if f <= hoy else None


def _clave(descripcion: str) -> str:
    """La descripción sin números ni signos: lo que se aprende como "comercio"."""
    partes = [p for p in re.split(r"\s+", descripcion.upper()) if not any(c.isdigit() for c in p)]
    return " ".join(partes).strip(" *-.") or descripcion.upper()


def validar(filas: list, hoy: date) -> tuple[list[dict], int]:
    """(filas buenas, cuántas se descartaron)."""
    buenas, malas = [], 0
    for f in filas:
        if not isinstance(f, dict):
            malas += 1
            continue
        fecha = _fecha(f.get("fecha"), hoy)
        monto = f.get("monto")
        desc = " ".join(str(f.get("descripcion") or "").split())[:80]
        if fecha is None or not isinstance(monto, (int, float)) or monto <= 0 or not desc:
            malas += 1
            continue
        buenas.append({"fecha": fecha.isoformat(), "descripcion": desc,
                       "monto": round(float(monto), 2), "es_ingreso": bool(f.get("es_ingreso"))})
    return buenas, malas


def _ya_cargado(conn: sqlite3.Connection, wid: int, f: dict) -> Optional[str]:
    fecha = date.fromisoformat(f["fecha"])
    columna = "ingresos" if f["es_ingreso"] else "pasivos"
    for t in conn.execute(
            f"SELECT motivo, fecha, {columna} AS importe FROM transacciones WHERE workspace_id = ? "
            f"AND fecha BETWEEN ? AND ? AND {columna} > 0 ORDER BY fecha",
            (wid, (fecha - timedelta(days=conc.DIAS_DESPUES)).isoformat(),
             (fecha + timedelta(days=conc.DIAS_ANTES)).isoformat())):
        if abs(t["importe"] - f["monto"]) <= 1:
            return f"{t['motivo']} {conc.pesos_c(round(t['importe'] * 100))} ({date.fromisoformat(t['fecha']):%d/%m})"
    return None


def proponer(conn: sqlite3.Connection, filas: list[dict], descartadas: int, *, wid: int) -> dict:
    items = []
    for f in filas:
        regla = conn.execute("SELECT motivo FROM reglas_comercio WHERE workspace_id = ? AND tipo = ? "
                             "AND comercio = ?", (wid, TIPO_REGLA, _clave(f["descripcion"]))).fetchone()
        items.append({**f, "motivo": regla["motivo"] if regla else None,
                      "ya": _ya_cargado(conn, wid, f)})
    n = 0
    for it in items:
        if not it["ya"]:
            n += 1
            it["n"] = n
    return {"tipo": "foto", "items": items, "numerados": n, "descartadas": descartadas}


def texto(prop: dict) -> str:
    items = prop["items"]
    if not items:
        extra = (f" ({prop['descartadas']} no se leían bien)" if prop["descartadas"] else "")
        return f"📷 No encontré movimientos en la foto{extra}. Si es un extracto o un resumen, mandá el archivo."
    lineas = ["📷 En la foto veo:"]
    for it in items:
        signo = "+" if it["es_ingreso"] else ""
        base = (f"{date.fromisoformat(it['fecha']):%d/%m} {it['descripcion']} "
                f"{signo}{conc.pesos_c(round(it['monto'] * 100))}")
        if it["ya"]:
            lineas.append(f"   ✔ {base} = ya lo tenías: {it['ya']}")
        elif it.get("descartado"):
            lineas.append(f"{it['n']}. {base} → no se carga")
        else:
            lineas.append(f"{it['n']}. {base} → {it['motivo'] or '¿categoría?'}")
    if prop["descartadas"]:
        lineas.append(f"({prop['descartadas']} fila(s) no se leían bien y las dejé afuera.)")
    if prop["numerados"]:
        lineas.append("\nLo leí con Gemini: revisá montos y fechas. ¿Va? Contestá *ok*. "
                      "Para corregir antes: *1 compras* · *1 no* · *cancelar*")
    else:
        lineas.append("\nNo hay nada nuevo para cargar.")
    return "\n".join(lineas)


def responder(conn: sqlite3.Connection, lote: lotes.Lote, *, aceptar: bool, cancelar: bool,
              correcciones: tuple[tuple[int, str], ...], user_id: int, wid: int,
              ahora: datetime) -> conc.Resultado:
    from places.finanzas.core.comandos import resolver_categoria  # diferido

    if cancelar:
        lotes.descartar(conn, lote.id)
        return conc.Resultado("Listo, no cargué nada de la foto.", "rechazado")
    prop = lote.propuesta
    por_n = {it["n"]: it for it in prop["items"] if it.get("n")}
    existentes = conc._motivos(conn, wid)
    dudosa = False
    for n, que in correcciones:
        it = por_n.get(n)
        if it is None:
            continue
        if conc._norm(que) in {"no", "sacar"}:
            it["descartado"] = True
            continue
        tipo, nombre = resolver_categoria(que, existentes)
        it.update(motivo=nombre if tipo != "nueva" else " ".join(que.split()).capitalize(),
                  descartado=False)
        dudosa = dudosa or tipo != "exacta"
    lotes.actualizar(conn, lote.id, prop)
    a_cargar = [it for it in prop["items"] if it.get("n") and not it.get("descartado")]
    faltan = [str(it["n"]) for it in a_cargar if not it["motivo"]]
    if aceptar and faltan:
        return conc.Resultado(f"Me falta la categoría de: {', '.join(faltan)}. Contestá "
                              f"*{faltan[0]} compras* (o *{faltan[0]} no*).", "pendiente")
    if not aceptar or dudosa:
        aviso = "Revisá y contestá *ok*.\n\n" if (aceptar and dudosa) else ""
        return conc.Resultado(aviso + texto(prop), "pendiente")
    if not a_cargar:
        lotes.descartar(conn, lote.id)
        return conc.Resultado("No quedó nada para cargar.", "rechazado")
    grupos = conc._grupos(conn, wid)
    ops: list = []
    reglas: dict[str, str] = {}
    for it in a_cargar:
        pasivos, ingresos = (0.0, it["monto"]) if it["es_ingreso"] and grupos.get(
            it["motivo"]) == "Ingreso" else ((-it["monto"], 0.0) if it["es_ingreso"]
                                             else (it["monto"], 0.0))
        ops.append(InsertarMovimiento(Movimiento(
            fecha=date.fromisoformat(it["fecha"]), motivo=it["motivo"], pasivos=pasivos,
            ingresos=ingresos, comentario=f"Foto · {it['descripcion']}")))
        reglas[_clave(it["descripcion"])] = it["motivo"]
    for comercio, motivo in reglas.items():
        previa = conn.execute("SELECT id, motivo FROM reglas_comercio WHERE workspace_id = ? AND "
                              "tipo = ? AND comercio = ?", (wid, TIPO_REGLA, comercio)).fetchone()
        if previa is None:
            ops.append(Insertar("reglas_comercio", {"workspace_id": wid, "tipo": TIPO_REGLA,
                                                    "comercio": comercio, "motivo": motivo}))
        elif previa["motivo"] != motivo:
            ops.append(Actualizar("reglas_comercio", previa["id"], {"motivo": motivo}))
    lotes.aplicar_operaciones(conn, lote.id, ops, user_id=user_id, ahora=ahora)
    return conc.Resultado(f"✅ Cargué {len(a_cargar)} de la foto.\n*deshacer* los borra.", "lote")
