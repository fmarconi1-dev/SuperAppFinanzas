"""El dólar oficial vendedor de una fecha, de una fuente pública gratuita (Fase D, paso 5).

Para cargar los consumos en dólares de las tarjetas ("Venta divisa" + el gasto,
al mismo precio, el día del pago) cuando ese día no hubo una compra de dólares
en la caja. Fuente: **ArgentinaDatos** (`api.argentinadatos.com`, gratis, sin
clave; ya es fuente del repo desde ADR-0004). Verificado el 20/10/2026: el
9/10/2026 da venta $1.540, lo mismo que la compra de dólares de ese día en el
extracto de Franco.

* Un día sin cotización (fin de semana, feriado) responde 404: se usa el día
  hábil anterior, hasta 5 días para atrás, y se dice qué fecha se usó.
* Si la fuente no contesta (timeout, 5xx, sin red): `CotizacionNoDisponible`.
  **Nunca** se usa en silencio una cotización vieja: el Secretario le pide el
  dólar a Franco ("No contestó" ≠ "no existe").
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE = "https://api.argentinadatos.com/v1/cotizaciones/dolares/oficial"
DIAS_PARA_ATRAS = 5


class CotizacionNoDisponible(Exception):
    """La fuente no contestó o no tiene cotización cerca de esa fecha."""


def oficial_vendedor(fecha: date) -> tuple[float, date]:
    """(pesos por dólar, fecha de la cotización usada)."""
    for atras in range(DIAS_PARA_ATRAS + 1):
        f = fecha - timedelta(days=atras)
        url = f"{BASE}/{f:%Y/%m/%d}"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                datos = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue          # ese día no hubo cotización: el anterior
            raise CotizacionNoDisponible(f"ArgentinaDatos respondió {e.code}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise CotizacionNoDisponible(f"no pude hablar con ArgentinaDatos ({e})") from None
        except json.JSONDecodeError:
            raise CotizacionNoDisponible("ArgentinaDatos contestó algo que no entiendo") from None
        venta = datos.get("venta") if isinstance(datos, dict) else None
        if not isinstance(venta, (int, float)) or venta <= 0:
            raise CotizacionNoDisponible("ArgentinaDatos no trajo el precio de venta")
        return float(venta), f
    raise CotizacionNoDisponible(
        f"no hay cotización entre el {fecha - timedelta(days=DIAS_PARA_ATRAS):%d/%m} y el "
        f"{fecha:%d/%m}")
