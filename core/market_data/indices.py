"""Series históricas de índices, para comparar la cartera contra un benchmark.

**La pregunta que responde.** *"¿Me fue mejor o peor que el mercado?"* — que no
se contesta comparando el rendimiento acumulado de la cartera contra el del
índice, porque Franco no puso toda la plata el primer día: aportó en 24
momentos distintos y el índice no. La pregunta honesta es **money-weighted**:

> *Si hubieras puesto la misma plata, en las mismas fechas, en SPY,
> ¿cuánto tendrías hoy?*

Este módulo trae la materia prima (la serie del índice). La simulación de los
aportes vive en `places/inversiones/cartera/benchmark.py`, que es donde está el
dominio de la cartera.

---

## Tres decisiones que definen los números

**1. Se usa `adjclose`, no `close`.** El cierre ajustado incorpora los
dividendos reinvertidos. SPY rinde ~1,3% anual en dividendos: comparar el
rendimiento *total* de Franco (que sí cobra sus dividendos, y la app los cuenta
en `rendimientos.py`) contra el SPY *sin* dividendos le regalaría varios puntos
a la cartera en una comparación que se supone justa.

**2. El día que no cotiza toma el cierre anterior, y hay tope.** Un depósito
puede caer sábado, domingo o feriado. Se usa el último cierre disponible hacia
atrás, con un límite de `DIAS_ATRAS` días: si hay que retroceder más que eso,
el dato no está y **se dice**, no se estira. Estirar sin tope convertiría un
hueco de seis meses en la serie en un precio con aspecto de bueno.

**3. Se cachea en `cartera_precios_cache`, la tabla que ya existe.** Un cierre
de índice es exactamente lo que esa tabla guarda: ticker, fecha, precio,
moneda, fuente. **No hace falta una migración nueva** — y el repo pide que las
migraciones sean siempre aditivas justamente para no tener que inventar una
cada vez que aparece un dato con la misma forma que otro.

Sin red en tests: `fetch` inyectable, como el resto de `core/market_data/`.
"""

from __future__ import annotations

import json
import urllib.parse
from datetime import date, datetime, timedelta

__all__ = [
    "INDICES", "URL_YAHOO", "DIAS_ATRAS",
    "serie_historica", "guardar_serie", "cargar_serie",
    "serie_con_fallback", "valor_en",
]

#: Los benchmarks que ofrece la app: ``clave -> (símbolo Yahoo, moneda)``.
#:
#: La moneda **no es decorativa**: define contra qué flujos se compara. SPY
#: cotiza en dólares y se compara contra los aportes en USD; el Merval cotiza
#: en pesos y se compara contra los aportes en ARS. Cruzarlos reproduciría la
#: trampa nº 1 del proyecto (mezclar monedas infla el resultado con la
#: devaluación).
INDICES = {
    "SPY": ("SPY", "USD"),
    "MERVAL": ("^MERV", "ARS"),
}

URL_YAHOO = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?range={rango}&interval=1d"
)

#: Cuántos días se puede retroceder para encontrar un cierre. Diez cubre
#: cualquier fin de semana largo o feriado bursátil encadenado sin llegar a
#: tapar un hueco real de la serie.
DIAS_ATRAS = 10


def _fetch_http(url: str) -> str:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "SuperAppFinanzas/1.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8")


def _cargar(crudo):
    return json.loads(crudo) if isinstance(crudo, (str, bytes)) else crudo


