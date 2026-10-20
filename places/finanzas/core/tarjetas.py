"""Desarmar el pago de la tarjeta con su resumen (Fase D, paso 5, ADR-0009 §3).

El pago de la tarjeta en la caja es un **contenedor**: se reemplaza por los
gastos reales del resumen que cubre. Regla verificada con los 9 resúmenes de
Franco (todos cierran al centavo):

* **Gastos reales** = consumos en pesos + IIBB + IVA (+ intereses o comisiones).
* **Diferencia** = lo pagado en la caja − los gastos reales: la percepción
  RG 5617 del 30% que se pagó (positiva) o que el banco devolvió (negativa).
  Va a la línea neutra **"Percepción 30% (se devuelve)"** (Flujo Capital): no
  es gasto. Su acumulado arranca en cero el día del corte (Franco, 19/10).
* **Todo con la fecha del pago en la caja**, no la de cada compra: así cuadra
  el saldo y no se tocan meses cerrados. Las cuotas se cargan como vienen.
* **Consumos en dólares**: "Venta divisa" + el gasto, al mismo precio. El
  precio es el de la compra de dólares de ese día en la caja; si no hubo, el
  oficial vendedor de esa fecha (ArgentinaDatos); si la fuente no contesta, se
  le pregunta a Franco (``dolar 1540``). Siempre se dice cuál se usó.
* Antes de cargar un consumo se busca **un gasto ya cargado** (la misma regla
  que con el banco, contra la fecha de la compra): no se duplica.

Cuándo pasa: el resumen se **guarda** apenas llega (no mueve plata). Si el
pago ya está en la caja esperando, se propone el desarmado; si no, se propone
cuando llegue el extracto con el pago. El desarmado es un lote: no escribe
nada hasta el `ok`, y `deshacer` deja el pago otra vez esperando.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

from places.finanzas.core import conciliacion as conc
from places.finanzas.core import lotes
from places.finanzas.core.extracto_galicia import FilaBanco
from places.finanzas.core.lotes import Actualizar, Insertar, InsertarMovimiento, Movimiento, Ref
from places.finanzas.core.resumen_tarjeta import Consumo, Linea, Resumen

#: Un pago de la caja cubre el resumen si cae después del cierre y hasta 5 días
#: después del vencimiento (el débito automático a veces se asienta tarde).
DIAS_DESPUES_DEL_VENCIMIENTO = 5
MOTIVO_VENTA = "Venta divisa"

Cotizador = Callable[[date], tuple[float, date]]


# ---------------------------------------------------------------------------
# Guardar el resumen
# ---------------------------------------------------------------------------

def _a_json(r: Resumen) -> str:
    return json.dumps(asdict(r), default=lambda x: x.isoformat())


def _de_json(texto: str) -> Resumen:
    d = json.loads(texto)
    fechas = ("cierre_anterior", "vencimiento_anterior", "cierre", "vencimiento",
              "cierre_proximo", "vencimiento_proximo")

    def lineas(xs):
        return [Linea(date.fromisoformat(x["fecha"]), x["texto"], x["pesos"], x["dolares"])
                for x in xs]

    return Resumen(
        d["tarjeta"], *(date.fromisoformat(d[f]) for f in fechas),
        saldo_anterior=tuple(d["saldo_anterior"]), total=tuple(d["total"]),
        pagos=lineas(d["pagos"]), devoluciones=lineas(d["devoluciones"]),
        consumos=[Consumo(date.fromisoformat(c["fecha"]), c["referencia"], c["pesos"],
                          c["dolares"], c["cuota"], c["plastico"]) for c in d["consumos"]],
        cargos=lineas(d["cargos"]), percepciones=lineas(d["percepciones"]))


def _pagos(conn: sqlite3.Connection, wid: int, tarjeta: str, cierre: date,
           vencimiento: date) -> list[dict]:
    """Las filas de la caja que pagaron este resumen y esperan desarmarse."""
    return [dict(f) for f in conn.execute(
        "SELECT id, fecha, monto FROM banco_filas WHERE workspace_id = ? AND estado = "
        "'esperando_resumen' AND tipo LIKE ? AND fecha > ? AND fecha <= ? ORDER BY orden",
        (wid, f"PAGO TARJETA %{tarjeta}%", cierre.isoformat(),
         (vencimiento + timedelta(days=DIAS_DESPUES_DEL_VENCIMIENTO)).isoformat()))]


def recibir(conn: sqlite3.Connection, r: Resumen, *, user_id: int, wid: int, ahora: datetime,
            cotizador: Optional[Cotizador]) -> tuple[str, Optional[dict]]:
    """Guarda el resumen (si no estaba) y, si su pago ya está en la caja, propone el desarmado."""
    previo = conn.execute("SELECT id, estado FROM resumenes WHERE workspace_id = ? AND tarjeta = ? "
                          "AND cierre = ?", (wid, r.tarjeta, r.cierre.isoformat())).fetchone()
    nombre = f"{r.tarjeta}, cierre {r.cierre:%d/%m}, vence {r.vencimiento:%d/%m}"
    if previo and previo["estado"] == "desarmado":
        return f"💳 Ya tenía el resumen {nombre}, y ya lo desarmé.", None
    if previo is None:
        conn.execute(
            "INSERT INTO resumenes (workspace_id, tarjeta, cierre, vencimiento, total_pesos, "
            "total_dolares, detalle, estado, guardado_en) VALUES (?, ?, ?, ?, ?, ?, ?, "
            "'esperando_pago', ?)",
            (wid, r.tarjeta, r.cierre.isoformat(), r.vencimiento.isoformat(), r.total[0],
             r.total[1], _a_json(r), ahora.isoformat()))
        resumen_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        resumen_id = previo["id"]
    prop = proponer(conn, resumen_id, user_id=user_id, wid=wid, ahora=ahora, cotizador=cotizador)
    if prop is None:
        dolares = f" y USD {r.total[1] / 100:,.2f}".replace(",", "X").replace(".", ",").replace(
            "X", ".") if r.total[1] else ""
        verbo = "Ya tenía guardado" if previo else "Guardé"
        return (f"💳 {verbo} el resumen {nombre} (total {conc.pesos_c(r.total[0])}{dolares}). "
                "Cuando me mandes el extracto con el pago, lo desarmo en sus gastos."), None
    return texto(prop), prop


# ---------------------------------------------------------------------------
# La propuesta
# ---------------------------------------------------------------------------

def con_pago(conn: sqlite3.Connection, wid: int) -> list[int]:
    """Resúmenes guardados cuyo pago ya apareció en la caja (para proponerlos)."""
    ids = []
    for f in conn.execute("SELECT id, tarjeta, cierre, vencimiento FROM resumenes WHERE "
                          "workspace_id = ? AND estado = 'esperando_pago' ORDER BY cierre",
                          (wid,)):
        if _pagos(conn, wid, f["tarjeta"], date.fromisoformat(f["cierre"]),
                  date.fromisoformat(f["vencimiento"])):
            ids.append(f["id"])
    return ids


def _cotizacion(conn: sqlite3.Connection, wid: int, fecha: date,
                cotizador: Optional[Cotizador]) -> tuple[Optional[dict], Optional[str]]:
    """(cotización, aviso). La de la caja ese día gana; si no, la pública; si no, None."""
    r = conn.execute("SELECT cotizacion FROM banco_filas WHERE workspace_id = ? AND tratamiento "
                     "= 'divisa' AND fecha = ? AND cotizacion IS NOT NULL ORDER BY orden DESC "
                     "LIMIT 1", (wid, fecha.isoformat())).fetchone()
    if r:
        return {"valor": r["cotizacion"],
                "fuente": f"la compra de dólares del {fecha:%d/%m} en la caja"}, None
    if cotizador is None:
        return None, "no tengo de dónde sacar el dólar"
    from core.api.cotizaciones import CotizacionNoDisponible

    try:
        valor, usada = cotizador(fecha)
    except CotizacionNoDisponible as e:
        return None, f"no pude traer el dólar oficial ({e})"
    return {"valor": valor, "fuente": f"el oficial vendedor del {usada:%d/%m} (ArgentinaDatos)"}, None


def _sueltos(conn: sqlite3.Connection, wid: int, desde: date, hasta: date) -> tuple[
        list[conc.Cargado], dict[int, int]]:
    """Lo cargado a mano sin pareja (o marcado "tarjeta"), y el vínculo "tarjeta" de cada uno."""
    tarjeta = {r["transaccion_id"]: r["id"] for r in conn.execute(
        "SELECT id, transaccion_id FROM emparejamientos WHERE workspace_id = ? AND rol = 'tarjeta'",
        (wid,))}
    filas = conn.execute(
        """
        SELECT t.id, t.fecha, t.pasivos, t.ingresos, t.motivo, t.creado_en, gc.bruto
        FROM transacciones t LEFT JOIN gasto_cuentas gc ON gc.transaccion_id = t.id
        WHERE t.workspace_id = ? AND t.fecha BETWEEN ? AND ? AND t.pasivos > 0
          AND NOT EXISTS (SELECT 1 FROM emparejamientos e WHERE e.transaccion_id = t.id
                          AND e.rol != 'tarjeta')
        ORDER BY t.id
        """, (wid, desde.isoformat(), hasta.isoformat())).fetchall()
    cargados = [conc.Cargado(f["id"], date.fromisoformat(f["fecha"]), float(f["pasivos"]),
                             float(f["ingresos"]), f["motivo"], f["creado_en"],
                             round(f["bruto"] * 100) if f["bruto"] is not None else None, None)
                for f in filas if conc._norm(f["motivo"]) not in conc._MOTIVOS_DEL_SECRETARIO]
    return cargados, tarjeta


def proponer(conn: sqlite3.Connection, resumen_id: int, *, user_id: int, wid: int,
             ahora: datetime, cotizador: Optional[Cotizador]) -> Optional[dict]:
    """La propuesta de desarmado, o None si el pago todavía no está en la caja."""
    fila = conn.execute("SELECT detalle FROM resumenes WHERE id = ?", (resumen_id,)).fetchone()
    r = _de_json(fila["detalle"])
    pagos = _pagos(conn, wid, r.tarjeta, r.cierre, r.vencimiento)
    if not pagos:
        return None
    fecha = max(date.fromisoformat(p["fecha"]) for p in pagos)
    pagado = -sum(p["monto"] for p in pagos)
    corte = conc.corte(conn, user_id, wid)
    existentes = conc._motivos(conn, wid)
    impuestos = conc.motivo_existente("Impuestos", existentes)

    def aprendida(comercio: str) -> Optional[str]:
        x = conn.execute("SELECT motivo FROM reglas_comercio WHERE workspace_id = ? AND tipo = ? "
                         "AND comercio = ?", (wid, f"TARJETA {r.tarjeta}", comercio)).fetchone()
        return x["motivo"] if x else None

    # Emparejar los consumos en pesos con lo cargado a mano, por la fecha de la compra.
    indices_en_pesos = [k for k, c in enumerate(r.consumos) if c.pesos > 0 and not c.dolares]
    en_pesos = [r.consumos[k] for k in indices_en_pesos]
    posicion = {k: i for i, k in enumerate(indices_en_pesos)}
    cargados, tarjeta_id = _sueltos(conn, wid, min([c.fecha for c in en_pesos] + [fecha])
                                    - timedelta(days=conc.DIAS_ANTES), fecha)
    por_id = {c.id: c for c in cargados}
    filas = [FilaBanco(c.fecha, -c.pesos, 0, "CONSUMO") for c in en_pesos]
    asignados, empates = conc.emparejar(filas, cargados)
    ajuste_inicial = conc._ajuste_inicial(conn, wid)

    items: list[dict] = []
    for k, c in enumerate(r.consumos):
        base = {"fecha_compra": c.fecha.isoformat(), "referencia": c.referencia,
                "comercio": c.comercio, "cuota": c.cuota}
        if c.dolares:
            items.append({**base, "clase": "usd", "dolares": c.dolares, "pesos_extra": c.pesos,
                          "motivo": aprendida(c.comercio)})
            continue
        i = posicion.get(k)
        if i is not None and i in asignados:
            cid, por = asignados[i]
            g = por_id[cid]
            items.append({**base, "clase": "coincide", "txn": cid, "pesos": c.pesos,
                          "desc": g.describir(), "por": por,
                          "correccion": c.pesos if por == "monto" and g.importe != c.pesos else None,
                          "arrastre": ajuste_inicial is not None and g.creado_en < ajuste_inicial,
                          "tarjeta_id": tarjeta_id.get(cid)})
        else:
            emp = empates.get(i, []) if i is not None else []
            items.append({**base, "clase": "consumo", "pesos": c.pesos,
                          "motivo": aprendida(c.comercio), "empate_ids": emp,
                          "empate": [por_id[x].describir() for x in emp]})
    for c in r.cargos:
        items.append({"clase": "cargo", "texto": c.texto, "pesos": c.pesos, "motivo": impuestos})

    # Se numera en el orden en que se muestra: primero lo que se carga, al final
    # lo que ya estaba cargado.
    n = 0
    for grupo in (("consumo", "usd", "cargo"), ("coincide",)):
        for it in items:
            if it["clase"] in grupo:
                n += 1
                it["n"] = n

    cotizacion, aviso = (None, None)
    if any(it["clase"] == "usd" for it in items):
        cotizacion, aviso = _cotizacion(conn, wid, fecha, cotizador)

    percepcion = conc.motivo_existente(conc.MOTIVO_PERCEPCION, existentes)
    acumulado = round(float(conn.execute(
        "SELECT COALESCE(SUM(pasivos), 0) FROM transacciones WHERE workspace_id = ? "
        "AND motivo = ? AND fecha >= ?", (wid, percepcion or conc.MOTIVO_PERCEPCION,
                                          corte.isoformat())).fetchone()[0]) * 100)
    anterior = conn.execute("SELECT pagado FROM resumenes WHERE workspace_id = ? AND tarjeta = ? "
                            "AND cierre = ? AND pagado IS NOT NULL",
                            (wid, r.tarjeta, r.cierre_anterior.isoformat())).fetchone()
    confirmacion = None
    if anterior is not None:
        confirmacion = ("ok" if anterior["pagado"] == r.pagado_en_pesos else
                        f"⚠️ Este resumen dice que pagaste {conc.pesos_c(r.pagado_en_pesos)} del "
                        f"anterior, y en la caja salieron {conc.pesos_c(anterior['pagado'])}.")
    en_tarjeta = [conc.Cargado.describir(c) for c in cargados
                  if c.id in tarjeta_id and r.cierre_anterior < c.fecha <= r.cierre
                  and c.id not in {it.get("txn") for it in items}]
    return {
        "tipo": "resumen", "resumen_id": resumen_id, "tarjeta": r.tarjeta,
        "cierre": r.cierre.isoformat(), "vencimiento": r.vencimiento.isoformat(),
        "pagos": [p["id"] for p in pagos], "fecha": fecha.isoformat(), "pagado": pagado,
        "gastos_reales": r.gastos_reales, "diferencia": pagado - r.gastos_reales,
        "acumulado": acumulado + pagado - r.gastos_reales, "items": items, "numerados": n,
        "cotizacion": cotizacion, "aviso_dolar": aviso, "confirmacion": confirmacion,
        "en_tarjeta_sin_resumen": en_tarjeta,
    }


# ---------------------------------------------------------------------------
# El texto
# ---------------------------------------------------------------------------

def _usd(c: int) -> str:
    entero, dec = divmod(abs(c), 100)
    return f"USD {entero:,}".replace(",", ".") + (f",{dec:02d}" if dec else "")


def _pesos_de(it: dict, prop: dict) -> Optional[int]:
    if prop["cotizacion"] is None:
        return None
    return round(it["dolares"] * prop["cotizacion"]["valor"]) + it.get("pesos_extra", 0)


def texto(prop: dict) -> str:
    f = date.fromisoformat(prop["fecha"])
    lineas = [f"💳 {prop['tarjeta']}, cierre {date.fromisoformat(prop['cierre']):%d/%m}, "
              f"vence {date.fromisoformat(prop['vencimiento']):%d/%m}.",
              f"Lo pagaste el {f:%d/%m} en la caja: {conc.pesos_c(prop['pagado'])}"
              + (f" ({len(prop['pagos'])} filas)" if len(prop["pagos"]) > 1 else "") + "."]
    if prop.get("confirmacion") and prop["confirmacion"] != "ok":
        lineas.append(prop["confirmacion"])
    lineas.append(f"\nSe desarma en (todo con fecha {f:%d/%m}):")
    for it in prop["items"]:
        if it["clase"] == "coincide":
            continue
        destino = it["motivo"] or "¿categoría?"
        if it.get("descartado"):
            destino = "no se carga"
        if it["clase"] == "cargo":
            lineas.append(f"{it['n']}. {it['texto']} {conc.pesos_c(it['pesos'])} → {destino}")
            continue
        cuota = f" ({it['cuota']})" if it.get("cuota") else ""
        if it["clase"] == "usd":
            pesos = _pesos_de(it, prop)
            monto = (f"{_usd(it['dolares'])} = {conc.pesos_c(pesos)}" if pesos is not None
                     else _usd(it["dolares"]))
            lineas.append(f"{it['n']}. {it['referencia']}{cuota} {monto} → {destino} "
                          f"(+ {MOTIVO_VENTA})")
        else:
            linea = f"{it['n']}. {it['referencia']}{cuota} {conc.pesos_c(it['pesos'])} → {destino}"
            if it.get("empate_ids") and not it.get("descartado"):
                opciones = " o ".join(f"#{i} {d}" for i, d in zip(it["empate_ids"], it["empate"]))
                linea += f"\n     ¿será {opciones}? Si es, contestá *{it['n']} es {it['empate_ids'][0]}*"
            lineas.append(linea)
    if any(it["clase"] == "usd" for it in prop["items"]):
        if prop["cotizacion"]:
            lineas.append(f"   Dólar a {conc.pesos_c(round(prop['cotizacion']['valor'] * 100))}: "
                          f"{prop['cotizacion']['fuente']}. Si va otro, *dolar 1540*.")
        else:
            lineas.append(f"   ⚠️ Me falta el dólar ({prop['aviso_dolar']}): contestá *dolar 1540*.")
    revisar = [it for it in prop["items"] if it["clase"] == "coincide"]
    if revisar:
        lineas.append("\n*Ya los tenías cargados* (si no es, contestá *N no*):")
        for it in revisar:
            linea = f"{it['n']}. {it['referencia']} {conc.pesos_c(it['pesos'])} = {it['desc']}"
            if it["correccion"]:
                linea += f" → lo corrijo a {conc.pesos_c(it['correccion'])}"
            if it["arrastre"]:
                linea += " · ya estaba en el ajuste inicial: lo descuento del ajuste"
            lineas.append(linea)
    d = prop["diferencia"]
    lineas.append(f"\n{conc.MOTIVO_PERCEPCION}: {'+' if d >= 0 else '-'}{conc.pesos_c(abs(d))} "
                  f"(lo pagado menos los gastos reales; no es gasto).")
    a = prop["acumulado"]
    lineas.append(f"   Acumulado desde el corte: {'+' if a >= 0 else '-'}{conc.pesos_c(abs(a))}"
                  + (" ✔" if a == 0 else " (vuelve a cero cuando el banco termina de devolverla; "
                     "los primeros meses arrastra lo que venía de antes del corte)"))
    if prop.get("en_tarjeta_sin_resumen"):
        lineas.append("\nMarcaste como tarjeta y no están en este resumen: "
                      + "; ".join(prop["en_tarjeta_sin_resumen"]) + ".")
    lineas.append("\n¿Va? Contestá *ok*. Para corregir antes: *2 salidas* · *2 no* · *cancelar*")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Respuestas y aplicar
# ---------------------------------------------------------------------------

def responder(conn: sqlite3.Connection, lote: lotes.Lote, *, aceptar: bool, cancelar: bool,
              correcciones: tuple[tuple[int, str], ...], user_id: int, wid: int,
              ahora: datetime, dolar: Optional[float] = None) -> conc.Resultado:
    from places.finanzas.core.comandos import resolver_categoria  # diferido

    if cancelar:
        lotes.descartar(conn, lote.id)
        return conc.Resultado("Listo, descarté el desarmado: el pago sigue esperando.", "rechazado")
    prop = lote.propuesta
    if dolar is not None:
        prop["cotizacion"] = {"valor": dolar, "fuente": "el que me dijiste"}
    por_n = {it["n"]: it for it in prop["items"] if it.get("n")}
    errores, dudosa = [], False
    existentes = conc._motivos(conn, wid)
    for n, que in correcciones:
        it = por_n.get(n)
        if it is None:
            errores.append(f"{n}: no está en la propuesta")
            continue
        clave = conc._norm(que)
        if clave in {"no", "sacar"}:
            if it["clase"] == "coincide":
                it.update(clase="consumo", motivo=None, empate_ids=[], empate=[])
            else:
                it["descartado"] = True
            continue
        if clave.startswith("es "):
            cid = clave.removeprefix("es ").lstrip("#").strip()
            if not cid.isdigit() or int(cid) not in it.get("empate_ids", []):
                errores.append(f"{n}: *es* solo sirve para elegir entre los que te mostré")
                continue
            it.update(clase="coincide", txn=int(cid), por="monto", correccion=None,
                      desc=it["empate"][it["empate_ids"].index(int(cid))], arrastre=False,
                      tarjeta_id=None)
            continue
        tipo, nombre = resolver_categoria(que, existentes)
        it.update(motivo=nombre if tipo != "nueva" else " ".join(que.split()).capitalize(),
                  descartado=False)
        dudosa = dudosa or tipo != "exacta"
    lotes.actualizar(conn, lote.id, prop)
    if errores:
        return conc.Resultado("⚠️ " + "\n⚠️ ".join(errores) + "\n\n" + texto(prop), "pendiente")
    faltan = [str(it["n"]) for it in prop["items"] if it["clase"] in ("consumo", "usd", "cargo")
              and not it["motivo"] and not it.get("descartado")]
    if aceptar and faltan:
        return conc.Resultado(f"Me falta la categoría de: {', '.join(faltan)}. Contestá "
                              f"*{faltan[0]} compras* (o *{faltan[0]} no*).", "pendiente")
    if aceptar and prop["cotizacion"] is None and any(
            it["clase"] == "usd" and not it.get("descartado") for it in prop["items"]):
        return conc.Resultado("Me falta el dólar para los consumos en dólares: contestá "
                              "*dolar 1540*.", "pendiente")
    if not aceptar or dudosa:
        aviso = "Revisá y contestá *ok*.\n\n" if (aceptar and dudosa) else ""
        return conc.Resultado(aviso + texto(prop), "pendiente")
    aplicar(conn, lote.id, prop, user_id=user_id, wid=wid, ahora=ahora)
    vivos = [it for it in prop["items"] if not it.get("descartado")]
    cargados = sum(1 for it in vivos if it["clase"] != "coincide")
    emparejados = sum(1 for it in vivos if it["clase"] == "coincide")
    return conc.Resultado(
        f"✅ Desarmé el pago de {prop['tarjeta']}: cargué {cargados} gasto(s) con fecha "
        f"{date.fromisoformat(prop['fecha']):%d/%m}"
        + (f" y emparejé {emparejados} que ya tenías" if emparejados else "")
        + ".\n*deshacer* deja el pago otra vez esperando.", "lote")


def aplicar(conn: sqlite3.Connection, lote_id: int, prop: dict, *, user_id: int, wid: int,
            ahora: datetime) -> None:
    creado = ahora.isoformat()
    fecha = date.fromisoformat(prop["fecha"])
    fila_pago = prop["pagos"][0]
    existentes = conc._motivos(conn, wid)
    motivo_ajuste = conc.motivo_existente(conc.MOTIVO_AJUSTE, existentes) or conc.MOTIVO_AJUSTE
    motivo_percepcion = (conc.motivo_existente(conc.MOTIVO_PERCEPCION, existentes)
                         or conc.MOTIVO_PERCEPCION)
    motivo_venta = conc.motivo_existente(MOTIVO_VENTA, existentes) or MOTIVO_VENTA
    conc.asegurar_categoria(conn, motivo_percepcion, "Flujo Capital", user_id, wid)
    if any(it["clase"] == "usd" for it in prop["items"]):
        conc.asegurar_categoria(conn, motivo_venta, "Ingreso", user_id, wid)
    if any(it.get("arrastre") for it in prop["items"]):
        conc.asegurar_categoria(conn, motivo_ajuste, "Gasto Variable", user_id, wid)

    ops: list[Any] = [Actualizar("banco_filas", p, {"estado": "desarmada"}) for p in prop["pagos"]]
    ops.append(Actualizar("resumenes", prop["resumen_id"],
                          {"estado": "desarmado", "pagado": prop["pagado"]}))
    reglas: dict[str, str] = {}

    def cargar(clave: str, mov: Movimiento) -> None:
        ops.append(InsertarMovimiento(mov, clave=clave))
        ops.append(Insertar("emparejamientos", {
            "workspace_id": wid, "transaccion_id": Ref(clave), "banco_fila_id": fila_pago,
            "rol": "origen", "creado_en": creado}))

    for k, it in enumerate(prop["items"]):
        if it.get("descartado"):
            continue
        comentario = f"{prop['tarjeta']} · {it.get('referencia') or it.get('texto')}" + (
            f" · cuota {it['cuota']}" if it.get("cuota") else "")
        if it["clase"] == "coincide":
            if it.get("tarjeta_id"):
                ops.append(Actualizar("emparejamientos", it["tarjeta_id"],
                                      {"rol": "resumen", "banco_fila_id": fila_pago}))
            else:
                ops.append(Insertar("emparejamientos", {
                    "workspace_id": wid, "transaccion_id": it["txn"], "banco_fila_id": fila_pago,
                    "rol": "resumen", "creado_en": creado}))
            if it["correccion"]:
                ops.append(Actualizar("transacciones", it["txn"], {"pasivos": it["correccion"] / 100}))
            if it["arrastre"]:
                cargar(f"r{k}", Movimiento(fecha=fecha, motivo=motivo_ajuste,
                                           ingresos=-it["pesos"] / 100,
                                           comentario="Regla del corte: ya estaba en el ajuste inicial"))
        elif it["clase"] == "usd":
            pesos = _pesos_de(it, prop)
            cargar(f"g{k}", Movimiento(fecha=fecha, motivo=it["motivo"], pasivos=pesos / 100,
                                       comentario=f"{comentario} · {_usd(it['dolares'])}"))
            cargar(f"v{k}", Movimiento(fecha=fecha, motivo=motivo_venta, ingresos=pesos / 100,
                                       comentario=f"{comentario} · {_usd(it['dolares'])}"))
            reglas[it["comercio"]] = it["motivo"]
        else:
            cargar(f"g{k}", Movimiento(fecha=fecha, motivo=it["motivo"], pasivos=it["pesos"] / 100,
                                       comentario=comentario))
            if it["clase"] == "consumo":
                reglas[it["comercio"]] = it["motivo"]
    if prop["diferencia"]:
        cargar("percepcion", Movimiento(fecha=fecha, motivo=motivo_percepcion,
                                        pasivos=prop["diferencia"] / 100,
                                        comentario=f"{prop['tarjeta']} · lo pagado menos los "
                                                   "gastos reales"))
    tipo = f"TARJETA {prop['tarjeta']}"
    for comercio, motivo in reglas.items():
        previa = conn.execute("SELECT id, motivo FROM reglas_comercio WHERE workspace_id = ? AND "
                              "tipo = ? AND comercio = ?", (wid, tipo, comercio)).fetchone()
        if previa is None:
            ops.append(Insertar("reglas_comercio", {"workspace_id": wid, "tipo": tipo,
                                                    "comercio": comercio, "motivo": motivo}))
        elif previa["motivo"] != motivo:
            ops.append(Actualizar("reglas_comercio", previa["id"], {"motivo": motivo}))
    lotes.aplicar_operaciones(conn, lote_id, ops, user_id=user_id, ahora=ahora)
