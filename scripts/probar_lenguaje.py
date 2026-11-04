"""¿Gemini traduce bien lo que escribe Franco? (Fase E, paso 2, ADR-0012). No toca la base real.

Pasa ~50 frases (las reales del 2/11 y las de todos los días) por el mismo
`procesar` del Secretario, con Gemini de verdad, sobre una base **temporal**
con las categorías de Franco y, para las de la conciliación, un extracto como
el del 2/11 (nombres inventados). Por cada frase dice:

* **BIEN**: entendió lo que Franco quiso (o repreguntó cuando tenía que).
* **DUDOSA**: no cargaría nada mal, pero no entendió del todo (repreguntó de
  más, se le escapó una corrección, propuso una categoría nueva).
* **MAL**: con el *sí* cargaría algo distinto de lo que Franco quiso. La meta
  antes de prenderlo (`LENGUAJE_NATURAL=1`) es **cero MAL**.
* **FALLA**: Gemini no contestó (con el motivo de Google). Antes de las frases
  va un pedido de prueba: si falla, se dice por qué y no se sigue.

Necesita `GEMINI_API_KEY`. En la PC (PowerShell) o dentro de Fly:

    .venv\\Scripts\\python.exe scripts\\probar_lenguaje.py
    fly ssh console -a superapp-finanzas -C "python /app/scripts/probar_lenguaje.py"

Va despacio a propósito (15 pedidos por minuto en el plan gratis, verificado
en AI Studio el 4/11/2026): unos 4 minutos.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#: Las categorías de Franco (backup del 3/11/2026) y su grupo.
CATEGORIAS = [
    ("Ajuste Reconciliación", "Gasto Variable"), ("Auto", "Gasto Fijo"),
    ("Compra Divisa", "Inversion"), ("Compras", "Gasto Variable"), ("Expensas", "Gasto Fijo"),
    ("Haberes Fundación", "Ingreso"), ("Haberes SBT", "Ingreso"), ("Haberes UCEMA", "Ingreso"),
    ("Impuestos", "Gasto Fijo"), ("Inversiones", "Inversion"), ("Otros ingresos", "Ingreso"),
    ("Pago tarjeta", "Gasto Variable"), ("Retiro Inversiones", "Ingreso"),
    ("Salidas", "Gasto Variable"), ("Servicios", "Gasto Fijo"), ("Transportes", "Gasto Variable"),
    ("Venta divisa", "Ingreso"), ("Viajes", "Gasto Variable"),
]

#: El extracto del 2/11, con nombres inventados: (fecha, tipo, comercio, pesos).
EXTRACTO = [
    (date(2026, 10, 16), "COMPRA DEBITO", "KIOSCO DEL ANCLA", -100.00),
    (date(2026, 10, 21), "TRANSFERENCIA DE TERCEROS", "AMIGO INVENTADO", 10000.00),
    (date(2026, 10, 22), "INTERES CAPITALIZADO", None, 3.47),
    (date(2026, 10, 26), "TRANSFERENCIA A TERCEROS", "PROFE INVENTADO", -23800.00),
    (date(2026, 10, 28), "TRANSFERENCIA A TERCEROS", "MECANICO INVENTADO", -81070.00),
    (date(2026, 10, 28), "TRANSFERENCIAS CASH SUELDOS", "UNIVERSIDAD INVENTADA", 404625.00),
    (date(2026, 10, 30), "TRANSFERENCIA DE TERCEROS", "FUNDACION INVENTADA", 2410000.00),
    (date(2026, 10, 30), "DEP.EFVO.AUTOSERVICIO TICKET:", None, 1350000.00),
    (date(2026, 10, 31), "COMPRA DEBITO", "FERRETERIA INVENTADA", -41200.00),
]


# ---------------------------------------------------------------- los casos

@dataclass
class Caso:
    mensaje: str
    #: "suelto" (nada abierto) o "extracto" (la conciliación del 2/11 abierta).
    escenario: str = "suelto"
    #: Gastos: [(días antes de hoy o fecha, monto, {categorías válidas}, ingreso)].
    gastos: list = field(default_factory=list)
    #: Correcciones a la propuesta: {comercio o número: {categorías} | "no"}.
    correcciones: dict = field(default_factory=dict)
    ok: Optional[bool] = None          # si la orden tiene que aceptar la propuesta
    cancelar: bool = False
    consulta: Optional[str] = None     # "resumen", "agenda"
    orden_exacta: Optional[str] = None  # deshacer, evento:, fima…: se compara normalizada
    #: Tiene que repreguntar o no hacer nada (falta un dato, no es para el bot).
    no_escribe: bool = False
    #: Lo puede resolver el parser solo, sin Gemini (también vale).
    parser: bool = False


def _lunes_pasado(hoy: date) -> date:
    return hoy - timedelta(days=hoy.weekday() or 7)


CASOS: list[Caso] = [
    # -- gastos sueltos, como habla Franco
    Caso("ayer gasté 5 lucas en el chino", gastos=[(1, 5000, {"Compras"}, False)]),
    Caso("pagué 12 mil de luz", gastos=[(0, 12000, {"Servicios"}, False)]),
    Caso("gaste 3500 en nafta", gastos=[(0, 3500, {"Auto"}, False)]),
    Caso("nafta 20k", gastos=[(0, 20000, {"Auto"}, False)]),
    Caso("le transferí 15.000 a juan por el asado", gastos=[(0, 15000, {"Salidas"}, False)]),
    Caso("cobré el sueldo de ucema 404.625", gastos=[(0, 404625, {"Haberes UCEMA"}, True)]),
    Caso("super 8.500 ayer", gastos=[(1, 8500, {"Compras"}, False)]),
    Caso("5000 en el chino", gastos=[(0, 5000, {"Compras"}, False)]),
    Caso("20000 nafta con la visa", gastos=[(0, 20000, {"Auto"}, False)]),
    Caso("ayer 3000 uber al centro", gastos=[(1, 3000, {"Transportes"}, False)]),
    Caso("1500 cafe con ana", gastos=[(0, 1500, {"Salidas"}, False)]),
    Caso("3 cafes 4500", gastos=[(0, 4500, {"Salidas"}, False)]),
    Caso("expensas de octubre 185 mil", gastos=[(0, 185000, {"Expensas"}, False)]),
    Caso("taxi 7800", gastos=[(0, 7800, {"Transportes"}, False)]),
    Caso("me cobraron 2 lucas de comisión en el banco",
         gastos=[(0, 2000, {"Impuestos", "Servicios"}, False)]),
    Caso("almuerzo con bobby 32.000", gastos=[(0, 32000, {"Salidas"}, False)]),
    Caso("pagué el seguro del auto 60 mil el lunes",
         gastos=[("lunes", 60000, {"Auto"}, False)]),
    Caso("compré dólares por 1.200.000", gastos=[(0, 1200000, {"Compra Divisa"}, False)]),
    Caso("nafta 20k y peaje 1500",
         gastos=[(0, 20000, {"Auto"}, False), (0, 1500, {"Auto", "Transportes"}, False)]),
    Caso("ayer: super 8500, farmacia 4200",
         gastos=[(1, 8500, {"Compras"}, False), (1, 4200, {"Compras"}, False)]),
    Caso("cobré 1.350.000 de SBT en efectivo", gastos=[(0, 1350000, {"Haberes SBT"}, True)]),
    Caso("viaje a córdoba, pasajes 180 lucas", gastos=[(0, 180000, {"Viajes"}, False)]),
    # -- sin datos suficientes o que no son para el bot: no puede escribir nada
    Caso("fui al chino", no_escribe=True),
    Caso("gasté un montón en el super", no_escribe=True),
    Caso("hola", no_escribe=True),
    Caso("gracias!", no_escribe=True),
    Caso("comprame acciones de YPF", no_escribe=True),
    # -- consultas y comandos
    Caso("cuánto llevo gastado este mes?", consulta="resumen"),
    Caso("qué tengo esta semana?", consulta="agenda"),
    Caso("borrá lo último que cargué", orden_exacta="deshacer"),
    Caso("fima: 3749755,32 efectivo 60000 caja 207.287,49",
         orden_exacta="fima 3749755,32 efectivo 60000"),
    Caso("tengo 3,7 palos en el fima y 60 lucas en efectivo",
         orden_exacta="fima 3700000 efectivo 60000"),
    # -- la conciliación abierta (el extracto del 2/11)
    Caso("1. Compras\n2. Ok\n3. Compras\n4. Compras\n5. Haberes UCEMA", "extracto",
         parser=True),
    Caso("va", "extracto", ok=True, parser=True),
    Caso("el del mecánico ponelo en auto", "extracto",
         correcciones={"MECANICO INVENTADO": {"Auto"}}),
    Caso("la ferretería es compras y el profe salidas", "extracto",
         correcciones={"FERRETERIA INVENTADA": {"Compras"}, "PROFE INVENTADO": {"Salidas"}}),
    Caso("lo de la universidad es haberes ucema y lo de la fundación haberes fundación",
         "extracto", correcciones={"UNIVERSIDAD INVENTADA": {"Haberes UCEMA"},
                                   "FUNDACION INVENTADA": {"Haberes Fundación"}}),
    Caso("el de 81 mil es un service del auto", "extracto",
         correcciones={"MECANICO INVENTADO": {"Auto"}}),
    Caso("lo de amigo inventado no lo cargues", "extracto",
         correcciones={"AMIGO INVENTADO": "no"}),
    Caso("la ferretería no era compras, era auto", "extracto",
         correcciones={"FERRETERIA INVENTADA": {"Auto"}}),
    Caso("el profe es salidas, el mecánico auto y el resto como dijiste, dale", "extracto",
         correcciones={"PROFE INVENTADO": {"Salidas"}, "MECANICO INVENTADO": {"Auto"}}, ok=True),
    Caso("cancelá todo", "extracto", cancelar=True),
    Caso("qué es el 2?", "extracto", no_escribe=True),
    Caso("por qué el depósito dice haberes sbt?", "extracto", no_escribe=True),
    Caso("el 9 es salidas", "extracto", no_escribe=True),
    Caso("agregá el café de 1500", "extracto", gastos=[(0, 1500, {"Salidas"}, False)]),
]


# ---------------------------------------------------------------- la base temporal

def _base(carpeta: Path, escenario: str, ahora: datetime) -> Path:
    """Una base nueva con las categorías de Franco (y el extracto abierto, si va)."""
    import core.db as core_db
    from core.context import set_current_workspace_id
    from core.workspaces import resolve_workspace_id
    from places.finanzas.core import conciliacion, lotes
    from places.finanzas.core.extracto_galicia import Extracto, FilaBanco
    from places.finanzas.core.transactions import insert_transaction

    ruta = carpeta / f"{escenario}.db"
    os.environ["DB_PATH"] = str(ruta)          # backup_db y compañía, nunca la base real
    core_db.BACKUP_DIR = carpeta / "backups"
    core_db.init_db(ruta)
    conn = core_db.connect(ruta)
    conn.execute("INSERT OR IGNORE INTO usuarios (id, username, fullname) "
                 "VALUES (1, 'franco', 'Franco')")
    set_current_workspace_id(None)
    for motivo, grupo in CATEGORIAS:
        insert_transaction(conn, fecha=date(2026, 9, 1), motivo=motivo, pasivos=1, user_id=1)
        conn.execute("UPDATE categorias SET grupo = ? WHERE motivo = ?", (grupo, motivo))
    conn.execute("DELETE FROM transacciones")
    if escenario == "extracto":
        txn = insert_transaction(conn, fecha=date(2026, 10, 18), motivo="Ajuste Reconciliación",
                                 ingresos=82758.25, user_id=1)
        conn.execute("UPDATE transacciones SET creado_en = '2026-10-18 21:00:00' WHERE id = ?",
                     (txn,))
        saldo, filas = 15326301, []
        for fecha, tipo, comercio, pesos in EXTRACTO:
            monto = round(pesos * 100)
            saldo += monto
            filas.append(FilaBanco(fecha=fecha, monto=monto, saldo=saldo, tipo=tipo,
                                   comercio=comercio))
        wid = resolve_workspace_id(conn, 1)
        prop = conciliacion.proponer_extracto(conn, Extracto(tuple(filas)), user_id=1, wid=wid,
                                              ahora=ahora)
        lotes.proponer(conn, workspace_id=wid, user_id=1, origen="extracto", propuesta=prop,
                       ahora=ahora)
    conn.commit()
    conn.close()
    return ruta


def _numeros_por_comercio(conn) -> dict[str, int]:
    from core.workspaces import resolve_workspace_id
    from places.finanzas.core import lotes

    lote = lotes.vigente(conn, workspace_id=resolve_workspace_id(conn, 1),
                         ahora=datetime.now(_zona()))
    if lote is None:
        return {}
    filas = lote.propuesta.get("filas", [])
    return {filas[it["fila"]].get("comercio") or filas[it["fila"]]["tipo"]: it["n"]
            for it in lote.propuesta["items"] if it.get("n") and "fila" in it}


def _zona():
    from places.finanzas.core.comandos import ZONA
    return ZONA


# ---------------------------------------------------------------- evaluar

@dataclass
class Resultado:
    nota: str        # BIEN | DUDOSA | MAL
    detalle: str
    gemini: str      # lo que devolvió Gemini (o "—" si no hizo falta)
    respuesta: str   # la primera línea de lo que contestaría el Secretario


def _fecha_esperada(dias: Any, hoy: date) -> date:
    return _lunes_pasado(hoy) if dias == "lunes" else hoy - timedelta(days=dias)


def evaluar(caso: Caso, traduccion: Any, respuesta: Any, *, hoy: date, cantidad: int,
            numeros: dict[str, int], motivos: list[str]) -> tuple[str, str]:
    """(nota, detalle) de una traducción. `traduccion` es None si el parser lo resolvió solo."""
    from places.finanzas.core.comandos import (
        EntradaInvalida, _leer_respuesta_lote, normalizar, parsear_gasto, resolver_categoria)
    from places.finanzas.core.lenguaje import clasificar

    if traduccion is None:
        if caso.parser:
            return "BIEN", "lo entendió el parser solo"
        if respuesta.resultado == "cargado" and caso.gastos:
            return "BIEN", "lo entendió el parser solo"
        return "DUDOSA", f"no consultó a Gemini (respuesta: {respuesta.resultado})"

    escribe = traduccion.tipo == "orden" and clasificar(
        traduccion.orden, hoy=hoy, cantidad=cantidad) not in (None, "consulta")
    if caso.no_escribe:
        return ("MAL", f"escribiría «{traduccion.orden}»") if escribe else \
            ("BIEN", f"{traduccion.tipo}")
    if traduccion.tipo != "orden":
        return "DUDOSA", f"{traduccion.tipo}: {traduccion.texto[:60]}"
    orden = traduccion.orden

    if caso.consulta:
        return ("BIEN", "") if normalizar(orden) == caso.consulta else (
            "MAL" if escribe else "DUDOSA", f"esperaba «{caso.consulta}»")
    if caso.orden_exacta:
        if caso.orden_exacta.startswith("fima"):
            from places.finanzas.core import saldos
            try:
                if saldos.parsear(orden, hoy) == saldos.parsear(caso.orden_exacta, hoy):
                    return "BIEN", ""
            except EntradaInvalida:
                pass
            return "MAL", f"esperaba «{caso.orden_exacta}»"
        return ("BIEN", "") if normalizar(orden) == normalizar(caso.orden_exacta) else (
            "MAL" if escribe else "DUDOSA", f"esperaba «{caso.orden_exacta}»")

    if caso.gastos:
        renglones = [r for r in orden.splitlines() if r.strip()]
        if clasificar(orden, hoy=hoy, cantidad=cantidad) is None:
            return "DUDOSA", "el bot no la entiende: no cargaría nada"
        if len(renglones) != len(caso.gastos):
            return "MAL", f"{len(renglones)} gastos, esperaba {len(caso.gastos)}"
        notas = []
        for renglon, (dias, monto, cats, ingreso) in zip(renglones, caso.gastos):
            try:
                g = parsear_gasto(renglon, hoy)
            except EntradaInvalida as e:
                return "DUDOSA", f"«{renglon}»: {e}"
            if (g.fecha, round(g.monto, 2), g.es_ingreso) != (
                    _fecha_esperada(dias, hoy), monto, ingreso):
                return "MAL", (f"«{renglon}»: {g.fecha:%d/%m} ${g.monto:,.0f}"
                               f"{' ingreso' if g.es_ingreso else ''}")
            tipo, nombre = resolver_categoria(g.categoria, motivos)
            if tipo == "nueva" or nombre not in cats:
                notas.append(f"categoría «{nombre or g.categoria}» (esperaba {'/'.join(cats)})")
        return ("DUDOSA", "; ".join(notas)) if notas else ("BIEN", "")

    # Correcciones a la propuesta
    r = _leer_respuesta_lote(orden, cantidad)
    if r is None:
        return ("MAL", f"escribiría «{orden}»") if escribe else (
            "DUDOSA", "no es una respuesta a la propuesta")
    if caso.cancelar:
        return ("BIEN", "") if r.cancelar else ("MAL", "esperaba cancelar")
    if r.cancelar:
        return "MAL", "cancelaría la propuesta"
    esperado = {numeros.get(k, k): v for k, v in caso.correcciones.items()}
    obtenido = {}
    for n, que in r.correcciones:
        if normalizar(que) in {"no", "sacar", "interno"}:
            obtenido[n] = "no"
        else:
            obtenido[n] = resolver_categoria(que, motivos)[1] or que
    sobran = [n for n in obtenido if n not in esperado]
    distintas = [n for n in esperado if n in obtenido and (
        obtenido[n] != esperado[n] if esperado[n] == "no" else obtenido[n] not in esperado[n])]
    if sobran or distintas:
        return "MAL", f"correcciones {obtenido}, esperaba {esperado}"
    if r.aceptar and not caso.ok:
        return "MAL", "agrega un ok que Franco no dijo"
    faltan = [n for n in esperado if n not in obtenido]
    if faltan or (caso.ok and not r.aceptar):
        return "DUDOSA", f"le faltó {faltan or 'el ok'}"
    return "BIEN", ""


# ---------------------------------------------------------------- correr

class Grabador:
    """Envuelve al traductor real para guardar qué contestó o en qué falló (y respetar
    el límite). Sin el error, una frase en la que Gemini falló parecía "no consultó"."""

    def __init__(self, real: Any, pausa: float):
        self.real, self.pausa, self.ultima, self.error = real, pausa, None, None

    def traducir(self, mensaje: str, contexto: str):
        from core.api.gemini import GeminiNoDisponible

        try:
            self.ultima = self.real.traducir(mensaje, contexto)
        except GeminiNoDisponible as e:
            self.error = str(e)
            raise
        finally:
            time.sleep(self.pausa)
        return self.ultima


def correr(traductor: Any, casos: list[Caso] = CASOS, *, pausa: float = 4.5,
           salida: Callable[[str], None] = print) -> list[Resultado]:
    import core.db as core_db
    from places.finanzas.core.comandos import procesar
    from places.finanzas.core.transactions import all_motivos

    ahora = datetime.now(_zona())
    hoy = ahora.date()
    resultados = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        carpeta = Path(tmp)
        bases = {e: _base(carpeta, e, ahora) for e in {c.escenario for c in casos}}
        for i, caso in enumerate(casos, 1):
            ruta = carpeta / f"caso{i}.db"
            # Con la API de backup de SQLite: un `shutil.copy` deja afuera lo que está en el WAL.
            origen, destino = sqlite3.connect(bases[caso.escenario]), sqlite3.connect(ruta)
            origen.backup(destino)
            origen.close()
            destino.close()
            os.environ["DB_PATH"] = str(ruta)
            conn = core_db.connect(ruta)
            try:
                from places.finanzas.core.comandos import _cantidad
                from places.finanzas.core import lotes
                from core.workspaces import resolve_workspace_id
                lote = lotes.vigente(conn, workspace_id=resolve_workspace_id(conn, 1), ahora=ahora)
                cantidad = _cantidad(lote.propuesta) if lote else 0
                numeros = _numeros_por_comercio(conn)
                motivos = all_motivos(conn, user_id=1)
                grabador = Grabador(traductor, pausa)
                r = procesar(conn, caso.mensaje, user_id=1, ahora=ahora, traductor=grabador)
                t = grabador.ultima
                if grabador.error:
                    nota, detalle = "FALLA", f"Gemini: {grabador.error}"
                else:
                    nota, detalle = evaluar(caso, t, r, hoy=hoy, cantidad=cantidad,
                                            numeros=numeros, motivos=motivos)
            except Exception as e:  # noqa: BLE001 — una falla no corta la prueba: se muestra
                t, r = None, None
                nota, detalle = "FALLA", f"{type(e).__name__}: {e}"
            finally:
                conn.rollback()
                conn.close()
            gem = "—" if t is None else (t.orden.replace("\n", " / ") if t.tipo == "orden"
                                         else f"[{t.tipo}] {t.texto}")
            res = Resultado(nota, detalle, gem, (r.texto.splitlines()[0] if r else ""))
            resultados.append(res)
            salida(f"{nota:6} {caso.mensaje.splitlines()[0][:48]!r:52} → {gem[:70]}"
                   + (f"  ({detalle})" if detalle else ""))
    cuenta = {n: sum(r.nota == n for r in resultados)
              for n in ("BIEN", "DUDOSA", "MAL", "FALLA")}
    salida(f"\n{cuenta['BIEN']} BIEN · {cuenta['DUDOSA']} DUDOSA · {cuenta['MAL']} MAL · "
           f"{cuenta['FALLA']} FALLA de {len(resultados)}")
    return resultados


def main() -> int:
    from core.api.gemini import ClienteGemini, GeminiNoDisponible

    cliente = ClienteGemini.desde_entorno()
    if cliente is None:
        print("Falta GEMINI_API_KEY.")
        return 2
    # Un pedido de prueba antes de las 46: si Gemini no contesta, se dice por qué y se corta.
    try:
        prueba = cliente.traducir("nafta 20k", "Hoy: prueba de conexión.")
    except GeminiNoDisponible as e:
        print(f"Gemini no contesta (modelo {cliente.modelo}): {e}")
        return 2
    print(f"Gemini contesta (modelo {cliente.modelo}): {prueba}\n")
    time.sleep(4.5)
    resultados = correr(cliente)
    return 1 if any(r.nota in ("MAL", "FALLA") for r in resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
