"""Cuándo vence cada instrumento de renta fija.

**De dónde sale el dato.** No hubo que cargar nada: las fechas ya estaban en tu
cartera, escondidas en la descripción que trae la hoja `Config` del Excel —
`"Bono Tesoro Nacional Vto. 30/11/2029"`, `"Letra Tesoro Vto. 17/04/2026"`,
`"ON MSU Energy Vto. 05/12/2030"`. Este módulo las lee de ahí.

**Las tres calidades de dato, y por qué se distinguen.** Las descripciones no
son homogéneas:

* **Fecha completa** — `"Vto. 30/11/2029"`, `"Vto 30/06/2026"` (a veces sin el
  punto). Es el caso mayoritario y el único que permite contar días.
* **Solo el año** — `"Bono Tesoro Vto. 2028"`. Se sabe el año y nada más.
* **Nada** — `"Bono USD 2038"` tiene el año en el *nombre*, no como
  vencimiento; el pagaré `#UMV060770008` no tiene descripción con fecha.

**Nunca se inventa una fecha.** Un "31/12/2028" fabricado para un bono que dice
solo "2028" se ve idéntico a un dato real y contamina cualquier cuenta de días
que venga después. Por eso `precision` viaja junto a la fecha y la vista
muestra "2028", no "31/12/2028". Es la misma disciplina que el `estimado` de
los ajustes y el `s/d` del análisis por sector.

Lo que no tiene fecha se corrige a mano y queda en `cartera_vencimientos`
(M14), con la misma cascada probada en `cartera_sectores`: **el override manual
gana siempre** sobre lo parseado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

__all__ = [
    "Vencimiento", "CATEGORIAS_CON_VENCIMIENTO", "parse_vencimiento",
    "resolver", "set_override", "quitar_override", "proximos", "resumen",
]

#: Categorías de `Config` que vencen. Las acciones y los CEDEAR no vencen: no
#: es que les falte el dato, es que no aplica (misma distinción que en
#: `analisis.py` con el sector de un bono).
CATEGORIAS_CON_VENCIMIENTO = ("Bonos", "Letras", "ONs", "Pagarés", "Cheques")

#: `Vto. 30/11/2029`, `Vto 30/06/2026`, `Vencimiento 14/02/2025`.
_RE_FECHA = re.compile(
    r"v(?:to|cto|encimiento)\.?\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",
    re.IGNORECASE,
)
#: `Vto. 2028` — solo el año. **No** matchea `Bono USD 2038`, donde el año es
#: parte del nombre del bono y no dice cuándo vence.
_RE_ANIO = re.compile(r"v(?:to|cto|encimiento)\.?\s*(\d{4})\b", re.IGNORECASE)

#: Umbral de "esto te vence pronto". 90 días da tiempo a decidir la
#: reinversión sin que el aviso sea ruido permanente.
DIAS_PROXIMO = 90


@dataclass(frozen=True)
class Vencimiento:
    """La fecha de vencimiento de un instrumento, **con su calidad**."""

    ticker: str
    fecha: date | None
    #: ``"dia"`` | ``"anio"`` | ``"sin_dato"``. Determina qué se puede afirmar.
    precision: str = "sin_dato"
    #: ``"descripcion"`` | ``"manual"``.
    fuente: str = "descripcion"

    @property
    def es_exacto(self) -> bool:
        return self.precision == "dia"

    @property
    def etiqueta(self) -> str:
        """Cómo se muestra. **Nunca imprime un día que no se sabe.**"""
        if self.fecha is None:
            return "s/d"
        if self.precision == "anio":
            return str(self.fecha.year)
        return self.fecha.strftime("%d/%m/%Y")

    def dias_restantes(self, hoy: date | None = None) -> int | None:
        """Días hasta el vencimiento. ``None`` si la fecha no es exacta:
        contar días contra un año redondeado sería inventar precisión."""
        if self.fecha is None or self.precision != "dia":
            return None
        return (self.fecha - (hoy or date.today())).days

    def vencido(self, hoy: date | None = None) -> bool:
        d = self.dias_restantes(hoy)
        return d is not None and d < 0

    def proximo(self, hoy: date | None = None, dias: int = DIAS_PROXIMO) -> bool:
        d = self.dias_restantes(hoy)
        return d is not None and 0 <= d <= dias


# ---------------------------------------------------------------------------
# Parseo
# ---------------------------------------------------------------------------

def parse_vencimiento(descripcion: str | None) -> tuple[date | None, str]:
    """``(fecha, precision)`` desde la descripción del instrumento.

    Devuelve ``(None, "sin_dato")`` cuando no hay nada que leer — que es un
    resultado legítimo, no un error.
    """
    if not descripcion:
        return None, "sin_dato"
    texto = str(descripcion)

    m = _RE_FECHA.search(texto)
    if m:
        d, mes, a = (int(g) for g in m.groups())
        if a < 100:                      # "Vto. 30/06/26"
            a += 2000
        try:
            return date(a, mes, d), "dia"
        except ValueError:               # 31/02: dato malo, no se adivina
            return None, "sin_dato"

    m = _RE_ANIO.search(texto)
    if m:
        anio = int(m.group(1))
        if 1900 <= anio <= 2200:
            # Se guarda el 31/12 como ancla ordenable, pero `precision="anio"`
            # impide que alguien lo muestre o cuente días contra él.
            return date(anio, 12, 31), "anio"
    return None, "sin_dato"


# ---------------------------------------------------------------------------
# Overrides manuales (M14)
# ---------------------------------------------------------------------------

def set_override(conn, ticker: str, fecha: date) -> None:
    """Fija a mano el vencimiento de un ticker. Gana sobre lo parseado."""
    conn.execute(
        "INSERT INTO cartera_vencimientos (ticker, fecha, fuente, es_override) "
        "VALUES (?, ?, 'manual', 1) "
        "ON CONFLICT(ticker) DO UPDATE SET fecha = excluded.fecha, "
        "  fuente = 'manual', es_override = 1, actualizado_en = datetime('now')",
        (ticker.strip().upper(), fecha.isoformat()),
    )


def quitar_override(conn, ticker: str) -> bool:
    cur = conn.execute(
        "DELETE FROM cartera_vencimientos WHERE ticker = ? AND es_override = 1",
        (ticker.strip().upper(),),
    )
    return cur.rowcount > 0


def _overrides(conn) -> dict[str, date]:
    try:
        filas = conn.execute(
            "SELECT ticker, fecha FROM cartera_vencimientos WHERE es_override = 1"
        )
    except Exception:                    # base sin M14: no puede romper nada
        return {}
    out: dict[str, date] = {}
    for r in filas:
        try:
            out[r["ticker"]] = datetime.strptime(str(r["fecha"])[:10],
                                                 "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
    return out


# ---------------------------------------------------------------------------
# Resolución
# ---------------------------------------------------------------------------

def resolver(instrumentos: dict, conn=None) -> dict[str, Vencimiento]:
    """``{ticker: Vencimiento}`` para lo que vence.

    `instrumentos`: ``{ticker: obj}`` con `descripcion` y `categoria_activo`
    (los de `ingest.instrumentos_desde_config` o `_instrumentos_de_db`).

    Cascada: **override manual → descripción**. Los instrumentos que no vencen
    (acciones, CEDEAR, cripto) quedan fuera del resultado: a una acción no le
    *falta* el vencimiento, no tiene.
    """
    manual = _overrides(conn) if conn is not None else {}
    out: dict[str, Vencimiento] = {}

    for ticker, inst in (instrumentos or {}).items():
        categoria = getattr(inst, "categoria_activo", None) or ""
        es_pagare = str(ticker).startswith("#")
        if categoria not in CATEGORIAS_CON_VENCIMIENTO and not es_pagare:
            continue

        if ticker in manual:
            out[ticker] = Vencimiento(ticker, manual[ticker], "dia", "manual")
            continue

        fecha, precision = parse_vencimiento(getattr(inst, "descripcion", None))
        out[ticker] = Vencimiento(ticker, fecha, precision, "descripcion")

    return out


# ---------------------------------------------------------------------------
# Para la vista
# ---------------------------------------------------------------------------

def _por_ticker(valuadas) -> dict | None:
    """Normaliza las posiciones a ``{ticker: posicion}``.

    **Acepta lista o diccionario a propósito.** La vista maneja las posiciones
    valuadas como una **lista** y este módulo asumía un diccionario, así que
    `valuadas.get(...)` reventaba con
    ``AttributeError: 'list' object has no attribute 'get'`` — en producción,
    el 5/8/2026. Los tests no lo vieron porque estaban escritos contra la
    suposición del módulo y no contra el llamador real.
    """
    if valuadas is None:
        return None
    if isinstance(valuadas, dict):
        return valuadas
    return {getattr(p, "ticker", None): p for p in valuadas}


def proximos(vencs: dict, valuadas=None,
             hoy: date | None = None, incluir_vencidos: bool = False) -> list[dict]:
    """Filas listas para mostrar, **de lo que vence antes a lo que vence
    después**, y con lo que no tiene fecha al final.

    `valuadas`: ``{ticker: PosicionValuada}`` para poder decir *cuánta plata*
    vence, que es la pregunta real. Solo entran las posiciones **vivas**: un
    bono que ya vendiste no te vence.

    Vive acá y no en la vista para poder testearse sin Streamlit.
    """
    hoy = hoy or date.today()
    indexadas = _por_ticker(valuadas)
    filas: list[dict] = []

    for ticker, v in vencs.items():
        pos = (indexadas or {}).get(ticker)
        if indexadas is not None:
            if pos is None or getattr(pos, "cerrada", False):
                continue
            if not getattr(pos, "cant_actual", 0):
                continue
        if v.vencido(hoy) and not incluir_vencidos:
            continue

        dias = v.dias_restantes(hoy)
        filas.append({
            "Ticker": ticker,
            "Vence": v.etiqueta,
            "Días": dias,
            "Valor": getattr(pos, "valor_ars_actual", None) if pos else None,
            "US$": getattr(pos, "valor_usd_actual", None) if pos else None,
            "Fuente": "a mano" if v.fuente == "manual" else "",
            "_orden": v.fecha or date.max,
            "_exacto": v.es_exacto,
        })

    # Sin fecha al final: no se puede afirmar que vencen tarde, solo que no se
    # sabe. Mezclarlos con los ordenados sugeriría una precisión que no hay.
    filas.sort(key=lambda f: (f["_orden"] == date.max, f["_orden"]))
    return filas


def resumen(vencs: dict, valuadas=None,
            hoy: date | None = None, dias: int = DIAS_PROXIMO) -> dict:
    """Cuánto vence en los próximos `dias`, y qué falta resolver."""
    hoy = hoy or date.today()
    filas = proximos(vencs, valuadas, hoy)
    pronto = [f for f in filas if f["Días"] is not None and 0 <= f["Días"] <= dias]
    return {
        "n_total": len(filas),
        "n_proximos": len(pronto),
        "ars_proximos": sum(f["Valor"] or 0.0 for f in pronto),
        "usd_proximos": sum(f["US$"] or 0.0 for f in pronto),
        "sin_fecha": [f["Ticker"] for f in filas if f["Días"] is None],
        "proximo": min(pronto, key=lambda f: f["Días"]) if pronto else None,
    }
