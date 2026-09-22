"""Serie histórica del dólar MEP (ADR-0004).

Fuente: `argentinadatos` (`/v1/cotizaciones/dolares/bolsa`). El BCRA **no**
publica el MEP (su serie es el mayorista A3500), por eso no se usa acá.

Resguardos exigidos por el repo para fuentes comunitarias:

  * **caché en DB** (`cartera_precios_cache`, ticker ``MEP``): si la API no
    responde, se sirve lo cacheado;
  * **override manual** (``es_override=1``): gana sobre cualquier proveedor;
  * **congelado por fila**: el TC se graba en `cartera_movimientos.tc_mep` al
    importar, así una caída futura de la API no altera lo ya importado.

Sin red en tests: todas las funciones aceptan un ``fetch`` inyectable
(mismo patrón que `places/inversiones/scoring/snapshot.py`).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

from core.market_data._errores import ERRORES_DE_RED

__all__ = [
    "URL_MEP",
    "TICKER_MEP",
    "obtener_serie_mep",
    "mep_para_fecha",
    "guardar_serie_en_cache",
    "cargar_serie_desde_cache",
    "set_override_mep",
]

URL_MEP = "https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa"

#: Pseudo-ticker con el que la serie MEP vive en `cartera_precios_cache`.
TICKER_MEP = "MEP"

#: Tope de días hacia atrás al buscar el último hábil con dato (cubre
#: fines de semana largos y feriados encadenados).
_MAX_DIAS_ATRAS = 10


def _fetch_http(url: str) -> str:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "SuperAppFinanzas/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8")


def obtener_serie_mep(fetch=None) -> dict[str, float]:
    """Descarga la serie MEP y la devuelve como ``{'YYYY-MM-DD': valor}``.

    Usa el precio de **venta** (el relevante para valuar tenencias). Lanza
    la excepción del `fetch` si la fuente falla — el fallback a caché lo
    decide el caller (ver `serie_mep_con_fallback`).
    """
    crudo = (fetch or _fetch_http)(URL_MEP)
    datos = json.loads(crudo) if isinstance(crudo, (str, bytes)) else crudo
    serie: dict[str, float] = {}
    for punto in datos:
        fecha = str(punto.get("fecha", "")).strip()
        valor = punto.get("venta", punto.get("compra"))
        if fecha and isinstance(valor, (int, float)):
            serie[fecha] = float(valor)
    return serie


def _a_date(f) -> date:
    if isinstance(f, datetime):
        return f.date()
    if isinstance(f, date):
        return f
    return datetime.strptime(str(f)[:10], "%Y-%m-%d").date()


def mep_para_fecha(serie: dict[str, float], fecha) -> float | None:
    """MEP de `fecha`; si no hay dato (finde/feriado), el último hábil anterior.

    Devuelve ``None`` si no hay ningún dato dentro de la ventana de búsqueda
    (p. ej. fechas previas al inicio de la serie).
    """
    if not serie:
        return None
    d = _a_date(fecha)
    for _ in range(_MAX_DIAS_ATRAS + 1):
        valor = serie.get(d.isoformat())
        if valor is not None:
            return valor
        d -= timedelta(days=1)
    return None


# ---------------------------------------------------------------------------
# Caché en DB
# ---------------------------------------------------------------------------

def guardar_serie_en_cache(conn, serie: dict[str, float], fuente: str = "argentinadatos") -> int:
    """Persiste la serie en `cartera_precios_cache` (no pisa overrides).

    Devuelve la cantidad de fechas escritas. No hace commit.
    """
    n = 0
    for fecha, valor in serie.items():
        conn.execute(
            "INSERT INTO cartera_precios_cache "
            "(ticker, fecha, precio, moneda, fuente, es_override) "
            "VALUES (?, ?, ?, 'ARS', ?, 0) "
            "ON CONFLICT(ticker, fecha, moneda) DO UPDATE SET "
            "  precio = excluded.precio, fuente = excluded.fuente, "
            "  actualizado_en = datetime('now') "
            "WHERE cartera_precios_cache.es_override = 0",
            (TICKER_MEP, fecha, float(valor), fuente),
        )
        n += 1
    return n


def cargar_serie_desde_cache(conn) -> dict[str, float]:
    """Lee la serie MEP cacheada (incluye overrides manuales)."""
    filas = conn.execute(
        "SELECT fecha, precio FROM cartera_precios_cache "
        "WHERE ticker = ? AND moneda = 'ARS'",
        (TICKER_MEP,),
    )
    return {r["fecha"]: float(r["precio"]) for r in filas}


def set_override_mep(conn, fecha, valor: float) -> None:
    """Fija a mano el MEP de una fecha. Gana sobre el proveedor."""
    conn.execute(
        "INSERT INTO cartera_precios_cache "
        "(ticker, fecha, precio, moneda, fuente, es_override) "
        "VALUES (?, ?, ?, 'ARS', 'manual', 1) "
        "ON CONFLICT(ticker, fecha, moneda) DO UPDATE SET "
        "  precio = excluded.precio, fuente = 'manual', es_override = 1, "
        "  actualizado_en = datetime('now')",
        (TICKER_MEP, _a_date(fecha).isoformat(), float(valor)),
    )


def serie_mep_con_fallback(conn, fetch=None) -> tuple[dict[str, float], str]:
    """Serie MEP lista para usar, con la política completa de resguardo.

    Intenta el proveedor y refresca la caché; si falla, sirve la caché.
    Devuelve ``(serie, origen)`` con origen ``"proveedor"`` | ``"cache"``.
    Los overrides manuales siempre pisan al proveedor.
    """
    # Solo la fuente caída, una respuesta con otra forma o la base ocupada caen
    # a la caché. Un bug nuestro se ve (trampa 36; antes `except Exception`).
    try:
        serie = obtener_serie_mep(fetch)
        if not serie:
            raise ValueError("serie vacía")
        guardar_serie_en_cache(conn, serie)
        origen = "proveedor"
    except ERRORES_DE_RED + (KeyError, TypeError, AttributeError,
                             sqlite3.OperationalError):
        serie, origen = {}, "cache"
    # La caché ya incluye lo recién guardado + los overrides manuales.
    cacheada = cargar_serie_desde_cache(conn)
    if cacheada:
        serie = {**serie, **cacheada}
    return serie, origen
