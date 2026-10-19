"""FIMA, efectivo y el ajuste (Fase D, paso 4b, ADR-0009 §5).

Franco declara cuánto tiene: ``fima 512.300 efectivo 98.000`` (con fecha
opcional adelante). El Secretario calcula cuánto **esperaba** y, si no
coincide, **prevalece lo de Franco** y propone el ajuste. Como todo, es un
lote: no se escribe nada hasta el `ok`, y `deshacer` lo revierte.

* **FIMA** esperado = el último declarado + suscripciones − rescates del
  banco. La diferencia es **Ingreso "Rendimiento FIMA"** (puede ser negativa).
* **Efectivo** esperado = el último declarado + extracciones − lo gastado en
  efectivo (por su **bruto**: si pagaste $150.000 y te devolvieron $125.000 por
  transferencia, del bolsillo salieron $150.000) + lo cobrado en efectivo. La
  diferencia va a **"Ajuste Reconciliación"**: un faltante como gasto
  (`pasivos`), un sobrante en `ingresos` (mueve el saldo sin contar como
  ingreso ni gasto del mes).

Qué cuenta en cada declaración (Franco, 19/10/2026: lo declarado incluye todo
lo que se movió hasta esa fecha):

* Del banco, los movimientos con fecha **después** de la declaración anterior
  y hasta esta.
* De lo cargado a mano, lo que es efectivo y **todavía no se contó**: lo que
  ya estaba marcado efectivo con fecha posterior a la declaración anterior (o
  marcado después de ella), y lo que nadie decidió todavía (se marca
  efectivo ahora). Lo que es tarjeta, o ya tiene su fila del banco, no.
* Si algo que se contó como efectivo apareció después en el banco (no era
  efectivo), se **devuelve** en la declaración siguiente.

Montos en centavos enteros, como el banco.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from places.finanzas.core import conciliacion as conc
from places.finanzas.core import lotes
from places.finanzas.core.lotes import Actualizar, Insertar, InsertarMovimiento, Movimiento, Ref

MOTIVO_RENDIMIENTO = "Rendimiento FIMA"
#: Si el último extracto quedó más viejo que esto, se avisa: lo que se movió
#: después en el banco todavía no se sabe.
DIAS_EXTRACTO_VIEJO = 3
#: Roles con los que un gasto ya no es efectivo "sin decidir".
_ROLES_NO_EFECTIVO = ("origen", "mismo", "arrastre", "tarjeta", "reversion", "anterior", "ajuste")

_RE_PARTE = re.compile(r"(fima|efectivo|efvo)\s*[:=]?\s*(\$?\s*[\d.,]+k?)", re.IGNORECASE)
_RE_RESTO = re.compile(r"^[\s,;y]*$", re.IGNORECASE)


def parsear(texto: str, hoy: date) -> Optional[tuple[date, dict[str, int]]]:
    """``[fecha,] fima 512.300 efectivo 98.000`` → (fecha, {parte: centavos}). None si no es eso."""
    from places.finanzas.core.comandos import _RE_FECHA_INICIO, _numero, parsear_fecha  # diferido

    resto = texto.strip()
    fecha = hoy
    if m := _RE_FECHA_INICIO.match(resto):
        if not _RE_PARTE.match(resto[m.end():].strip()):
            return None
        fecha = parsear_fecha(m.group(1), hoy)
        resto = resto[m.end():]
    if not _RE_PARTE.match(resto.strip()):
        return None
    partes: dict[str, int] = {}
    for nombre, monto in _RE_PARTE.findall(resto):
        parte = "efectivo" if nombre.lower() in ("efectivo", "efvo") else "fima"
        partes[parte] = round(_numero(monto) * 100)
    if not _RE_RESTO.match(_RE_PARTE.sub("", resto)):
        return None
    return fecha, partes


def _ultima(conn: sqlite3.Connection, wid: int, parte: str) -> Optional[dict]:
    r = conn.execute(
        "SELECT fecha, monto, declarado_en FROM saldos_declarados WHERE workspace_id = ? "
        "AND parte = ? ORDER BY fecha DESC, id DESC LIMIT 1", (wid, parte)).fetchone()
    return dict(r) if r else None


def _banco(conn: sqlite3.Connection, wid: int, tratamiento: str, desde: str, hasta: str) -> int:
    """Lo que entró a esa parte desde la caja, en centavos (un débito de la caja suma)."""
    r = conn.execute(
        "SELECT COALESCE(SUM(-monto), 0) FROM banco_filas WHERE workspace_id = ? "
        "AND tratamiento = ? AND fecha > ? AND fecha <= ?",
        (wid, tratamiento, desde, hasta)).fetchone()
    return int(r[0])


def _efectivo_a_contar(conn: sqlite3.Connection, wid: int, corte: date, desde: Optional[dict],
                       hasta: date) -> tuple[list[dict], list[int], list[dict]]:
    """(gastos en efectivo a contar, ids sin decidir a marcar, a devolver)."""
    filas = conn.execute(
        """
        SELECT t.id, t.fecha, t.pasivos, t.ingresos, t.motivo, gc.bruto
        FROM transacciones t LEFT JOIN gasto_cuentas gc ON gc.transaccion_id = t.id
        WHERE t.workspace_id = ? AND t.fecha >= ? AND t.fecha <= ?
        ORDER BY t.fecha, t.id
        """, (wid, corte.isoformat(), hasta.isoformat())).fetchall()
    roles: dict[int, list[dict]] = {}
    for e in conn.execute("SELECT id, transaccion_id, rol, creado_en, era_efectivo "
                          "FROM emparejamientos WHERE workspace_id = ?", (wid,)):
        roles.setdefault(e["transaccion_id"], []).append(dict(e))
    pares = _pares_venta_divisa(filas)
    contar, marcar = [], []
    for t in filas:
        if conc._norm(t["motivo"]) in conc._MOTIVOS_DEL_SECRETARIO | {"pago tarjeta"}:
            continue
        if t["id"] in pares or not (t["pasivos"] or t["ingresos"]):
            continue
        suyos = roles.get(t["id"], [])
        if any(e["rol"] in _ROLES_NO_EFECTIVO for e in suyos):
            continue
        efectivo = next((e for e in suyos if e["rol"] == "efectivo"), None)
        if efectivo is None:
            marcar.append(t["id"])
        elif desde is not None and not (
                t["fecha"] > desde["fecha"]
                or datetime.fromisoformat(efectivo["creado_en"])
                > datetime.fromisoformat(desde["declarado_en"])):
            continue    # ya se contó en una declaración anterior
        sale = (round(t["bruto"] * 100) if t["bruto"] is not None and t["pasivos"] > 0
                else round(t["pasivos"] * 100))
        contar.append({"id": t["id"], "fecha": t["fecha"], "motivo": t["motivo"],
                       "neto": round(t["ingresos"] * 100) - sale})
    devolver = []
    if desde is not None:
        for e in conn.execute(
                """
                SELECT e.id, t.pasivos, gc.bruto FROM emparejamientos e
                JOIN transacciones t ON t.id = e.transaccion_id
                LEFT JOIN gasto_cuentas gc ON gc.transaccion_id = t.id
                WHERE e.workspace_id = ? AND e.era_efectivo = 1 AND t.fecha <= ?
                """, (wid, desde["fecha"])):
            sale = round((e["bruto"] if e["bruto"] is not None else e["pasivos"]) * 100)
            devolver.append({"emparejamiento": e["id"], "monto": sale})
    return contar, marcar, devolver


def _pares_venta_divisa(filas) -> set[int]:
    pares: set[int] = set()
    for v in filas:
        if conc._norm(v["motivo"]) != "venta divisa" or not v["ingresos"]:
            continue
        g = next((t for t in filas if t["id"] not in pares and t["id"] != v["id"]
                  and t["fecha"] == v["fecha"] and t["pasivos"] > 0
                  and abs(round(t["pasivos"] * 100) - round(v["ingresos"] * 100)) <= 1), None)
        if g:
            pares.update({v["id"], g["id"]})
    return pares


def proponer(conn: sqlite3.Connection, *, user_id: int, wid: int, fecha: date,
             partes: dict[str, int], ahora: datetime) -> dict:
    corte = conc.corte(conn, user_id, wid)
    prop: dict = {"tipo": "saldos", "fecha": fecha.isoformat(), "partes": [], "marcar": [],
                  "devolver": [], "aviso": None}
    ultima_fila = conn.execute("SELECT MAX(fecha) FROM banco_filas WHERE workspace_id = ?",
                               (wid,)).fetchone()[0]
    if ultima_fila and date.fromisoformat(ultima_fila) < fecha - timedelta(days=DIAS_EXTRACTO_VIEJO):
        prop["aviso"] = (f"El último extracto que tengo llega hasta el "
                         f"{date.fromisoformat(ultima_fila):%d/%m}: si después moviste el FIMA o "
                         "sacaste del cajero, todavía no lo sé y el ajuste va a salir corrido. Lo "
                         "mejor es mandarme el extracto del día y después los saldos.")
    for parte in ("fima", "efectivo"):
        if parte not in partes:
            continue
        previa = _ultima(conn, wid, parte)
        if previa and previa["fecha"] > fecha.isoformat():
            raise conc.ConciliacionInvalida(
                f"Ya tengo un saldo de {parte} del {date.fromisoformat(previa['fecha']):%d/%m}, "
                f"posterior a esta fecha.")
        p = {"parte": parte, "declarado": partes[parte], "previa": previa}
        if parte == "fima" and previa:
            p["movimientos"] = _banco(conn, wid, "fima", previa["fecha"], fecha.isoformat())
            p["esperado"] = previa["monto"] + p["movimientos"]
        if parte == "efectivo":
            contar, marcar, devolver = _efectivo_a_contar(conn, wid, corte, previa, fecha)
            prop["marcar"] = marcar
            if previa:
                p["extracciones"] = _banco(conn, wid, "extraccion", previa["fecha"],
                                           fecha.isoformat())
                p["en_efectivo"] = sum(c["neto"] for c in contar)
                p["cantidad"] = len(contar)
                p["devuelto"] = sum(d["monto"] for d in devolver)
                prop["devolver"] = [d["emparejamiento"] for d in devolver]
                p["esperado"] = (previa["monto"] + p["extracciones"] + p["en_efectivo"]
                                 + p["devuelto"])
        if "esperado" in p:
            p["diferencia"] = p["declarado"] - p["esperado"]
        prop["partes"].append(p)
    return prop


def texto(prop: dict) -> str:
    f = date.fromisoformat(prop["fecha"])
    lineas = [f"💰 Saldos al {f:%d/%m}:"]
    for p in prop["partes"]:
        nombre = "FIMA" if p["parte"] == "fima" else "Efectivo"
        previa = p["previa"]
        if previa is None:
            lineas.append(f"{nombre}: {conc.pesos_c(p['declarado'])}. Es el primero que me "
                          "decís: lo guardo como punto de partida.")
            continue
        desde = f"{conc.pesos_c(previa['monto'])} ({date.fromisoformat(previa['fecha']):%d/%m})"
        if p["parte"] == "fima":
            lineas.append(f"{nombre}: tenías {desde}, {_mas(p['movimientos'])} de suscripciones "
                          f"y rescates del banco → esperaba {conc.pesos_c(p['esperado'])}.")
        else:
            linea = (f"{nombre}: tenías {desde}, {_mas(p['extracciones'])} de extracciones, "
                     f"{_mas(p['en_efectivo'])} de {p['cantidad']} movimiento(s) en efectivo")
            if p["devuelto"]:
                linea += f", {_mas(p['devuelto'])} de lo que conté como efectivo y no lo era"
            lineas.append(linea + f" → esperaba {conc.pesos_c(p['esperado'])}.")
        d = p["diferencia"]
        if abs(d) <= 1:
            lineas.append(f"   Me decís {conc.pesos_c(p['declarado'])}: coincide ✔")
        elif p["parte"] == "fima":
            lineas.append(f"   Me decís {conc.pesos_c(p['declarado'])} → {_mas(d)} de "
                          f"{MOTIVO_RENDIMIENTO}.")
        elif d < 0:
            lineas.append(f"   Me decís {conc.pesos_c(p['declarado'])} → faltan "
                          f"{conc.pesos_c(-d)}: los cargo como gasto en {conc.MOTIVO_AJUSTE}.")
        else:
            lineas.append(f"   Me decís {conc.pesos_c(p['declarado'])} → sobran "
                          f"{conc.pesos_c(d)}: van a {conc.MOTIVO_AJUSTE} (no cuentan como "
                          "ingreso).")
    if prop.get("aviso"):
        lineas.append(f"\n⚠️ {prop['aviso']}")
    lineas.append("\n¿Va? Contestá *ok* o *cancelar*.")
    return "\n".join(lineas)


def _mas(c: int) -> str:
    return ("+" if c >= 0 else "-") + conc.pesos_c(abs(c))


def aplicar(conn: sqlite3.Connection, lote_id: int, prop: dict, *, user_id: int, wid: int,
            ahora: datetime) -> None:
    creado = ahora.isoformat()
    fecha = date.fromisoformat(prop["fecha"])
    existentes = conc._motivos(conn, wid)
    motivo_ajuste = conc.motivo_existente(conc.MOTIVO_AJUSTE, existentes) or conc.MOTIVO_AJUSTE
    motivo_rend = conc.motivo_existente(MOTIVO_RENDIMIENTO, existentes) or MOTIVO_RENDIMIENTO
    ops: list = []
    for k, p in enumerate(prop["partes"]):
        ops.append(Insertar("saldos_declarados", {
            "workspace_id": wid, "parte": p["parte"], "fecha": prop["fecha"],
            "monto": p["declarado"], "declarado_en": creado}))
        d = p.get("diferencia")
        if d is None or abs(d) <= 1:
            continue
        if p["parte"] == "fima":
            conc.asegurar_categoria(conn, motivo_rend, "Ingreso", user_id, wid)
            mov = Movimiento(fecha=fecha, motivo=motivo_rend, ingresos=d / 100,
                             comentario="FIMA declarado contra el esperado")
        else:
            conc.asegurar_categoria(conn, motivo_ajuste, "Gasto Variable", user_id, wid)
            mov = Movimiento(fecha=fecha, motivo=motivo_ajuste,
                             pasivos=-d / 100 if d < 0 else 0.0,
                             ingresos=d / 100 if d > 0 else 0.0,
                             comentario="Efectivo declarado contra el esperado")
        ops.append(InsertarMovimiento(mov, clave=f"a{k}"))
        ops.append(Insertar("emparejamientos", {
            "workspace_id": wid, "transaccion_id": Ref(f"a{k}"), "banco_fila_id": None,
            "rol": "ajuste", "creado_en": creado}))
    for tid in prop["marcar"]:
        ops.append(Insertar("emparejamientos", {
            "workspace_id": wid, "transaccion_id": tid, "banco_fila_id": None,
            "rol": "efectivo", "creado_en": creado}))
    for eid in prop["devolver"]:
        ops.append(Actualizar("emparejamientos", eid, {"era_efectivo": 2}))
    lotes.aplicar_operaciones(conn, lote_id, ops, user_id=user_id, ahora=ahora)


def control_total(conn: sqlite3.Connection, *, user_id: int, wid: int) -> Optional[str]:
    """¿Saldo de la app = caja + FIMA + efectivo? None si todavía no hay con qué comparar."""
    from places.finanzas.core.metrics import saldo_cuenta_corriente

    caja = conn.execute("SELECT fecha, saldo FROM banco_filas WHERE workspace_id = ? "
                        "ORDER BY orden DESC LIMIT 1", (wid,)).fetchone()
    if caja is None:
        caja = conn.execute("SELECT fecha, monto AS saldo FROM saldos_declarados WHERE "
                            "workspace_id = ? AND parte = 'caja' ORDER BY id DESC LIMIT 1",
                            (wid,)).fetchone()
    fima, efectivo = _ultima(conn, wid, "fima"), _ultima(conn, wid, "efectivo")
    if caja is None or fima is None or efectivo is None:
        return None
    app = round(saldo_cuenta_corriente(conn, user_id=user_id) * 100)
    real = caja["saldo"] + fima["monto"] + efectivo["monto"]
    esperando = -int(conn.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM banco_filas WHERE workspace_id = ? "
        "AND estado = 'esperando_resumen'", (wid,)).fetchone()[0])
    tarjeta = round(float(conn.execute(
        "SELECT COALESCE(SUM(t.pasivos), 0) FROM emparejamientos e JOIN transacciones t "
        "ON t.id = e.transaccion_id WHERE e.workspace_id = ? AND e.rol = 'tarjeta'",
        (wid,)).fetchone()[0]) * 100)
    resto = app - real - esperando + tarjeta
    lineas = [f"🧮 Saldo de la app {conc.pesos_c(app)} · caja "
              f"{conc.pesos_c(caja['saldo'])} ({date.fromisoformat(caja['fecha']):%d/%m}) + FIMA "
              f"{conc.pesos_c(fima['monto'])} + efectivo {conc.pesos_c(efectivo['monto'])} = "
              f"{conc.pesos_c(real)}."]
    if esperando:
        lineas.append(f"   {conc.pesos_c(esperando)} son pagos de tarjeta esperando su resumen.")
    if tarjeta:
        lineas.append(f"   {conc.pesos_c(tarjeta)} son gastos con tarjeta que todavía no pagaste.")
    if abs(resto) <= 100:
        lineas.append("   Cierra ✔")
    else:
        lineas.append(f"   No cierra por {conc.pesos_c(abs(resto))}: puede ser algo que todavía "
                      "no pasó por el banco (o un extracto que me falta).")
    return "\n".join(lineas)
