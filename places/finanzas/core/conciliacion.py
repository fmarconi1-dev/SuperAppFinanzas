"""Conciliación con el extracto de la caja de ahorro (Fase D, paso 4, ADR-0009).

Franco manda el extracto de Galicia; esto lo compara con lo cargado y arma
una **propuesta** (un lote): qué coincide, qué falta, qué sobra y qué no
coincide. **No escribe nada hasta el `ok`.** Todo es determinístico (ADR-0006
§6: la IA nunca decide plata).

Las reglas, en el orden en que se aplican:

1. **Empalme.** El extracto tiene que seguir donde terminó el anterior (la
   cadena de saldos). Si no, hay un hueco y no se propone nada. La primera vez,
   el último movimiento anterior al corte (17/10/2026) es el ancla.
2. **Clasificación por tipo** (la primera línea del movimiento): gasto,
   ingreso, interno (FIMA, cajero), pago de tarjeta (espera su resumen),
   dólares, inversiones, percepción del 30% (línea neutra), transferencias
   propias o de terceros (se preguntan), o desconocido (se pregunta y se
   recuerda).
3. **Emparejar sin duplicar.** Antes de proponer algo nuevo se busca un gasto
   ya cargado: hasta $1 de diferencia (manda el banco), de 5 días antes a 2
   después, uno a uno, la fecha más cercana gana y un empate se pregunta.
   También contra el **bruto** de un gasto con cuenta (`150000-25000*5`).
4. **Devoluciones.** Un crédito de terceros que entra hasta 30 días después de
   un gasto con bruto mayor que el neto es su devolución: no se carga.
5. **Regla del corte** (Franco, 19/10/2026). Un gasto cargado **antes que el
   ajuste inicial** ya estaba dentro de ese ajuste: si su fila del banco sale
   después del corte, el lote le resta esa parte al ajuste (*Ajuste
   Reconciliación* con `ingresos` del mismo signo que el banco).
6. **Sobrantes.** Lo cargado a mano que no está en el banco es efectivo, salvo
   que Franco diga tarjeta. Lo de los últimos 5 días del extracto no se
   pregunta: puede salir en el próximo.

Montos del banco en **centavos enteros**; los de `transacciones` son pesos.
"""

from __future__ import annotations

import itertools
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from core.db import get_config
from places.finanzas.core import lotes
from places.finanzas.core.extracto_galicia import Extracto, FilaBanco
from places.finanzas.core.lotes import Actualizar, Insertar, InsertarMovimiento, Movimiento, Ref

#: Desde qué día se concilia (Franco, 18/10/2026: "de acá en adelante, desde
#: los movimientos del banco del 17/10/2026"). Se puede cambiar por espacio con
#: la clave `conciliacion_desde` de `configuracion`.
CORTE_POR_DEFECTO = "2026-10-17"

DIAS_ANTES = 5           # el gasto puede ser hasta 5 días anterior a la fila del banco
DIAS_DESPUES = 2         # o hasta 2 posterior
TOLERANCIA = 100         # $1, en centavos
DIAS_DEVOLUCION = 30     # una devolución entra hasta 30 días después del gasto
DIAS_COLA = 5            # lo cargado en los últimos 5 días del extracto espera al próximo
DIAS_GUARDA = 10         # días antes del corte que se miran para no confundir gastos viejos

MOTIVO_AJUSTE = "Ajuste Reconciliación"
MOTIVO_PERCEPCION = "Percepción 30% (se devuelve)"

#: Tipo de movimiento (prefijo de la primera línea, normalizada) → tratamiento.
#: El orden importa: el primero que coincide gana.
_TRATAMIENTOS = (
    ("PAGO TARJETA", "pago_tarjeta"),
    ("COMPRA VENTA DE DOLARES", "divisa"),
    ("SUSCRIPCION FIMA", "fima"),
    ("RESCATE FIMA", "fima"),
    ("EXTRACCION CAJERO", "extraccion"),
    # Depósito de efectivo en la caja: son los haberes de SBT (Franco, 19/10/2026).
    ("DEP.EFVO", "ingreso"),
    # La percepción del 30% que se devuelve va a la línea neutra (Franco, 19/10/2026).
    ("PERCEPCION RG 5617", "percepcion"),
    ("TRANSF. CTAS PROPIAS", "propia"),
    ("TRANSFERENCIA DE CUENTA PROPIA", "propia"),
    ("INGRESO DE DINERO A CUENTA PROPIA", "propia"),
    ("TRANSFERENCIA DE TERCEROS", "terceros"),
    ("CREDITO TRANSFERENCIA", "terceros"),
    ("COMP. TITULOS", "inversion"),
    ("HONORARIOS", "ingreso"),
    ("TRANSFERENCIAS CASH SUELDOS", "ingreso"),
    ("INTERES CAPITALIZADO", "ingreso"),
    ("COMPRA DEBITO", "gasto"),
    ("PAGO DE SERVICIOS", "gasto"),
    ("DEB. AUTOM. DE SERV.", "gasto"),
    ("PAGO CON TRANSFERENCIA", "gasto"),
    ("PAGO EN TRANSPORTE", "gasto"),
    # Gasto, con la categoría aprendida por destinatario (Franco, 19/10/2026).
    ("TRANSFERENCIA A TERCEROS", "gasto"),
    ("COMISION", "gasto"),
    ("COM. ", "gasto"),
    ("IVA", "gasto"),
    ("PERCEP", "gasto"),
    ("PERC.", "gasto"),
    ("IMP.", "gasto"),
    ("IMPUESTO", "gasto"),
)

#: Categoría por defecto según el tipo, **solo si ese motivo existe** en el espacio.
_CATEGORIA_POR_TIPO = (
    ("PAGO EN TRANSPORTE", "Transportes"),
    ("PAGO DE SERVICIOS", "Servicios"),
    ("DEB. AUTOM. DE SERV.", "Servicios"),
    ("COMISION", "Impuestos"),
    ("COM. ", "Impuestos"),
    ("IVA", "Impuestos"),
    ("PERCEP", "Impuestos"),
    ("PERC.", "Impuestos"),
    ("IMP.", "Impuestos"),
    ("IMPUESTO", "Impuestos"),
    ("INTERES CAPITALIZADO", "Otros ingresos"),
    ("DEP.EFVO", "Haberes SBT"),
    ("COMP. TITULOS", "Inversiones"),
)

