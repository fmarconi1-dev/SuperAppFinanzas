"""Arranque de la API (Fase A y B, ADR-0008). Lo lanza `docker-entrypoint.sh`.

Escucha en 127.0.0.1:8000 (no se expone: nginx le pasa `/api/`). Si se cae,
el entrypoint la vuelve a levantar.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from core.api.cotizaciones import oficial_vendedor
from core.api.google import ClienteAgenda
from core.api.servidor import ahora_ar, crear_servidor
from core.db import init_db
from places.finanzas.core import briefing
from places.finanzas.core.comandos import procesar, procesar_archivo


def _procesar(conn, texto: str, user_id: int, id_mensaje: Optional[str] = None):
    # La agenda se lee del entorno en cada mensaje: si faltan sus variables,
    # los comandos de agenda lo dicen y todo lo demás anda igual.
    return procesar(conn, texto, user_id=user_id, agenda=ClienteAgenda.desde_entorno(),
                    id_mensaje=id_mensaje, cotizador=oficial_vendedor)


def _procesar_archivo(conn, archivo, user_id: int, id_mensaje: Optional[str] = None):
    # El dólar de los consumos en USD de las tarjetas (ArgentinaDatos, gratis).
    return procesar_archivo(conn, archivo, user_id=user_id, cotizador=oficial_vendedor)


def _componer(conn, texto: str, tipo: str, user_id: int) -> str:
    return briefing.componer(conn, texto, tipo, user_id=user_id, hoy=ahora_ar().date())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[api] %(levelname)s %(name)s: %(message)s")
    init_db()
    host = os.environ.get("API_HOST", "127.0.0.1")
    puerto = int(os.environ.get("API_PORT", "8000"))
    servidor = crear_servidor(host, puerto, procesar=_procesar, componer=_componer,
                              procesar_archivo=_procesar_archivo)
    logging.getLogger("superapp.api").info("Escuchando en %s:%s", host, puerto)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
