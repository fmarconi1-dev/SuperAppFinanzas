"""Precios de valuación: proveedores ARG (data912) y globales (yahoo).

Capa por proveedor + caché + override manual, según `docs/DATOS-MERCADO-ARG.md`
(las APIs comunitarias pueden cortar sin aviso: nada de "tiempo real" sin
resguardo).

Precedencia al resolver un precio (`resolver_precio`):

    1. **override manual** (`es_override=1` en `cartera_precios_cache`)
    2. **caché** de esa fecha
    3. **proveedor** (y se cachea lo que llega)

Normalización: `data912` sirve los bonos/letras **por cada 100 nominales**
(AE38 = 127.360 donde el broker muestra 1.262,6). Los instrumentos cuya
`moneda_cotiz` termina en ``/100`` se dividen por 100 — misma regla que el
LEEME del Excel.

Sin red en tests: todas las funciones toman un ``fetch`` inyectable.
"""

from __future__ import annotations

import json
from datetime import date, datetime

__all__ = [
    "PANELES_ARG",
    "URL_YAHOO",
    "precios_arg",
    "precio_yahoo",
    "guardar_precio_en_cache",
    "set_override_precio",
    "leer_precio_cache",
    "leer_precio_mas_reciente",
    "resolver_precio",
]

#: Paneles de data912 que cubren la cartera (acciones, CEDEARs, renta fija).
PANELES_ARG = ("arg_stocks", "arg_cedears", "arg_bonds")

_URL_DATA912 = "https://data912.com/live/{panel}"
URL_YAHOO = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?range=1d&interval=1d"
)


def _fetch_http(url: str) -> str:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "SuperAppFinanzas/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8")


def _cargar(crudo):
    return json.loads(crudo) if isinstance(crudo, (str, bytes)) else crudo


def _hoy(fecha=None) -> str:
    if fecha is None:
        return date.today().isoformat()
    if isinstance(fecha, datetime):
        return fecha.date().isoformat()
    if isinstance(fecha, date):
        return fecha.isoformat()
    return str(fecha)[:10]


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------

def precios_arg(fetch=None, paneles=PANELES_ARG) -> dict[str, float]:
    """Últimos precios del mercado argentino: ``{symbol: precio}``.

    Recorre los paneles de data912 y toma el cierre (`c`); si viene en 0 o
    ausente, cae al mid entre punta compradora y vendedora. Un panel caído no
    tumba a los demás.
    """
    f = fetch or _fetch_http
    out: dict[str, float] = {}
    for panel in paneles:
        try:
            datos = _cargar(f(_URL_DATA912.format(panel=panel)))
        except Exception:
            continue
        for fila in datos or []:
            symbol = str(fila.get("symbol", "")).strip()
            if not symbol:
                continue
            precio = fila.get("c")
            if not isinstance(precio, (int, float)) or precio <= 0:
                bid, ask = fila.get("px_bid"), fila.get("px_ask")
                if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and bid > 0 < ask:
                    precio = (bid + ask) / 2
                else:
                    continue
            out[symbol] = float(precio)
    return out


def precio_yahoo(symbol: str, fetch=None) -> float | None:
    """Último precio de Yahoo Finance (CEDEARs del exterior, BTC).

    Devuelve ``None`` si la respuesta no trae precio (símbolo inexistente,
    fuente caída): el caller decide el fallback.
    """
    try:
        datos = _cargar((fetch or _fetch_http)(URL_YAHOO.format(symbol=symbol)))
        meta = datos["chart"]["result"][0]["meta"]
        precio = meta.get("regularMarketPrice")
        return float(precio) if isinstance(precio, (int, float)) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Caché / override
# ---------------------------------------------------------------------------

def guardar_precio_en_cache(
    conn, ticker: str, precio: float, fecha=None, moneda: str = "ARS",
    fuente: str = "data912",
) -> None:
    """Cachea un precio. **No pisa** un override manual de esa fecha."""
    conn.execute(
        "INSERT INTO cartera_precios_cache "
        "(ticker, fecha, precio, moneda, fuente, es_override) "
        "VALUES (?, ?, ?, ?, ?, 0) "
        "ON CONFLICT(ticker, fecha, moneda) DO UPDATE SET "
        "  precio = excluded.precio, fuente = excluded.fuente, "
        "  actualizado_en = datetime('now') "
        "WHERE cartera_precios_cache.es_override = 0",
        (ticker, _hoy(fecha), float(precio), moneda, fuente),
    )


def set_override_precio(
    conn, ticker: str, precio: float, fecha=None, moneda: str = "ARS"
) -> None:
    """Precio manual (fallback si la fuente se cae, o corrección puntual)."""
    conn.execute(
        "INSERT INTO cartera_precios_cache "
        "(ticker, fecha, precio, moneda, fuente, es_override) "
        "VALUES (?, ?, ?, ?, 'manual', 1) "
        "ON CONFLICT(ticker, fecha, moneda) DO UPDATE SET "
        "  precio = excluded.precio, fuente = 'manual', es_override = 1, "
        "  actualizado_en = datetime('now')",
        (ticker, _hoy(fecha), float(precio), moneda),
    )


def leer_precio_cache(conn, ticker: str, fecha=None, moneda: str = "ARS"):
    """Devuelve ``(precio, es_override)`` o ``None`` si no está cacheado."""
    row = conn.execute(
        "SELECT precio, es_override FROM cartera_precios_cache "
        "WHERE ticker = ? AND fecha = ? AND moneda = ?",
        (ticker, _hoy(fecha), moneda),
    ).fetchone()
    if row is None:
        return None
    return float(row["precio"]), bool(row["es_override"])


def leer_precio_mas_reciente(conn, ticker: str, moneda: str = "ARS"):
    """Último precio conocido del ticker, sin importar la fecha.

    Red de contención para instrumentos **ilíquidos**: un pagaré o un cheque
    no cotiza en ningún panel, así que su único precio es el que informó el
    broker en su última tenencia. Sin esto, al caducar esa foto la posición
    quedaba sin valuar y desaparecía del patrimonio.

    Devuelve ``(precio, fecha)`` o ``None``.
    """
    row = conn.execute(
        "SELECT precio, fecha FROM cartera_precios_cache "
        "WHERE ticker = ? AND moneda = ? ORDER BY fecha DESC LIMIT 1",
        (ticker, moneda),
    ).fetchone()
    if row is None:
        return None
    return float(row["precio"]), row["fecha"]


def resolver_precio(
    conn, ticker: str, fecha=None, moneda: str = "ARS",
    precios_proveedor: dict[str, float] | None = None,
    divide_por_100: bool = False,
) -> tuple[float | None, str]:
    """Precio de `ticker` aplicando override → caché → proveedor.

    `precios_proveedor` es el dict ya traído por `precios_arg()` (se pasa una
    sola vez para no pegarle a la API por cada ticker). Devuelve
    ``(precio, origen)`` con origen ``"override" | "cache" | "proveedor"`` o
    ``(None, "sin_dato")``.
    """
    cacheado = leer_precio_cache(conn, ticker, fecha, moneda)
    if cacheado is not None and cacheado[1]:
        return cacheado[0], "override"

    if precios_proveedor:
        crudo = precios_proveedor.get(ticker)
        if isinstance(crudo, (int, float)) and crudo > 0:
            precio = crudo / 100.0 if divide_por_100 else float(crudo)
            guardar_precio_en_cache(conn, ticker, precio, fecha, moneda)
            return precio, "proveedor"

    if cacheado is not None:
        return cacheado[0], "cache"
    return None, "sin_dato"