#: Tratamientos que no se cargan: mueven plata entre caja, FIMA y efectivo.
INTERNOS = {"fima", "extraccion"}
#: Tratamientos que se intentan emparejar con lo ya cargado.
EMPAREJABLES = {"gasto", "ingreso", "propia", "terceros", "desconocido", "movimiento",
                "divisa", "inversion", "percepcion"}
#: Tratamientos que **aprenden** la categoría por comercio. Las transferencias
#: propias y de terceros no: casi siempre son devoluciones y se preguntan.
APRENDEN = {"gasto", "ingreso", "desconocido", "movimiento"}
#: Motivos que el Secretario carga solo y que nunca son "sobrantes".
_MOTIVOS_DEL_SECRETARIO = {"ajuste reconciliacion", "rendimiento fima", "caja",
                           "percepcion 30% (se devuelve)"}
#: Roles de `emparejamientos` que sacan un gasto del juego (ya tiene pareja o destino).
#: "anterior" = un gasto de antes del corte que ya tiene su fila del banco antes
#: del corte: queda fuera del juego para no confundirlo con una fila nueva igual.
_ROLES_EXCLUSIVOS = ("origen", "mismo", "arrastre", "efectivo", "tarjeta", "reversion",
                     "anterior")


class ConciliacionInvalida(ValueError):
    """El extracto no se puede conciliar así. El texto va a Franco."""


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    from places.finanzas.core.comandos import normalizar  # import diferido: comandos importa esto
    return normalizar(s)


def _cent(pesos: float) -> int:
    return round(float(pesos) * 100)


def pesos_c(c: int) -> str:
    """Centavos → "$2.500" / "-$2.500,50" (el formato de siempre)."""
    from places.finanzas.core.comandos import pesos
    return pesos(c / 100)


def corte(conn: sqlite3.Connection, user_id: int, wid: int) -> date:
    return date.fromisoformat(get_config(conn, "conciliacion_desde", CORTE_POR_DEFECTO,
                                         user_id=user_id, workspace_id=wid))


def clasificar(tipo: str, aprendidos: dict[str, str]) -> str:
    if tipo in aprendidos:
        return aprendidos[tipo]
    for prefijo, tratamiento in _TRATAMIENTOS:
        if tipo.startswith(prefijo):
            return tratamiento
    return "desconocido"


def motivo_existente(nombre: str, existentes: list[str]) -> Optional[str]:
    """El motivo del espacio que se llama así (sin importar acentos ni mayúsculas)."""
    n = _norm(nombre)
    return next((m for m in existentes if _norm(m) == n), None)


def asegurar_categoria(conn: sqlite3.Connection, motivo: str, grupo: str, uid: int,
                       wid: int) -> None:
    """Crea el motivo **con su grupo** si no existe. Si existe, no lo toca.

    No es parte del lote: crear una categoría no mueve plata, y `_asegurar_motivo`
    de `transactions.py` la crearía como "Sin categorizar" (y la percepción, o el
    ajuste, aparecerían como gasto sin categoría en `resumen`).
    """
    conn.execute(
        "INSERT INTO categorias (motivo, grupo, user_id, workspace_id) "
        "SELECT ?, ?, ?, ? WHERE NOT EXISTS "
        "(SELECT 1 FROM categorias WHERE motivo = ? AND workspace_id = ?)",
        (motivo, grupo, uid, wid, motivo, wid),
    )


def _grupos(conn: sqlite3.Connection, wid: int) -> dict[str, str]:
    return {r["motivo"]: r["grupo"] for r in conn.execute(
        "SELECT motivo, grupo FROM categorias WHERE workspace_id = ?", (wid,))}


def montos_para(monto: int, motivo: str, grupo: Optional[str]) -> tuple[float, float]:
    """(pasivos, ingresos) en pesos para cargar una fila del banco en `motivo`.

    Un débito es gasto. Un crédito es ingreso si la categoría es de ingreso (o
    "Inversiones", que es dual); si no, es una **devolución** de esa categoría
    (`pasivos` negativo, la convención de siempre).
    """
    if monto < 0:
        return -monto / 100, 0.0
    if grupo == "Ingreso" or _norm(motivo) == "inversiones":
        return 0.0, monto / 100
    return -monto / 100, 0.0


# ---------------------------------------------------------------------------
# Lo que ya está en la base
# ---------------------------------------------------------------------------

@dataclass
class Cargado:
    """Un gasto o ingreso ya cargado, candidato a emparejarse con el banco."""

    id: int
    fecha: date
    pasivos: float
    ingresos: float
    motivo: str
    creado_en: str
    bruto: Optional[int]          # centavos, si se cargó con una cuenta
    efectivo_id: Optional[int]    # el vínculo "efectivo", si ya se había decidido

    @property
    def es_debito(self) -> bool:
        return self.pasivos > 0

    @property
    def importe(self) -> int:
        """Centavos, siempre positivo: lo que debería mostrar el banco."""
        if self.pasivos > 0:
            return _cent(self.pasivos)
        if self.ingresos > 0:
            return _cent(self.ingresos)
        return _cent(-self.pasivos)      # una devolución cargada a mano

    def describir(self) -> str:
        return f"{self.motivo} {pesos_c(self.importe)} ({self.fecha:%d/%m})"


def _cargados(conn: sqlite3.Connection, wid: int, desde: date, hasta: date) -> list[Cargado]:
    """Lo cargado entre esas fechas que todavía no tiene pareja ni destino.

    Un gasto marcado "efectivo" sigue en juego: si aparece en el banco, no
    era efectivo (y el vínculo se corrige).
    """
    filas = conn.execute(
        """
        SELECT t.id, t.fecha, t.pasivos, t.ingresos, t.motivo, t.creado_en, gc.bruto,
               (SELECT e.id FROM emparejamientos e WHERE e.transaccion_id = t.id
                  AND e.rol = 'efectivo') AS efectivo_id,
               (SELECT COUNT(*) FROM emparejamientos e WHERE e.transaccion_id = t.id
                  AND e.rol IN ('origen', 'mismo', 'arrastre', 'tarjeta', 'reversion',
                                'anterior')) AS ocupado
        FROM transacciones t
        LEFT JOIN gasto_cuentas gc ON gc.transaccion_id = t.id
        LEFT JOIN categorias c ON c.motivo = t.motivo AND c.workspace_id = t.workspace_id
        WHERE t.workspace_id = ? AND t.fecha BETWEEN ? AND ?
          AND COALESCE(c.grupo, '') != 'Saldo Inicial'
        ORDER BY t.id
        """,
        (wid, desde.isoformat(), hasta.isoformat()),
    ).fetchall()
    return [
        Cargado(r["id"], date.fromisoformat(r["fecha"]), float(r["pasivos"]),
                float(r["ingresos"]), r["motivo"], r["creado_en"],
                _cent(r["bruto"]) if r["bruto"] is not None else None, r["efectivo_id"])
        for r in filas
        if not r["ocupado"] and _norm(r["motivo"]) not in _MOTIVOS_DEL_SECRETARIO
        and (r["pasivos"] or r["ingresos"])
    ]


