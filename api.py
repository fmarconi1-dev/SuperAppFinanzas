"""Arranque de la API (Fase A, ADR-0008). Lo lanza `docker-entrypoint.sh`.

Escucha en 127.0.0.1:8000 (no se expone: nginx le pasa `/api/`). Si se cae,
el entrypoint la vuelve a levantar.
"""

from __future__ import annotations

import logging
import os

from core.api.servidor import crear_servidor
from core.db import init_db
from places.finanzas.core.comandos import procesar


def _procesar(conn, texto: str, user_id: int):
    return procesar(conn, texto, user_id=user_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[api] %(levelname)s %(name)s: %(message)s")
    init_db()
    host = os.environ.get("API_HOST", "127.0.0.1")
    puerto = int(os.environ.get("API_PORT", "8000"))
    servidor = crear_servidor(host, puerto, procesar=_procesar)
    logging.getLogger("superapp.api").info("Escuchando en %s:%s", host, puerto)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
