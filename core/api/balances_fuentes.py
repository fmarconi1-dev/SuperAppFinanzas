"""Fuentes de los balances de la semana (ADR-0011): el calendario, el S&P 500 y los precios.

Las fechas salen de una fuente de datos, nunca de un LLM. Verificadas el 20/10/2026:

* **Nasdaq** (`api.nasdaq.com/api/calendar/earnings?date=AAAA-MM-DD`, sin
  clave). Es la API que usa su propia página; Franco la aceptó como fuente el
  21/10/2026. Sin un User-Agent de navegador no contesta. Trae `time`
  (`time-pre-market` / `time-after-hours` / `time-not-supplied`) y `marketCap`.
  Un fin de semana o un feriado viene con `rows: null`. **Una vez que la fecha
  pasa, pierde el antes/después**: por eso se guarda al agendar.
* **Nasdaq, la ficha de cada empresa** (`api/analyst/{TICKER}/earnings-date`):
  dice **en prosa** si la fecha la confirmó la empresa ("is expected* to report
  earnings on 11/04/2026 before market open") o es una estimación por algoritmo
  ("is estimated to report earnings on 11/02/2026"). A veces trae el momento
  aunque el calendario diga `time-not-supplied` (MCD, 21/10/2026). Se consulta
  al agendar, solo para las elegidas.
* **Wikipedia** (`List_of_S&P_500_companies`, tabla `constituents`): la lista
  del S&P 500. Se refresca una vez por mes (eso lo decide quien la usa).
* **Yahoo** (`chart`): el cierre y el posmercado del día del balance, para el
  resumen del día (la reacción del precio).

Si una fuente no contesta: `CalendarioNoDisponible`, `ListaNoDisponible` o
`PrecioNoDisponible`, con el motivo. Nunca una lista vacía ni un número viejo
en silencio ("No contestó" ≠ "no existe").
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import unescape
from typing import Optional
from zoneinfo import ZoneInfo

#: Constantes del módulo (no del entorno) para que los tests apunten a fuentes
#: de mentira locales.
NASDAQ_BASE = "https://api.nasdaq.com/api"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

TIMEOUT = 20
#: Nasdaq no contesta sin un User-Agent de navegador.
UA_NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
#: Wikipedia pide un User-Agent que diga quién pregunta.
UA_WIKIPEDIA = "SecretarioFranco/1.0 (uso personal; lista del S&P 500 una vez por mes)"

#: Cuántos tickers tiene que tener la tabla para creerle (el S&P 500 tiene ~503).
MINIMO_SP500 = 450

_MOMENTOS = {"time-pre-market": "pre", "time-after-hours": "post"}


class CalendarioNoDisponible(Exception):
    """Nasdaq no contestó o contestó algo que no se entiende."""


class ListaNoDisponible(Exception):
    """Wikipedia no contestó o la tabla del S&P 500 no se pudo leer."""


@dataclass(frozen=True)
class FilaCalendario:
    ticker: str
    nombre: str
    fecha: date
    #: "pre" (antes de la apertura), "post" (después del cierre) o None (sin hora).
    momento: Optional[str]
    #: Capitalización en dólares, si Nasdaq la trae.
    capitalizacion: Optional[float]


@dataclass(frozen=True)
class FechaAnunciada:
    """Lo que dice la ficha de Nasdaq de una empresa sobre su próximo balance."""

    fecha: date
    momento: Optional[str]
    #: True si la fecha la calculó un algoritmo; False si la anunció la empresa.
    estimada: bool


def ticker_canonico(ticker: str) -> str:
    """`BRK.B`, `BRK-B` y `BRK/B` son el mismo: se comparan como `BRK.B`."""
    return re.sub(r"[/\-]", ".", ticker.strip().upper())


def _pedir(url: str, ua: str, error: type[Exception], fuente: str) -> object:
    pedido = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
            crudo = r.read()
    except urllib.error.HTTPError as e:
        raise error(f"{fuente} respondió HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise error(f"no pude hablar con {fuente} ({e})") from None
    try:
        return json.loads(crudo)
    except json.JSONDecodeError:
        raise error(f"{fuente} contestó algo que no es JSON") from None


# ---------------------------------------------------------------------------
# Calendario (Nasdaq)
# ---------------------------------------------------------------------------

def _capitalizacion(crudo: object) -> Optional[float]:
    """`"$1,797,112,860,000"` → 1.797112860e12. Vacío o `N/A` → None."""
    if not isinstance(crudo, str):
        return None
    limpio = crudo.replace("$", "").replace(",", "").strip()
    try:
        return float(limpio)
    except ValueError:
        return None


def calendario_del_dia(fecha: date) -> list[FilaCalendario]:
    """Las empresas que presentan balance ese día. Un día sin rueda da `[]`."""
    datos = _pedir(f"{NASDAQ_BASE}/calendar/earnings?date={fecha.isoformat()}",
                   UA_NAVEGADOR, CalendarioNoDisponible, "Nasdaq")
    cuerpo = datos.get("data") if isinstance(datos, dict) else None
    if not isinstance(cuerpo, dict):
        raise CalendarioNoDisponible(f"Nasdaq no trajo el calendario del {fecha:%d/%m}")
    filas = cuerpo.get("rows")
    if filas is None:
        return []                      # fin de semana o feriado: no hay nadie
    if not isinstance(filas, list):
        raise CalendarioNoDisponible(f"Nasdaq trajo el calendario del {fecha:%d/%m} roto")
    salida = []
    for f in filas:
        ticker = f.get("symbol") if isinstance(f, dict) else None
        if not isinstance(ticker, str) or not ticker.strip():
            continue                   # un renglón sin ticker no se puede elegir
        salida.append(FilaCalendario(
            ticker=ticker_canonico(ticker),
            nombre=" ".join(str(f.get("name") or "").split()),
            fecha=fecha,
            momento=_MOMENTOS.get(f.get("time")),
            capitalizacion=_capitalizacion(f.get("marketCap")),
        ))
    return salida


def calendario(desde: date, hasta: date) -> list[FilaCalendario]:
    """Del `desde` al `hasta` inclusive, salteando sábados y domingos."""
    filas: list[FilaCalendario] = []
    dia = desde
    while dia <= hasta:
        if dia.weekday() < 5:
            filas.extend(calendario_del_dia(dia))
        dia += timedelta(days=1)
    return filas


_RE_ANUNCIO = re.compile(
    r"is (expected\*?|estimated) to report earnings on\s+(\d{1,2})/(\d{1,2})/(\d{4})"
    r"(?:\s+(before market open|after market close))?", re.IGNORECASE)
_MOMENTO_TEXTO = {"before market open": "pre", "after market close": "post"}


def fecha_anunciada(ticker: str) -> Optional[FechaAnunciada]:
    """La próxima fecha de balance según la ficha de Nasdaq, o None si no la dice.

    None es "Nasdaq no tiene fecha para esa empresa" (contestó, pero sin el
    anuncio). Si Nasdaq no contesta: `CalendarioNoDisponible`.
    """
    simbolo = urllib.parse.quote(ticker_canonico(ticker), safe="")
    datos = _pedir(f"{NASDAQ_BASE}/analyst/{simbolo}/earnings-date",
                   UA_NAVEGADOR, CalendarioNoDisponible, "Nasdaq")
    cuerpo = datos.get("data") if isinstance(datos, dict) else None
    texto = cuerpo.get("reportText") if isinstance(cuerpo, dict) else None
    if not isinstance(texto, str):
        return None
    m = _RE_ANUNCIO.search(texto)
    if m is None:
        return None
    tipo, mes, dia, anio, momento = m.groups()
    try:
        fecha = date(int(anio), int(mes), int(dia))
    except ValueError:
        return None
    return FechaAnunciada(fecha=fecha, momento=_MOMENTO_TEXTO.get((momento or "").lower()),
                          estimada=tipo.lower() == "estimated")


# ---------------------------------------------------------------------------
# S&P 500 (Wikipedia)
# ---------------------------------------------------------------------------

_RE_FILA = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_RE_CELDA = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_RE_ETIQUETA = re.compile(r"<[^>]+>")
_RE_TICKER = re.compile(r"^[A-Z][A-Z0-9]*(?:[./\-][A-Z0-9]+)?$")


def lista_sp500() -> list[str]:
    """Los tickers del S&P 500, canónicos (`ticker_canonico`), sin repetir."""
    consulta = urllib.parse.urlencode({
        "action": "parse", "page": "List_of_S&P_500_companies", "prop": "text",
        "format": "json", "formatversion": "2",
    })
    datos = _pedir(f"{WIKIPEDIA_API}?{consulta}", UA_WIKIPEDIA, ListaNoDisponible, "Wikipedia")
    html = (datos.get("parse") or {}).get("text") if isinstance(datos, dict) else None
    if not isinstance(html, str):
        raise ListaNoDisponible("Wikipedia no trajo la página del S&P 500")
    inicio = html.find('id="constituents"')
    if inicio < 0:
        raise ListaNoDisponible("la página de Wikipedia ya no tiene la tabla 'constituents'")
    tabla = html[inicio:html.find("</table>", inicio)]
    tickers: list[str] = []
    for fila in _RE_FILA.findall(tabla):
        celdas = _RE_CELDA.findall(fila)
        if not celdas:
            continue                   # el encabezado tiene <th>, no <td>
        texto = unescape(_RE_ETIQUETA.sub("", celdas[0])).strip()
        if _RE_TICKER.match(texto):
            canonico = ticker_canonico(texto)
            if canonico not in tickers:
                tickers.append(canonico)
    if len(tickers) < MINIMO_SP500:
        raise ListaNoDisponible(
            f"la tabla de Wikipedia trajo {len(tickers)} tickers (espero unos 500)")
    return tickers


# ---------------------------------------------------------------------------
# Precios (Yahoo): la reacción del día del balance
# ---------------------------------------------------------------------------
#
# El `chart` de Yahoo (ya fuente probada en `Mercado.gs`, ADR-0010). Con
# `interval=1d` da los cierres oficiales; con `interval=5m&includePrePost=true`
# da las barras de cinco días con las ventanas `pre`/`regular`/`post` de cada
# día en `meta.tradingPeriods` (horario de Nueva York, con los feriados y los
# días de cierre temprano resueltos por Yahoo). Verificado el 21/10/2026: NFLX
# cerró el 20/10 en 68,69 y terminó el posmercado en 64,72.

YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
NUEVA_YORK = ZoneInfo("America/New_York")


class PrecioNoDisponible(Exception):
    """Yahoo no contestó, o no tiene el precio de ese día."""


def _simbolo_yahoo(ticker: str) -> str:
    """`BRK.B` → `BRK-B` (Yahoo usa guion para las clases)."""
    return urllib.parse.quote(ticker_canonico(ticker).replace(".", "-"), safe="-")


def _chart(ticker: str, consulta: str) -> dict:
    datos = _pedir(f"{YAHOO_BASE}/{_simbolo_yahoo(ticker)}?{consulta}", UA_NAVEGADOR,
                   PrecioNoDisponible, "Yahoo")
    try:
        return datos["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        raise PrecioNoDisponible(f"Yahoo no tiene {ticker}") from None


def _dia_ny(segundos: int) -> date:
    return datetime.fromtimestamp(segundos, NUEVA_YORK).date()


def cierres(ticker: str) -> dict[date, float]:
    """Los cierres oficiales de la rueda del último mes, por día (de Nueva York)."""
    r = _chart(ticker, "range=1mo&interval=1d")
    tiempos = r.get("timestamp") or []
    try:
        valores = r["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        raise PrecioNoDisponible(f"Yahoo trajo los cierres de {ticker} rotos") from None
    return {_dia_ny(t): float(v) for t, v in zip(tiempos, valores) if v is not None}


def ultimo_del_posmercado(ticker: str, fecha: date) -> float:
    """El último precio dentro del posmercado de `fecha` (16:00–20:00 de Nueva York).

    Se filtra por la ventana de **ese** día: a la mañana siguiente ya corre la
    pre-apertura del otro, y "el último precio" sería otra cosa.
    """
    r = _chart(ticker, "range=5d&interval=5m&includePrePost=true")
    ventanas = ((r.get("meta") or {}).get("tradingPeriods") or {}).get("post") or []
    ventana = next((v[0] for v in ventanas
                    if v and isinstance(v[0], dict) and _dia_ny(v[0]["start"]) == fecha), None)
    if ventana is None:
        raise PrecioNoDisponible(f"Yahoo no tiene el posmercado de {ticker} del {fecha:%d/%m}")
    try:
        valores = r["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        raise PrecioNoDisponible(f"Yahoo trajo las barras de {ticker} rotas") from None
    dentro = [v for t, v in zip(r.get("timestamp") or [], valores)
              if v is not None and ventana["start"] <= t < ventana["end"]]
    if not dentro:
        raise PrecioNoDisponible(f"{ticker} no operó en el posmercado del {fecha:%d/%m}")
    return float(dentro[-1])