def _ajuste_inicial(conn: sqlite3.Connection, wid: int) -> Optional[str]:
    """`creado_en` del ajuste inicial: el primer "Ajuste Reconciliación" del espacio."""
    filas = conn.execute(
        "SELECT motivo, creado_en FROM transacciones WHERE workspace_id = ? ORDER BY creado_en",
        (wid,)).fetchall()
    return next((r["creado_en"] for r in filas if _norm(r["motivo"]) == _norm(MOTIVO_AJUSTE)),
                None)


def _ultima_fila(conn: sqlite3.Connection, wid: int) -> Optional[dict]:
    r = conn.execute("SELECT orden, fecha, saldo FROM banco_filas WHERE workspace_id = ? "
                     "ORDER BY orden DESC LIMIT 1", (wid,)).fetchone()
    return dict(r) if r else None


def _ancla(conn: sqlite3.Connection, wid: int) -> Optional[dict]:
    r = conn.execute("SELECT fecha, monto FROM saldos_declarados WHERE workspace_id = ? "
                     "AND parte = 'caja' ORDER BY id DESC LIMIT 1", (wid,)).fetchone()
    return {"fecha": r["fecha"], "saldo": r["monto"]} if r else None


# ---------------------------------------------------------------------------
# Emparejar
# ---------------------------------------------------------------------------

def _montos_coinciden(fila: FilaBanco, c: Cargado) -> Optional[str]:
    """'monto', 'bruto' o None. La dirección tiene que ser la misma."""
    if (fila.monto < 0) != c.es_debito:
        return None
    if abs(abs(fila.monto) - c.importe) <= TOLERANCIA:
        return "monto"
    if fila.monto < 0 and c.bruto is not None and abs(-fila.monto - c.bruto) <= TOLERANCIA:
        return "bruto"
    return None


def _en_ventana(fila: FilaBanco, c: Cargado) -> bool:
    return fila.fecha - timedelta(days=DIAS_ANTES) <= c.fecha <= fila.fecha + timedelta(
        days=DIAS_DESPUES)


def emparejar(filas: list[FilaBanco], cargados: list[Cargado]) -> tuple[
        dict[int, tuple[int, str]], dict[int, list[int]]]:
    """({fila: (gasto, por)}, {fila: [gastos empatados]}). Uno a uno, la fecha más cercana.

    Se va resolviendo de a una la fila con el candidato más cercano. Si esa
    fila tiene dos o más candidatos libres a la misma distancia, es un empate:
    se pregunta y no se toca. **Salvo que sean iguales** (misma categoría y
    monto: dos pasajes del mismo día): ahí da lo mismo cuál, y va el primero.
    """
    como_es = {c.id: (c.motivo, c.importe) for c in cargados}
    candidatos: dict[int, list[tuple[int, int, str]]] = {}
    for i, f in enumerate(filas):
        for c in cargados:
            if _en_ventana(f, c) and (por := _montos_coinciden(f, c)):
                candidatos.setdefault(i, []).append((abs((f.fecha - c.fecha).days), c.id, por))
    asignados: dict[int, tuple[int, str]] = {}
    empates: dict[int, list[int]] = {}
    usados: set[int] = set()
    while True:
        mejor = None
        for i, cands in candidatos.items():
            if i in asignados or i in empates:
                continue
            libres = [x for x in cands if x[1] not in usados]
            if not libres:
                continue
            d = min(x[0] for x in libres)
            if mejor is None or (d, i) < (mejor[0], mejor[1]):
                mejor = (d, i, [x for x in libres if x[0] == d])
        if mejor is None:
            return asignados, empates
        _, i, cercanos = mejor
        if len({(como_es[x[1]], x[2]) for x in cercanos}) > 1:
            empates[i] = sorted(x[1] for x in cercanos)
        else:
            _, cid, por = min(cercanos, key=lambda x: x[1])
            asignados[i] = (cid, por)
            usados.add(cid)


def _netos(filas: list[FilaBanco], debitos: list[int], creditos: list[int],
           sueltos: list[Cargado]) -> dict[int, tuple[int, list[int]]]:
    """{débito: (gasto, [créditos])} para gastos cargados **ya netos** de devoluciones.

    Franco a veces carga lo que le quedó después de que le devolvieron
    (pagó $60.000, le transfirieron $45.000, cargó $15.000) sin escribir la
    cuenta. Se reconoce cuando un débito cercano menos unos créditos que
    entraron después da justo lo cargado (±$1). Determinístico, y se muestra
    para que Franco lo confirme: nunca se carga solo.
    """
    grupos: dict[int, tuple[int, list[int]]] = {}
    libres_d, libres_c = list(debitos), list(creditos)
    for c in sorted(sueltos, key=lambda c: (c.fecha, c.id)):
        if not c.es_debito:
            continue
        for i in libres_d:
            f = filas[i]
            resto = -f.monto - c.importe
            if not (_en_ventana(f, c) and resto > TOLERANCIA):
                continue
            cerca = [j for j in libres_c if f.fecha - timedelta(days=3) <= filas[j].fecha
                     <= f.fecha + timedelta(days=DIAS_DEVOLUCION)][:12]
            hallado = next((list(combo) for k in range(1, 6)
                            for combo in itertools.combinations(cerca, k)
                            if abs(sum(filas[j].monto for j in combo) - resto) <= TOLERANCIA), None)
            if hallado:
                grupos[i] = (c.id, hallado)
                libres_d.remove(i)
                for j in hallado:
                    libres_c.remove(j)
                break
    return grupos


