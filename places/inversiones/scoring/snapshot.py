"""Lectura del snapshot del scoring (generado por el batch de GitHub Actions).

La superapp NO calcula el scoring (regla dura del repo): el batch corre en el
repo público `Scoring-Inversiones` (cron 22:00 UTC, días hábiles) y publica
`data.json` en GitHub Pages. Acá solo se LEE ese JSON, con caché en memoria
(15 min) y fallback a la última copia local si la red falla.
Decisión registrada en `docs/decisiones/ADR-0002-scoring-snapshot-remoto.md`.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import streamlit as st

SNAPSHOT_URL = os.environ.get(
    "SCORING_SNAPSHOT_URL",
    "https://fmarconi1-dev.github.io/Scoring-Inversiones/data.json",
)
# Copia local de resguardo (vive en data/, ignorada por git).
CACHE_LOCAL = Path(os.environ.get("SCORING_CACHE_PATH", "data/scoring_cache.json"))
TIMEOUT_S = 10


def _fetch_remoto(url: str = SNAPSHOT_URL) -> dict:
    """Trae el JSON publicado en Pages. Lanza excepción si falla."""
    req = urllib.request.Request(url, headers={"User-Agent": "superapp-finanzas"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


@st.cache_data(ttl=15 * 60, show_spinner=False)
def _remoto_cacheado() -> dict:
    # st.cache_data NO cachea excepciones: si la red falla, el próximo
    # rerun vuelve a intentar (no queda 15 min "pegado" en el error).
    return _fetch_remoto()


def _persistir_fallback(datos: dict, cache_path: Path) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # no poder guardar el resguardo no es fatal


def _leer_fallback(cache_path: Path) -> dict | None:
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cargar_snapshot(fetch=None, cache_path: Path = CACHE_LOCAL):
    """Devuelve (datos, origen) con origen ∈ {"red", "cache_local", None}.

    Nunca lanza: si no hay red ni copia local devuelve (None, None) y la
    vista muestra el estado de error con retry (el tablero nunca se rompe
    por una llamada de red — regla heredada de Scoring-Inversiones).
    """
    fetch = fetch or _remoto_cacheado
    try:
        datos = fetch()
        _persistir_fallback(datos, cache_path)
        return datos, "red"
    except Exception:
        datos = _leer_fallback(cache_path)
        if datos is not None:
            return datos, "cache_local"
        return None, None


def refrescar() -> None:
    """Invalida el caché en memoria (para el botón 'Actualizar')."""
    _remoto_cacheado.clear()
