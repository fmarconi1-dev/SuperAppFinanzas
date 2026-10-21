"""Balances de la semana por WhatsApp (ADR-0011, `docs/PLAN-BALANCES.md`).

El domingo a la noche el Secretario le manda a Franco las empresas que
presentan balance esa semana: primero las de su lista (con las argentinas
adentro), después las 15 más grandes del S&P 500; `balances todas` muestra el
resto. Franco contesta como en los lotes (`1 3 7`, tickers, `todas`,
`ninguna`) y lo elegido queda anotado para agendar.

**Solo la fecha** (Franco, 21/10/2026): el día y si presenta antes de la
apertura o después del cierre. Nada de ganancia ni ingresos, y nada de IA:
todo sale del calendario de Nasdaq.

Reglas:

* **La propuesta no es un lote.** `lotes.proponer` deja una sola propuesta
  por espacio y descarta la anterior: la lista del domingo no puede tirar un
  extracto o un resumen pendiente. Vive en `balances_propuestas`, convive con
  un lote abierto, y una lista nueva solo reemplaza a la lista anterior.
* **Lo que ya pasó no se agenda** (Franco, 21/10/2026): si la lista llega tarde
  (la ventana de 24 h estaba cerrada), lo de un día anterior se avisa y no se toma.
* La red llega inyectada (`fuentes`: `calendario` y `lista_sp500`, de
  `core.api.balances_fuentes`). Acá no se sale a internet.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from core.api.balances_fuentes import FilaCalendario, ListaNoDisponible, ticker_canonico

log = logging.getLogger("superapp.balances")

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")

#: La lista de Franco (`MEJORAS.md`, 19/10/2026): las 23 preseteadas y las 20
#: sumadas como termómetros. Van primero aunque no estén en el S&P 500.
#: SPCX es SpaceX (verificado en Nasdaq el 20/10/2026); PAM es Pampa (PAMP es
#: el ticker de BYMA).
MI_LISTA = (
    "GGAL", "YPF", "MELI", "NU", "VIST", "VST", "CEG", "UNH", "NVDA", "GOOGL", "TSM",
    "UBER", "NBIS", "SATL", "SPCX", "MU", "MSFT", "META", "MCD", "KO", "PEP", "WMT", "PAM",
    # Argentinas
    "BMA", "BBAR", "SUPV", "TGS", "CEPU", "LOMA", "EDN", "TEO", "IRS", "GLOB",
    # Chips y centros de datos · energía · seguros de salud · consumo · bancos
    "ASML", "AVGO", "AMD", "AMZN", "ORCL", "NEE", "TLN", "ELV", "CVS", "COST", "PG", "JPM",
)
#: Cuántas del S&P 500 (fuera de la lista de Franco) van en el mensaje.
CANTIDAD_GRANDES = 15
#: La lista del S&P 500 se vuelve a pedir a Wikipedia una vez por mes.
VIGENCIA_SP500 = timedelta(days=30)

_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
_MOMENTO = {"pre": "pre-apertura", "post": "post-cierre", None: "sin hora"}
_ORDEN_MOMENTO = {"pre": 0, None: 1, "post": 2}


@dataclass
class Propuesta:
    id: int
    lunes: date
    items: list[dict]
    #: Los primeros `principales` items son los del mensaje; el resto, `balances todas`.
    principales: int
    elegidos: list[str]


@dataclass
class Eleccion:
    todas: bool = False
    ninguna: bool = False
    #: Números de renglón, en el orden en que los escribió Franco.
    numeros: tuple[int, ...] = ()
    tickers: tuple[str, ...] = ()
    explicita: bool = False   # empezó con "balances"


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

def lunes_de(hoy: date) -> date:
    """La semana de balances de `hoy`: la actual; un sábado o domingo, la que viene."""
    if hoy.weekday() >= 5:
        return hoy + timedelta(days=7 - hoy.weekday())
    return hoy - timedelta(days=hoy.weekday())


def _dia(f: date) -> str:
    return f"{_DIAS[f.weekday()]} {f:%d/%m}"


def _vence(lunes: date) -> datetime:
    """La propuesta vale hasta el final del viernes de esa semana."""
    return datetime.combine(lunes + timedelta(days=5), time(0, 0), tzinfo=ZONA)


# ---------------------------------------------------------------------------
# La lista del S&P 500 (una vez por mes)
# ---------------------------------------------------------------------------

def sp500(conn: sqlite3.Connection, fuentes: Any, ahora: datetime
          ) -> tuple[Optional[set[str]], Optional[str]]:
    """(tickers, aviso). Pide a Wikipedia si la copia guardada tiene más de un mes.

    Si Wikipedia no contesta, sirve la copia guardada (la lista cambia pocas
    veces por año y se refresca una vez por mes a propósito). Sin copia, los
    del S&P quedan `s/d` con el motivo: nunca una lista vacía en silencio.
    """
    filas = conn.execute("SELECT ticker, actualizado_en FROM balances_sp500").fetchall()
    guardada = {f["ticker"] for f in filas}
    if filas:
        actualizada = max(datetime.fromisoformat(f["actualizado_en"]) for f in filas)
        if ahora - actualizada < VIGENCIA_SP500:
            return guardada, None
    try:
        nueva = fuentes.lista_sp500()
    except ListaNoDisponible as e:
        if guardada:
            log.warning("Wikipedia no contestó (%s): uso la lista del S&P 500 guardada", e)
            return guardada, None
        log.error("Sin lista del S&P 500: %s", e)
        return None, f"S&P 500: s/d (no pude traer la lista: {e})"
    conn.execute("DELETE FROM balances_sp500")
    conn.executemany("INSERT INTO balances_sp500 (ticker, actualizado_en) VALUES (?, ?)",
                     [(t, ahora.isoformat()) for t in nueva])
    return set(nueva), None


# ---------------------------------------------------------------------------
# Armar la lista
# ---------------------------------------------------------------------------

def _item(f: FilaCalendario, grupo: str) -> dict:
    return {"ticker": f.ticker, "nombre": f.nombre, "fecha": f.fecha.isoformat(),
            "momento": f.momento, "capitalizacion": f.capitalizacion, "grupo": grupo}


def elegir(filas: list[FilaCalendario], sp: Optional[set[str]]) -> tuple[list[dict], int]:
    """(items numerados, cuántos van en el mensaje). Puro.

    Orden: la lista de Franco por fecha; las 15 más grandes del S&P 500 (por
    capitalización, fuera de su lista) por fecha; el resto del S&P, por fecha.
    """
    unicas: dict[str, FilaCalendario] = {}
    for f in filas:
        unicas.setdefault(f.ticker, f)        # si Nasdaq repite un ticker, vale la primera fecha
    mias_canon = {ticker_canonico(t) for t in MI_LISTA}

    def por_fecha(f: FilaCalendario):
        return (f.fecha, _ORDEN_MOMENTO[f.momento], -(f.capitalizacion or 0), f.ticker)

    mias = sorted((f for f in unicas.values() if f.ticker in mias_canon), key=por_fecha)
    # Una empresa con dos clases de acciones (GOOGL y GOOG, FOX y FOXA, NWS y
    # NWSA) es un solo balance: Nasdaq las trae con el mismo nombre. Va una.
    vistas = {f.nombre.lower() for f in mias if f.nombre}
    del_sp = []
    candidatas = [f for f in unicas.values()
                  if sp and f.ticker in sp and f.ticker not in mias_canon]
    for f in sorted(candidatas, key=lambda f: (-(f.capitalizacion or 0), f.ticker)):
        if f.nombre and f.nombre.lower() in vistas:
            continue
        vistas.add(f.nombre.lower())
        del_sp.append(f)
    grandes = sorted(del_sp[:CANTIDAD_GRANDES], key=por_fecha)
    resto = sorted(del_sp[CANTIDAD_GRANDES:], key=por_fecha)

    items = ([_item(f, "mia") for f in mias] + [_item(f, "grande") for f in grandes]
             + [_item(f, "resto") for f in resto])
    for n, it in enumerate(items, 1):
        it["n"] = n
    return items, len(mias) + len(grandes)


def _renglon(it: dict) -> str:
    return f"{it['n']}. {it['ticker']} — {_dia(date.fromisoformat(it['fecha']))}, " \
           f"{_MOMENTO[it['momento']]}"


def texto_lista(items: list[dict], principales: int, lunes: date,
                aviso: Optional[str]) -> str:
    viernes = lunes + timedelta(days=4)
    cabeza = f"📊 *Balances de la semana* ({lunes:%d/%m} al {viernes:%d/%m})"
    if not items:
        cuerpo = [cabeza, "", "Ninguna de tu lista ni de las grandes del S&P 500 presenta "
                              "balance esta semana."]
        if aviso:
            cuerpo += ["", aviso]
        return "\n".join(cuerpo)
    mias = [it for it in items if it["grupo"] == "mia"]
    grandes = [it for it in items if it["grupo"] == "grande"]
    resto = len(items) - principales
    lineas = [cabeza, "", "*Tu lista*"]
    lineas += [_renglon(it) for it in mias] or ["Ninguna presenta esta semana."]
    lineas += ["", "*S&P 500, las más grandes*"]
    if aviso:
        lineas.append(aviso)
    else:
        lineas += [_renglon(it) for it in grandes] or ["Ninguna presenta esta semana."]
    lineas += ["", "¿Cuáles agendo? Contestá con los números (*1 3 7*), los tickers "
                   "(*KO MSFT*), *todas* (las de este mensaje) o *ninguna*."]
    if resto:
        lineas.append(f"*balances todas* muestra las otras {resto} del S&P 500.")
    return "\n".join(lineas)


def texto_resto(prop: Propuesta) -> str:
    resto = prop.items[prop.principales:]
    if not resto:
        return "No hay más: la lista de esta semana ya estaba entera."
    viernes = prop.lunes + timedelta(days=4)
    lineas = [f"📊 Las otras {len(resto)} del S&P 500 ({prop.lunes:%d/%m} al {viernes:%d/%m})",
              ""]
    lineas += [_renglon(it) for it in resto]
    lineas += ["", "Contestá con los números o los tickers que querés agendar."]
    return "\n".join(lineas)


def armar(conn: sqlite3.Connection, *, workspace_id: int, lunes: date, fuentes: Any,
          ahora: datetime) -> str:
    """Trae la semana, guarda la propuesta (reemplaza la lista anterior) y la devuelve en texto.

    Si la lista anterior era de la misma semana (Franco mandó `balances` el
    domingo a las 19 y a las 20 llegó la del disparador), lo que ya había
    elegido pasa a la nueva, si sigue en el calendario. `CalendarioNoDisponible`
    sale tal cual: sin calendario no hay lista.
    """
    filas = fuentes.calendario(lunes, lunes + timedelta(days=4))
    sp, aviso = sp500(conn, fuentes, ahora)
    items, principales = elegir(filas, sp)
    anterior = vigente(conn, workspace_id=workspace_id, ahora=ahora)
    en_la_lista = {it["ticker"] for it in items}
    elegidos = ([t for t in anterior.elegidos if t in en_la_lista]
                if anterior and anterior.lunes == lunes else [])
    conn.execute("UPDATE balances_propuestas SET estado = 'reemplazada' "
                 "WHERE workspace_id = ? AND estado = 'vigente'", (workspace_id,))
    if items:
        conn.execute(
            "INSERT INTO balances_propuestas (workspace_id, lunes, items, principales, elegidos, "
            "estado, creado_en, vence_en) VALUES (?, ?, ?, ?, ?, 'vigente', ?, ?)",
            (workspace_id, lunes.isoformat(), json.dumps(items), principales,
             json.dumps(elegidos), ahora.isoformat(), _vence(lunes).isoformat()))
    return texto_lista(items, principales, lunes, aviso)


def vigente(conn: sqlite3.Connection, *, workspace_id: int, ahora: datetime
            ) -> Optional[Propuesta]:
    row = conn.execute(
        "SELECT * FROM balances_propuestas WHERE workspace_id = ? AND estado = 'vigente' "
        "AND vence_en > ? ORDER BY id DESC LIMIT 1",
        (workspace_id, ahora.isoformat())).fetchone()
    if row is None:
        return None
    return Propuesta(id=row["id"], lunes=date.fromisoformat(row["lunes"]),
                     items=json.loads(row["items"]), principales=row["principales"],
                     elegidos=json.loads(row["elegidos"]))


# ---------------------------------------------------------------------------
# La respuesta de Franco
# ---------------------------------------------------------------------------

_RE_SEPARADOR = re.compile(r"[\s,;]+")
TODAS = {"todas", "todos"}
NINGUNA = {"ninguna", "ninguno", "nada"}


def _normalizar(s: str) -> str:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return " ".join(sin_acentos.lower().split())


def leer_respuesta(texto: str, prop: Propuesta) -> Optional[Eleccion]:
    """¿El mensaje elige de la lista? None si es otra cosa (un gasto, `agenda`).

    Contesta si es `todas`, `ninguna`, o una lista de números **de la lista** y
    tickers **de la lista**, separados por espacios o comas. Puede empezar con
    `balances` (sirve para desempatar con un lote abierto). Un número solo que
    no está en la lista (`1500`) no contesta: sigue siendo un gasto.
    """
    clave = _normalizar(texto).strip(" .!¡?¿")
    explicita = clave.startswith("balances ")
    if explicita:
        clave = clave.removeprefix("balances ").strip()
    if clave in TODAS:
        return Eleccion(todas=True, explicita=explicita)
    if clave in NINGUNA:
        return Eleccion(ninguna=True, explicita=explicita)
    tokens = [t for t in _RE_SEPARADOR.split(clave) if t]
    if not tokens:
        return None
    de_la_lista = {it["ticker"] for it in prop.items}
    numeros, tickers = [], []
    for t in tokens:
        if t.isdigit():
            if not 1 <= int(t) <= len(prop.items):
                return None
            numeros.append(int(t))
        elif ticker_canonico(t) in de_la_lista:
            tickers.append(ticker_canonico(t))
        else:
            return None
    return Eleccion(numeros=tuple(numeros), tickers=tuple(tickers), explicita=explicita)


def _nombre(it: dict) -> str:
    return f"{it['ticker']} ({_dia(date.fromisoformat(it['fecha']))}, {_MOMENTO[it['momento']]})"


def responder(conn: sqlite3.Connection, prop: Propuesta, e: Eleccion, hoy: date) -> str:
    """Anota lo elegido (se suma a lo de antes). Lo de un día que ya pasó no se toma."""
    if e.ninguna:
        if prop.elegidos:
            return ("Listo, no sumo ninguna más. Lo que ya habías elegido sigue anotado: "
                    + ", ".join(prop.elegidos) + ".")
        return "Listo, esta semana no agendo ninguna."
    por_ticker = {it["ticker"]: it for it in prop.items}
    if e.todas:
        seleccion = prop.items[:prop.principales]
    else:
        seleccion = []
        for it in [prop.items[n - 1] for n in e.numeros] + [por_ticker[t] for t in e.tickers]:
            if it not in seleccion:
                seleccion.append(it)
    pasaron = [it for it in seleccion if date.fromisoformat(it["fecha"]) < hoy]
    ya_estaban = [it for it in seleccion if it not in pasaron and it["ticker"] in prop.elegidos]
    nuevas = [it for it in seleccion if it not in pasaron and it not in ya_estaban]

    elegidos = prop.elegidos + [it["ticker"] for it in nuevas]
    conn.execute("UPDATE balances_propuestas SET elegidos = ? WHERE id = ?",
                 (json.dumps(elegidos), prop.id))
    prop.elegidos = elegidos

    partes = []
    if nuevas:
        partes.append("✅ Anotado: " + ", ".join(_nombre(it) for it in nuevas) + ".")
    if ya_estaban:
        partes.append("Ya las tenías: " + ", ".join(it["ticker"] for it in ya_estaban) + ".")
    if pasaron:
        partes.append("No las agendo porque ya pasaron: "
                      + ", ".join(_nombre(it) for it in pasaron) + ".")
    if nuevas:
        partes.append("(Por ahora quedan anotadas: el agendado en tu Calendar llega en el "
                      "próximo paso. Ojo: *deshacer* todavía no las saca; borraría lo último "
                      "que cargaste de gastos.)")
    return "\n".join(partes)