def _devoluciones(conn: sqlite3.Connection, wid: int, filas: list[FilaBanco],
                  libres: list[int], desde: date, hasta: date) -> dict[int, int]:
    """{fila: gasto} para los créditos que devuelven parte de un gasto con bruto."""
    gastos = conn.execute(
        """
        SELECT t.id, t.fecha, t.pasivos, gc.bruto,
               COALESCE((SELECT SUM(b.monto) FROM emparejamientos e
                         JOIN banco_filas b ON b.id = e.banco_fila_id
                         WHERE e.transaccion_id = t.id AND e.rol = 'devolucion'), 0) AS devuelto
        FROM transacciones t JOIN gasto_cuentas gc ON gc.transaccion_id = t.id
        WHERE t.workspace_id = ? AND t.fecha BETWEEN ? AND ? AND gc.bruto > t.pasivos
        ORDER BY t.fecha, t.id
        """,
        ((wid), (desde - timedelta(days=DIAS_DEVOLUCION)).isoformat(), hasta.isoformat()),
    ).fetchall()
    resta = {g["id"]: _cent(g["bruto"]) - _cent(g["pasivos"]) - g["devuelto"] for g in gastos}
    fechas = {g["id"]: date.fromisoformat(g["fecha"]) for g in gastos}
    asignadas: dict[int, int] = {}
    for i in libres:
        f = filas[i]
        posibles = [gid for gid in resta
                    if fechas[gid] <= f.fecha <= fechas[gid] + timedelta(days=DIAS_DEVOLUCION)
                    and f.monto <= resta[gid] + TOLERANCIA]
        if posibles:
            gid = min(posibles, key=lambda g: (f.fecha - fechas[g]).days)
            asignadas[i] = gid
            resta[gid] -= f.monto
    return asignadas


# ---------------------------------------------------------------------------
# La propuesta
# ---------------------------------------------------------------------------

def _fila_json(f: FilaBanco, tratamiento: str) -> dict:
    return {"fecha": f.fecha.isoformat(), "monto": f.monto, "saldo": f.saldo, "tipo": f.tipo,
            "comercio": f.comercio, "cotizacion": f.cotizacion, "tratamiento": tratamiento}


def _fila_de(d: dict) -> FilaBanco:
    return FilaBanco(date.fromisoformat(d["fecha"]), d["monto"], d["saldo"], d["tipo"],
                     d["comercio"], d["cotizacion"])


def _categoria_propuesta(conn: sqlite3.Connection, wid: int, f: FilaBanco, tratamiento: str,
                         existentes: list[str]) -> tuple[Optional[str], Optional[str]]:
    """(motivo, de dónde salió: 'aprendida' | 'tipo') o (None, None) si hay que preguntar."""
    if tratamiento in APRENDEN and f.comercio:
        r = conn.execute("SELECT motivo FROM reglas_comercio WHERE workspace_id = ? AND tipo = ? "
                         "AND comercio = ?", (wid, f.tipo, f.comercio)).fetchone()
        if r:
            return r["motivo"], "aprendida"
    if tratamiento == "percepcion":
        return MOTIVO_PERCEPCION, "tipo"
    if tratamiento == "divisa":
        nombre = "Compra Divisa" if f.monto < 0 else "Venta divisa"
        return motivo_existente(nombre, existentes), "tipo"
    if tratamiento in ("propia", "terceros", "desconocido"):
        return None, None
    for prefijo, nombre in _CATEGORIA_POR_TIPO:
        if f.tipo.startswith(prefijo):
            m = motivo_existente(nombre, existentes)
            return (m, "tipo") if m else (None, None)
    return None, None


