"""Qué es "la fuente no contestó", para todas las fuentes externas.

**Por qué existe (trampa 16 + 36).** Hasta el 22/9/2026 cada proveedor hacía
``except Exception: return None``. Eso junta tres cosas distintas en un mismo
``None``: la fuente dijo que el dato **no existe**, la fuente **no contestó**,
y un **bug** nuestro. Con caché negativa encima, lo segundo se volvía "no
existe" para siempre y lo tercero no se veía nunca.

Regla: una falla de red se convierte en `FuenteNoDisponible` (se reintenta,
no se cachea como "sin dato"); un error de programación se deja pasar.
"""

from __future__ import annotations

import http.client

__all__ = ["FuenteNoDisponible", "ERRORES_DE_RED"]


class FuenteNoDisponible(Exception):
    """La fuente no contestó: sin token, caída, cuota agotada, timeout, o una
    respuesta que ni siquiera es JSON. **No** significa que el dato no exista."""


#: Lo que puede tirar una consulta HTTP que no contestó. `URLError`,
#: `HTTPError`, `ConnectionError` y los timeouts son `OSError`;
#: `IncompleteRead` es `HTTPException`; un cuerpo que no es JSON es
#: `ValueError`. Un `AttributeError`, `NameError`, etc. — un bug — **no**.
ERRORES_DE_RED = (OSError, http.client.HTTPException, ValueError)