def _a_date(f) -> date | None:
    if isinstance(f, datetime):
        return f.date()
    if isinstance(f, date):
        return f
    try:
        return datetime.strptime(str(f)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Proveedor
# ---------------------------------------------------------------------------

def serie_historica(clave: str, fetch=None, rango: str = "10y") -> dict[str, float]:
    """``{fecha_iso: cierre_ajustado}`` del índice. ``{}`` si la fuente falla.

    **Nunca lanza**: un proveedor caído no puede tumbar la pantalla de Cartera
    (misma regla que `precios.py` y `cronogramas.py`). El caller decide si
    sirve la caché.
    """
    simbolo = INDICES.get(str(clave).upper(), (clave, None))[0]
    url = URL_YAHOO.format(symbol=urllib.parse.quote(simbolo, safe=""),
                           rango=rango)
    try:
        datos = _cargar((fetch or _fetch_http)(url))
        r = datos["chart"]["result"][0]
        stamps = r["timestamp"]
        ind = r["indicators"]
        # `adjclose` incluye dividendos reinvertidos; `close` es el fallback
        # cuando Yahoo no lo sirve (algunos índices no pagan dividendos y no
        # traen la serie ajustada).
        try:
            cierres = ind["adjclose"][0]["adjclose"]
        except (KeyError, IndexError, TypeError):
            cierres = ind["quote"][0]["close"]
    except Exception:
        return {}

    out: dict[str, float] = {}
    for ts, precio in zip(stamps or [], cierres or []):
        if not isinstance(precio, (int, float)) or precio <= 0:
            continue          # Yahoo mete `null` en los días sin operar
        try:
            out[datetime.utcfromtimestamp(ts).date().isoformat()] = float(precio)
        except (OSError, OverflowError, ValueError):
            continue
    return out


# ---------------------------------------------------------------------------
# Caché (reusa `cartera_precios_cache`)
# ---------------------------------------------------------------------------

def guardar_serie(conn, clave: str, serie: dict[str, float]) -> int:
    """Guarda la serie en la caché de precios. Devuelve cuántas filas escribió.

    Usa `precios.guardar_precio_en_cache`, que **no pisa overrides manuales**:
    si alguien fijó a mano el cierre de un día, sigue mandando.
    """
    from .precios import guardar_precio_en_cache

    ticker, moneda = INDICES.get(str(clave).upper(), (clave, "USD"))
    n = 0
    for iso, precio in (serie or {}).items():
        try:
            guardar_precio_en_cache(conn, ticker, precio, iso,
                                    moneda or "USD", fuente="yahoo")
            n += 1
        except Exception:
            continue
    return n


def cargar_serie(conn, clave: str) -> dict[str, float]:
    """La serie que haya en caché. ``{}`` si no hay nada (o no existe la tabla)."""
    ticker, moneda = INDICES.get(str(clave).upper(), (clave, "USD"))
    try:
        filas = conn.execute(
            "SELECT fecha, precio FROM cartera_precios_cache "
            "WHERE ticker = ? AND moneda = ? ORDER BY fecha",
            (ticker, moneda or "USD"),
        ).fetchall()
    except Exception:
        return {}
    return {str(r["fecha"])[:10]: float(r["precio"]) for r in filas
            if r["precio"] is not None}


def serie_con_fallback(conn, clave: str, fetch=None,
                       rango: str = "10y") -> tuple[dict[str, float], str]:
    """``(serie, origen)`` con ``origen`` ``"proveedor"`` | ``"cache"``.

    Intenta el proveedor y refresca la caché; si vuelve vacío, sirve lo
    guardado. Misma política que `mep.serie_mep_con_fallback`.
    """
    serie = serie_historica(clave, fetch, rango)
    if serie:
        try:
            guardar_serie(conn, clave, serie)
        except Exception:
            pass                    # cachear es una mejora, no un requisito
        return serie, "proveedor"
    return cargar_serie(conn, clave), "cache"


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def valor_en(serie: dict[str, float], fecha,
             dias_atras: int = DIAS_ATRAS) -> float | None:
    """El cierre de `fecha`, o el del último día hábil anterior.

    Devuelve ``None`` si hay que retroceder más de `dias_atras` días: eso ya
    no es "el finde", es un hueco de la serie, y estirarlo daría un precio con
    apariencia de dato bueno. Devolver ``None`` obliga al caller a decir que
    ese flujo no se pudo comparar.
    """
    f = _a_date(fecha)
    if f is None or not serie:
        return None
    for i in range(dias_atras + 1):
        precio = serie.get((f - timedelta(days=i)).isoformat())
        if isinstance(precio, (int, float)) and precio > 0:
            return float(precio)
    return None