def proponer_extracto(
    conn: sqlite3.Connection, extracto: Extracto, *, user_id: int, wid: int, ahora: datetime,
) -> dict:
    """Arma la propuesta del extracto. `ConciliacionInvalida` si no se puede."""
    desde_corte = corte(conn, user_id, wid)
    ultima = _ultima_fila(conn, wid)
    conocidas = {(r["fecha"], r["monto"], r["saldo"]) for r in conn.execute(
        "SELECT fecha, monto, saldo FROM banco_filas WHERE workspace_id = ?", (wid,))}
    nuevas = [f for f in extracto.filas if f.fecha >= desde_corte
              and (f.fecha.isoformat(), f.monto, f.saldo) not in conocidas]

    ancla_nueva = None
    if ultima is None:
        previa = _ancla(conn, wid)
        if previa is None:
            antes = [f for f in extracto.filas if f.fecha < desde_corte]
            if not antes:
                raise ConciliacionInvalida(
                    f"Para arrancar necesito ver dónde estaba la caja antes del "
                    f"{desde_corte:%d/%m/%Y}: mandame un extracto que llegue hasta antes de esa "
                    "fecha (el que ya tenés, el que termina el 16/10, sirve).")
            previa = {"fecha": antes[-1].fecha.isoformat(), "saldo": antes[-1].saldo}
            ancla_nueva = previa
        ultima = {"orden": 0, "fecha": previa["fecha"], "saldo": previa["saldo"]}

    aprendidos = {r["tipo"]: r["tratamiento"] for r in conn.execute(
        "SELECT tipo, tratamiento FROM reglas_tipo WHERE workspace_id = ?", (wid,))}
    # Guarda: un gasto de los días antes del corte que ya tiene su fila del banco
    # **antes** del corte no puede emparejarse con una fila nueva del mismo monto
    # (un pasaje de subte, un kiosco): sería una regla del corte falsa. Se lo saca
    # del juego, y queda guardado para los próximos extractos.
    previas = [f for f in extracto.filas
               if desde_corte - timedelta(days=DIAS_GUARDA) <= f.fecha < desde_corte
               and clasificar(f.tipo, aprendidos) in EMPAREJABLES]
    viejos = [c for c in _cargados(conn, wid,
                                   desde_corte - timedelta(days=DIAS_GUARDA + DIAS_ANTES),
                                   desde_corte - timedelta(days=1))]
    anteriores = sorted(cid for cid, _ in emparejar(previas, viejos)[0].values())

    if not nuevas:
        if ancla_nueva:
            return {"tipo": "extracto", "ancla": ancla_nueva, "orden_inicial": 1, "filas": [],
                    "items": [], "numerados": 0, "anteriores": anteriores,
                    "desde": extracto.desde.isoformat(),
                    "hasta": extracto.hasta.isoformat(), "saldo_final": extracto.saldo_final}
        raise ConciliacionInvalida("Ya tenía todo este extracto: no hay movimientos nuevos.")
    if nuevas[0].saldo_antes != ultima["saldo"] or nuevas[0].fecha.isoformat() < ultima["fecha"]:
        raise ConciliacionInvalida(
            f"Este extracto no empalma con lo que ya tenía: la caja quedó en "
            f"{pesos_c(ultima['saldo'])} el {date.fromisoformat(ultima['fecha']):%d/%m} y el "
            f"primer movimiento nuevo ({nuevas[0].fecha:%d/%m}) arranca de "
            f"{pesos_c(nuevas[0].saldo_antes)}. Falta un pedazo: bajá el extracto desde el "
            f"{date.fromisoformat(ultima['fecha']) + timedelta(days=1):%d/%m}.")

    tratamientos = [clasificar(f.tipo, aprendidos) for f in nuevas]
    desde = nuevas[0].fecha
    hasta = nuevas[-1].fecha
    # Todo lo cargado desde el corte que todavía no tiene pareja ni destino: lo
    # que está en la ventana de alguna fila puede emparejarse, y lo que quedó
    # más viejo que la cola del extracto es un sobrante (aunque sea de antes de
    # este extracto: pudo haber quedado esperando en la cola del anterior).
    cargados = [c for c in _cargados(conn, wid, min(desde_corte, desde) - timedelta(days=DIAS_ANTES),
                                     max(hasta, ahora.date()) + timedelta(days=DIAS_DESPUES))
                if c.id not in anteriores]
    por_id = {c.id: c for c in cargados}
    emparejables = [i for i, t in enumerate(tratamientos) if t in EMPAREJABLES]
    asignados, empates = emparejar([nuevas[i] for i in emparejables], cargados)
    asignados = {emparejables[k]: v for k, v in asignados.items()}
    empates = {emparejables[k]: v for k, v in empates.items()}
    libres_credito = [i for i in emparejables if i not in asignados and i not in empates
                      and nuevas[i].monto > 0 and tratamientos[i] in
                      ("terceros", "propia", "desconocido", "movimiento")]
    devoluciones = _devoluciones(conn, wid, nuevas, libres_credito, desde, hasta)
    # Gastos que Franco cargó ya netos de devoluciones, sin escribir la cuenta.
    usados = {cid for cid, _ in asignados.values()}
    netos = _netos(
        nuevas,
        [i for i in emparejables if i not in asignados and i not in empates and nuevas[i].monto < 0],
        [i for i in libres_credito if i not in devoluciones],
        [c for c in cargados if c.id not in usados and not c.efectivo_id
         and c.fecha >= desde_corte])
    credito_de_neto = {j: (i, cid) for i, (cid, js) in netos.items() for j in js}

    gastos_devueltos = {gid: conn.execute(
        "SELECT id, fecha, pasivos, motivo, creado_en FROM transacciones WHERE id = ?",
        (gid,)).fetchone() for gid in set(devoluciones.values())}
    ajuste_inicial = _ajuste_inicial(conn, wid)

    def antes_del_ajuste(creado_en: str) -> bool:
        return ajuste_inicial is not None and creado_en < ajuste_inicial

    fechas_involucradas = [por_id[c].fecha for c, _ in asignados.values()] + [
        date.fromisoformat(g["fecha"]) for g in gastos_devueltos.values()] + [
        por_id[cid].fecha for cid, _ in netos.values()]
    if ajuste_inicial is None and any(f < desde_corte for f in fechas_involucradas):
        raise ConciliacionInvalida(
            f"Hay movimientos del banco que coinciden con gastos cargados antes del "
            f"{desde_corte:%d/%m}, y no encuentro el ajuste inicial («{MOTIVO_AJUSTE}»). Sin él "
            "no puedo aplicar la regla del corte: cargalo y mandame el extracto de nuevo.")

    existentes = _motivos(conn, wid)
    items: list[dict] = []
    for i, f in enumerate(nuevas):
        t = tratamientos[i]
        base = {"fila": i}
        if t in INTERNOS:
            items.append({**base, "clase": "interno"})
        elif t == "pago_tarjeta":
            items.append({**base, "clase": "esperando"})
        elif i in asignados:
            cid, por = asignados[i]
            c = por_id[cid]
            correccion = (abs(f.monto) if por == "monto" and abs(f.monto) != c.importe else None)
            items.append({**base, "clase": "coincide", "txn": cid, "por": por,
                          "desc": c.describir(), "correccion": correccion,
                          "arrastre": antes_del_ajuste(c.creado_en),
                          "efectivo_id": c.efectivo_id, "debito": c.es_debito,
                          "devolucion_manual": c.pasivos < 0})
        elif i in netos:
            c = por_id[netos[i][0]]
            items.append({**base, "clase": "coincide", "txn": c.id, "por": "neto", "grupo": i,
                          "desc": c.describir(), "correccion": None,
                          "arrastre": antes_del_ajuste(c.creado_en), "efectivo_id": None,
                          "debito": True, "devolucion_manual": False})
        elif i in credito_de_neto:
            grupo, cid = credito_de_neto[i]
            c = por_id[cid]
            items.append({**base, "clase": "devolucion", "txn": cid, "grupo": grupo,
                          "desc": c.describir(), "arrastre": antes_del_ajuste(c.creado_en)})
        elif i in devoluciones:
            g = gastos_devueltos[devoluciones[i]]
            items.append({**base, "clase": "devolucion", "txn": g["id"],
                          "desc": f"{g['motivo']} {pesos_c(_cent(g['pasivos']))} "
                                  f"({date.fromisoformat(g['fecha']):%d/%m})",
                          "arrastre": antes_del_ajuste(g["creado_en"])})
        else:
            motivo, origen = _categoria_propuesta(conn, wid, f, t, existentes)
            items.append({**base, "clase": "falta", "motivo": motivo, "origen": origen,
                          "empate": [por_id[x].describir() for x in empates.get(i, [])],
                          "empate_ids": empates.get(i, [])})

    emparejados = {it["txn"] for it in items if it["clase"] == "coincide"}
    tope = hasta - timedelta(days=DIAS_COLA)
    sobran, esperan = [], 0
    pares = _pares_venta_divisa(cargados)
    for c in cargados:
        if c.id in emparejados or c.efectivo_id or c.id in pares or c.fecha < desde_corte:
            continue
        if c.fecha > tope:
            esperan += 1
            continue
        # Un "Pago tarjeta" cargado a mano no es efectivo: desde el corte el pago
        # se reemplaza por el detalle del resumen (paso 5). Queda sin decidir.
        destino = None if _norm(c.motivo) == "pago tarjeta" else "efectivo"
        sobran.append({"clase": "sobra", "txn": c.id, "desc": c.describir(), "destino": destino})
    # Un faltante y un sobrante de montos parecidos (un redondeo, unos centavos
    # de más) pueden ser el mismo gasto: no se empareja solo (la tolerancia
    # acordada es $1), pero se sugiere, para que no quede cargado dos veces.
    # (También los de la cola: un gasto de ayer puede ser el de esta fila.)
    sueltos = [c for c in cargados if c.id not in emparejados and c.id not in pares
               and c.fecha >= desde_corte]
    for it in items:
        if it["clase"] != "falta":
            continue
        f = nuevas[it["fila"]]
        parecidos = [c for c in sueltos
                     if c.es_debito == (f.monto < 0) and _en_ventana(f, c)
                     and TOLERANCIA < abs(abs(f.monto) - c.importe) <= abs(f.monto) * 5 // 100]
        it["parecidos"] = [c.id for c in parecidos]
        it["parecidos_desc"] = [c.describir() for c in parecidos]
    items.extend(sobran)

    _numerar(items)
    return {"tipo": "extracto", "ancla": ancla_nueva, "orden_inicial": ultima["orden"] + 1,
            "filas": [_fila_json(f, t) for f, t in zip(nuevas, tratamientos)],
            "items": items, "numerados": sum(1 for it in items if it.get("n")),
            "anteriores": anteriores,
            "desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "saldo_final": nuevas[-1].saldo, "esperan": esperan}


def _motivos(conn: sqlite3.Connection, wid: int) -> list[str]:
    return [r["motivo"] for r in conn.execute(
        "SELECT motivo FROM categorias WHERE workspace_id = ? UNION "
        "SELECT DISTINCT motivo FROM transacciones WHERE workspace_id = ?", (wid, wid))
        if r["motivo"]]


def _pares_venta_divisa(cargados: list[Cargado]) -> set[int]:
    """Los pares "Venta divisa" + gasto del mismo día y monto: no tienen banco a propósito."""
    pares: set[int] = set()
    ventas = [c for c in cargados if _norm(c.motivo) == "venta divisa" and c.ingresos > 0]
    for v in ventas:
        gasto = next((c for c in cargados if c.id not in pares and c.id != v.id
                      and c.fecha == v.fecha and c.pasivos > 0
                      and abs(_cent(c.pasivos) - _cent(v.ingresos)) <= 1), None)
        if gasto:
            pares.update({v.id, gasto.id})
    return pares


def _numerar(items: list[dict]) -> None:
    """Numera lo que Franco puede contestar: faltan, después lo que conviene revisar
    (correcciones, la regla del corte, devoluciones) y al final los sobrantes."""
    n = 0
    for clase_ok in (lambda it: it["clase"] == "falta",
                     lambda it: it["clase"] == "devolucion" or (
                         it["clase"] == "coincide" and (it["correccion"] or it["arrastre"]
                                                         or it["por"] in ("bruto", "neto"))),
                     lambda it: it["clase"] == "sobra"):
        for it in items:
            if clase_ok(it):
                n += 1
                it["n"] = n


# ---------------------------------------------------------------------------
# El texto
# ---------------------------------------------------------------------------

def _linea_fila(f: dict) -> str:
    quien = f" · {f['comercio']}" if f.get("comercio") else ""
    signo = "+" if f["monto"] > 0 else ""
    return (f"{date.fromisoformat(f['fecha']):%d/%m} {f['tipo'].title()}{quien} "
            f"{signo}{pesos_c(abs(f['monto']))}")


def texto_propuesta(prop: dict, *, nuevo_ancla: bool) -> str:
    filas = prop["filas"]
    lineas = []
    if prop.get("ancla"):
        a = prop["ancla"]
        lineas.append(f"📍 Punto de partida: la caja tenía {pesos_c(a['saldo'])} el "
                      f"{date.fromisoformat(a['fecha']):%d/%m/%Y}.")
    if not filas:
        lineas.append("No hay movimientos desde el corte: con tu *ok* lo guardo como punto de "
                      "partida, y desde ahí concilio los próximos extractos.")
        return "\n".join(lineas)
    lineas.append(f"📄 Caja de ahorro, del {date.fromisoformat(prop['desde']):%d/%m} al "
                  f"{date.fromisoformat(prop['hasta']):%d/%m} ({len(filas)} movimientos nuevos).")
    if not nuevo_ancla:
        lineas.append("La cadena de saldos empalma con lo que ya tenía ✔")
    items = prop["items"]

    def de(clase):
        return [it for it in items if it["clase"] == clase]

    coinciden = de("coincide")
    if coinciden:
        lineas.append(f"\n✔ Coinciden {len(coinciden)} con lo que ya cargaste.")
    internos = de("interno")
    if internos:
        lineas.append(f"↔ Internos {len(internos)} (FIMA y cajero): no se cargan.")
    for it in de("esperando"):
        lineas.append(f"⏳ Esperando el resumen: {_linea_fila(filas[it['fila']])} "
                      "(se desarma cuando me mandes el resumen)")

    faltan = de("falta")
    if faltan:
        lineas.append("\n*Faltan* (te propongo):")
        for it in faltan:
            linea = f"{it['n']}. {_linea_fila(filas[it['fila']])} → "
            if it.get("descartada"):
                linea += "no se carga"
            elif it["motivo"]:
                linea += it["motivo"] + _marca(it)
            else:
                linea += "¿categoría?"
            if it.get("empate") and not it["motivo"] and not it.get("descartada"):
                opciones = " o ".join(f"#{i} {d}" for i, d in zip(it["empate_ids"], it["empate"]))
                linea += f"\n     puede ser {opciones}: contestá *{it['n']} es {it['empate_ids'][0]}*"
            elif it.get("parecidos") and not it.get("descartada"):
                opciones = " o ".join(f"#{i} {d}" for i, d in zip(it["parecidos"],
                                                                  it["parecidos_desc"]))
                linea += (f"\n     ¿será {opciones}? Si es, contestá *{it['n']} es "
                          f"{it['parecidos'][0]}* (y queda con el monto del banco)")
            lineas.append(linea)

    revisar = [it for it in items if it.get("n") and it["clase"] in ("coincide", "devolucion")]
    if revisar:
        lineas.append("\n*Revisá* (si no va, contestá *N no*):")
        for it in revisar:
            f = filas[it["fila"]]
            if it["clase"] == "devolucion":
                linea = (f"{it['n']}. {_linea_fila(f)} → devolución de {it['desc']}: "
                         "no se carga")
            else:
                linea = f"{it['n']}. {_linea_fila(f)} = {it['desc']}"
                if it["correccion"]:
                    linea += f" → lo corrijo a {pesos_c(it['correccion'])}"
                if it["por"] == "bruto":
                    linea += " (por lo que pagaste en el momento)"
                if it["por"] == "neto":
                    linea += (" (lo cargaste neto: con las devoluciones de abajo da justo; "
                              "si no, contestá *N no*)")
            if it["arrastre"]:
                linea += " · ya estaba en el ajuste inicial: lo descuento del ajuste"
            lineas.append(linea)

    sobran = de("sobra")
    if sobran:
        lineas.append("\n*Sobran* (los cargaste y no están en el banco):")
        for it in sobran:
            destino = {"efectivo": "efectivo", "tarjeta": "tarjeta (lo trae un resumen)",
                       None: "sin decidir"}[it["destino"]]
            lineas.append(f"{it['n']}. {it['desc']} → {destino}")
    if prop.get("esperan"):
        lineas.append(f"({prop['esperan']} gasto(s) de los últimos días esperan al próximo "
                      "extracto.)")

    lineas.append("\n¿Va? Contestá *ok*. Para corregir antes: *2 salidas* · *2 no* · "
                  "*5 tarjeta* · *cancelar*")
    return "\n".join(lineas)


def _marca(it: dict) -> str:
    if it.get("cat_tipo") == "parecida":
        return f"  ← ¿quisiste decir? (escribiste «{it['tipeada']}»)"
    if it.get("cat_tipo") == "nueva":
        return "  ← categoría nueva"
    return ""


# ---------------------------------------------------------------------------
# Respuestas y aplicar
# ---------------------------------------------------------------------------

@dataclass
class Resultado:
    texto: str
    resultado: str  # pendiente | lote | rechazado


def responder(
    conn: sqlite3.Connection, lote: lotes.Lote, *, aceptar: bool, cancelar: bool,
    correcciones: tuple[tuple[int, str], ...], user_id: int, wid: int, ahora: datetime,
) -> Resultado:
    from places.finanzas.core.comandos import resolver_categoria  # import diferido

    if cancelar:
        lotes.descartar(conn, lote.id)
        return Resultado("Listo, descarté la propuesta: no cargué nada.", "rechazado")
    prop = lote.propuesta
    items = prop["items"]
    por_n = {it["n"]: it for it in items if it.get("n")}
    dudosa, errores = False, []
    existentes = _motivos(conn, wid)
    for n, que in correcciones:
        it = por_n.get(n)
        if it is None:
            errores.append(f"{n}: ya no está en la propuesta")
            continue
        clave = _norm(que)
        if clave in {"no", "interno", "sacar"}:
            if it["clase"] == "falta":
                it["descartada"] = True
            elif it["clase"] == "sobra":
                it["destino"] = None
            else:   # deshacer el emparejamiento: pasa a faltar
                if it.get("por") == "neto":
                    # Las devoluciones que lo explicaban también pasan a faltar.
                    for otro in items:
                        if otro is not it and otro.get("grupo") == it["grupo"]:
                            _a_falta(otro, None)
                _a_falta(it, None)
            continue
        if it["clase"] == "sobra":
            if clave in {"efectivo", "tarjeta"}:
                it["destino"] = clave
            else:
                errores.append(f"{n}: para lo que sobra, contestá *{n} efectivo* o *{n} tarjeta*")
            continue
        if clave.startswith("es "):
            cid = clave.removeprefix("es ").lstrip("#").strip()
            opciones = dict(zip(it.get("empate_ids", []), it.get("empate", [])))
            opciones.update(zip(it.get("parecidos", []), it.get("parecidos_desc", [])))
            if it["clase"] != "falta" or not cid.isdigit() or int(cid) not in opciones:
                errores.append(f"{n}: *es* solo sirve para elegir entre los candidatos que te mostré")
                continue
            cid = int(cid)
            fila = prop["filas"][it["fila"]]
            t = conn.execute("SELECT pasivos, ingresos FROM transacciones WHERE id = ?",
                             (cid,)).fetchone()
            importe = _cent(t["pasivos"] or t["ingresos"])
            it.update(clase="coincide", txn=cid, por="monto", desc=opciones[cid],
                      correccion=abs(fila["monto"]) if abs(fila["monto"]) != abs(importe) else None,
                      arrastre=False, efectivo_id=None, debito=fila["monto"] < 0,
                      devolucion_manual=t["pasivos"] < 0)
            # Si estaba en "sobran", ya no sobra: es este.
            items[:] = [x for x in items if not (x["clase"] == "sobra" and x["txn"] == cid)]
            continue
        tipo, nombre = resolver_categoria(que, existentes)
        if it["clase"] != "falta":
            _a_falta(it, None)
        it.update(motivo=nombre if tipo != "nueva" else " ".join(que.split()).capitalize(),
                  cat_tipo=tipo, tipeada=que, descartada=False)
        dudosa = dudosa or tipo != "exacta"

    lotes.actualizar(conn, lote.id, prop)
    if errores:
        return Resultado("⚠️ " + "\n⚠️ ".join(errores) + "\n\n" + texto_propuesta(
            prop, nuevo_ancla=bool(prop.get("ancla"))), "pendiente")
    sin_categoria = [str(it["n"]) for it in items
                     if it["clase"] == "falta" and not it["motivo"] and not it.get("descartada")]
    if aceptar and sin_categoria:
        return Resultado(f"Me falta la categoría de: {', '.join(sin_categoria)}. Contestá "
                         f"*{sin_categoria[0]} salidas* (o *{sin_categoria[0]} no* si no va).",
                         "pendiente")
    if not aceptar or dudosa:
        aviso = "Revisá las marcadas y contestá *ok*.\n\n" if (aceptar and dudosa) else ""
        return Resultado(aviso + texto_propuesta(prop, nuevo_ancla=bool(prop.get("ancla"))),
                         "pendiente")

    cargados, emparejados = aplicar(conn, lote.id, prop, user_id=user_id, wid=wid, ahora=ahora)
    return Resultado(_texto_aplicado(prop, cargados, emparejados), "lote")


def _a_falta(it: dict, motivo: Optional[str]) -> None:
    """Un emparejamiento o una devolución que Franco rechazó: pasa a faltar."""
    it.update(clase="falta", motivo=motivo, origen=None, empate=[], empate_ids=[], txn=None,
              descartada=False)


def aplicar(conn: sqlite3.Connection, lote_id: int, prop: dict, *, user_id: int, wid: int,
            ahora: datetime) -> tuple[int, int]:
    """Arma las operaciones del lote y lo aplica. (cargados, emparejados)."""
    filas = prop["filas"]
    items = prop["items"]
    existentes = _motivos(conn, wid)
    motivo_ajuste = motivo_existente(MOTIVO_AJUSTE, existentes) or MOTIVO_AJUSTE
    # Las categorías del Secretario se crean con su grupo antes de cargar nada.
    if any(it.get("arrastre") for it in items):
        asegurar_categoria(conn, motivo_ajuste, "Gasto Variable", user_id, wid)
    if any(it.get("motivo") == MOTIVO_PERCEPCION for it in items):
        asegurar_categoria(conn, MOTIVO_PERCEPCION, "Flujo Capital", user_id, wid)
    grupos = _grupos(conn, wid)
    creado = ahora.isoformat()

    estado_de: dict[int, str] = {}
    for it in items:
        if "fila" not in it:
            continue
        estado_de[it["fila"]] = {
            "interno": "interna", "esperando": "esperando_resumen", "coincide": "emparejada",
            "devolucion": "devolucion",
        }.get(it["clase"], "descartada" if it.get("descartada") else "cargada")

    ops: list = []
    if prop.get("ancla"):
        ops.append(Insertar("saldos_declarados", {
            "workspace_id": wid, "parte": "caja", "fecha": prop["ancla"]["fecha"],
            "monto": prop["ancla"]["saldo"], "declarado_en": creado}))
    for i, f in enumerate(filas):
        ops.append(Insertar("banco_filas", {
            "workspace_id": wid, "orden": prop["orden_inicial"] + i, "fecha": f["fecha"],
            "monto": f["monto"], "saldo": f["saldo"], "tipo": f["tipo"], "comercio": f["comercio"],
            "cotizacion": f["cotizacion"], "tratamiento": f["tratamiento"],
            "estado": estado_de.get(i, "cargada")}, clave=f"f{i}"))

    for cid in prop.get("anteriores", []):
        ops.append(Insertar("emparejamientos", {
            "workspace_id": wid, "transaccion_id": cid, "banco_fila_id": None,
            "rol": "anterior", "creado_en": creado}))

    reglas: dict[tuple[str, str], str] = {}
    tipos_nuevos: set[str] = set()
    cargados = emparejados = 0
    for k, it in enumerate(items):
        if it["clase"] in ("coincide", "devolucion"):
            fila = filas[it["fila"]]
            rol = "devolucion" if it["clase"] == "devolucion" else (
                "arrastre" if it["arrastre"] else "mismo")
            if it["clase"] == "coincide" and it.get("efectivo_id"):
                # Lo había dado por efectivo y apareció en el banco: no era efectivo.
                ops.append(Actualizar("emparejamientos", it["efectivo_id"], {
                    "rol": rol, "banco_fila_id": Ref(f"f{it['fila']}"), "era_efectivo": 1}))
            else:
                ops.append(Insertar("emparejamientos", {
                    "workspace_id": wid, "transaccion_id": it["txn"],
                    "banco_fila_id": Ref(f"f{it['fila']}"), "rol": rol, "creado_en": creado}))
            if it["clase"] == "coincide" and it["correccion"]:
                columna = "pasivos" if it["debito"] else "ingresos"
                valor = it["correccion"] / 100
                if it.get("devolucion_manual"):
                    columna, valor = "pasivos", -valor
                ops.append(Actualizar("transacciones", it["txn"], {columna: valor}))
            if it["arrastre"]:
                ops.append(InsertarMovimiento(Movimiento(
                    fecha=date.fromisoformat(fila["fecha"]), motivo=motivo_ajuste,
                    ingresos=fila["monto"] / 100,
                    comentario="Regla del corte: ya estaba en el ajuste inicial"), clave=f"r{k}"))
                ops.append(Insertar("emparejamientos", {
                    "workspace_id": wid, "transaccion_id": Ref(f"r{k}"),
                    "banco_fila_id": Ref(f"f{it['fila']}"), "rol": "reversion",
                    "creado_en": creado}))
            emparejados += 1
        elif it["clase"] == "falta" and it["motivo"] and not it.get("descartada"):
            fila = filas[it["fila"]]
            pasivos, ingresos = montos_para(fila["monto"], it["motivo"], grupos.get(it["motivo"]))
            ops.append(InsertarMovimiento(Movimiento(
                fecha=date.fromisoformat(fila["fecha"]), motivo=it["motivo"], pasivos=pasivos,
                ingresos=ingresos, comentario=fila["comercio"]), clave=f"t{k}"))
            ops.append(Insertar("emparejamientos", {
                "workspace_id": wid, "transaccion_id": Ref(f"t{k}"),
                "banco_fila_id": Ref(f"f{it['fila']}"), "rol": "origen", "creado_en": creado}))
            cargados += 1
            if fila["tratamiento"] in APRENDEN and fila["comercio"]:
                reglas[(fila["tipo"], fila["comercio"])] = it["motivo"]
            if fila["tratamiento"] == "desconocido":
                tipos_nuevos.add(fila["tipo"])
        elif it["clase"] == "sobra" and it["destino"]:
            ops.append(Insertar("emparejamientos", {
                "workspace_id": wid, "transaccion_id": it["txn"], "banco_fila_id": None,
                "rol": it["destino"], "creado_en": creado}))

    for (tipo, comercio), motivo in reglas.items():
        previa = conn.execute("SELECT id, motivo FROM reglas_comercio WHERE workspace_id = ? "
                              "AND tipo = ? AND comercio = ?", (wid, tipo, comercio)).fetchone()
        if previa is None:
            ops.append(Insertar("reglas_comercio", {"workspace_id": wid, "tipo": tipo,
                                                    "comercio": comercio, "motivo": motivo}))
        elif previa["motivo"] != motivo:
            ops.append(Actualizar("reglas_comercio", previa["id"], {"motivo": motivo}))
    for tipo in sorted(tipos_nuevos):
        ops.append(Insertar("reglas_tipo", {"workspace_id": wid, "tipo": tipo,
                                            "tratamiento": "movimiento"}))

    lotes.aplicar_operaciones(conn, lote_id, ops, user_id=user_id, ahora=ahora)
    return cargados, emparejados


def _texto_aplicado(prop: dict, cargados: int, emparejados: int) -> str:
    if not prop["filas"]:
        return (f"✅ Guardé el punto de partida: la caja tenía {pesos_c(prop['ancla']['saldo'])} "
                f"el {date.fromisoformat(prop['ancla']['fecha']):%d/%m/%Y}.")
    partes = [f"cargué {cargados}" if cargados else None,
              f"emparejé {emparejados} con lo que ya tenías" if emparejados else None]
    hecho = " y ".join(p for p in partes if p) or "anoté los movimientos"
    return (f"✅ Listo: {hecho}. La caja quedó en {pesos_c(prop['saldo_final'])} el "
            f"{date.fromisoformat(prop['hasta']):%d/%m}.\n*deshacer* vuelve todo atrás.")
