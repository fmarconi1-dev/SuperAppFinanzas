"""Arranque de la API (Fase A y B, ADR-0008). Lo lanza `docker-entrypoint.sh`.

Escucha en 127.0.0.1:8000 (no se expone: nginx le pasa `/api/`). Si se cae,
el entrypoint la vuelve a levantar.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Optional

from core.api import balances_fuentes
from core.api.cotizaciones import oficial_vendedor
from core.api.gemini import ClienteGemini
from core.api.google import ClienteAgenda
from core.api.servidor import ahora_ar, crear_servidor
from core.db import init_db
from core.workspaces import resolve_workspace_id
from places.finanzas.core import balances, briefing
from places.finanzas.core.comandos import procesar, procesar_archivo


def _procesar(conn, texto: str, user_id: int, id_mensaje: Optional[str] = None):
    # La agenda se lee del entorno en cada mensaje: si faltan sus variables,
    # los comandos de agenda lo dicen y todo lo demás anda igual.
    return procesar(conn, texto, user_id=user_id, agenda=ClienteAgenda.desde_entorno(),
                    id_mensaje=id_mensaje, cotizador=oficial_vendedor,
                    fuentes_balances=balances_fuentes)


def _procesar_archivo(conn, archivo, user_id: int, id_mensaje: Optional[str] = None):
    # El dólar de los consumos en USD de las tarjetas (ArgentinaDatos, gratis) y,
    # para las fotos, Gemini en el plan gratuito (sin GEMINI_API_KEY no se leen).
    return procesar_archivo(conn, archivo, user_id=user_id, cotizador=oficial_vendedor,
                            lector_fotos=ClienteGemini.desde_entorno())


def _componer(conn, texto: str, tipo: str, user_id: int) -> str:
    return briefing.componer(conn, texto, tipo, user_id=user_id, hoy=ahora_ar().date())


def _balances(conn, datos: dict, user_id: int) -> str:
    # La lista del domingo (ADR-0011): calendario de Nasdaq y S&P 500 de Wikipedia.
    try:
        lunes = date.fromisoformat(str(datos.get("lunes")))
    except ValueError:
        raise ValueError("'lunes' tiene que ser una fecha AAAA-MM-DD") from None
    if lunes.weekday() != 0:
        raise ValueError(f"{lunes} no es lunes")
    return balances.armar(conn, workspace_id=resolve_workspace_id(conn, user_id), lunes=lunes,
                          fuentes=balances_fuentes, ahora=ahora_ar())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[api] %(levelname)s %(name)s: %(message)s")
    init_db()
    host = os.environ.get("API_HOST", "127.0.0.1")
    puerto = int(os.environ.get("API_PORT", "8000"))
    servidor = crear_servidor(host, puerto, procesar=_procesar, componer=_componer,
                              procesar_archivo=_procesar_archivo, balances=_balances)
    logging.getLogger("superapp.api").info("Escuchando en %s:%s", host, puerto)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
