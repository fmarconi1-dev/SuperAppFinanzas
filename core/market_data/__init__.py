"""Datos de mercado: MEP histórico y precios de valuación.

Capa por proveedor + caché + override manual (`docs/DATOS-MERCADO-ARG.md`).
Fuentes actuales: `argentinadatos` para el MEP histórico (ADR-0004),
`data912` para el mercado argentino y `yahoo` para BTC / activos del exterior.

Todas las funciones aceptan un `fetch` inyectable: los tests corren sin red.
"""

from __future__ import annotations

from .mep import (
    TICKER_MEP,
    cargar_serie_desde_cache,
    guardar_serie_en_cache,
    mep_para_fecha,
    obtener_serie_mep,
    serie_mep_con_fallback,
    set_override_mep,
)
from .precios import (
    guardar_precio_en_cache,
    leer_precio_cache,
    leer_precio_mas_reciente,
    precio_yahoo,
    precios_arg,
    resolver_precio,
    set_override_precio,
)

__all__ = [
    "TICKER_MEP",
    "cargar_serie_desde_cache",
    "guardar_serie_en_cache",
    "mep_para_fecha",
    "obtener_serie_mep",
    "serie_mep_con_fallback",
    "set_override_mep",
    "guardar_precio_en_cache",
    "leer_precio_cache",
    "leer_precio_mas_reciente",
    "precio_yahoo",
    "precios_arg",
    "resolver_precio",
    "set_override_precio",
]
