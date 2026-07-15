"""Tests del lector de snapshot del scoring (Fase 2).

Sin red: se inyecta el fetch. Cubre las tres salidas de cargar_snapshot:
red OK, fallback local, y sin datos.
"""

from __future__ import annotations

import json

import pytest

from places.inversiones.scoring.snapshot import cargar_snapshot

SNAPSHOT_EJEMPLO = {"generado": "2026-07-15 00:00", "empresas": [], "cambios": []}


def _fetch_ok():
    return dict(SNAPSHOT_EJEMPLO)


def _fetch_falla():
    raise OSError("sin red")


def test_red_ok_persiste_fallback(tmp_path):
    cache = tmp_path / "snap.json"
    datos, origen = cargar_snapshot(fetch=_fetch_ok, cache_path=cache)
    assert origen == "red"
    assert datos["generado"] == SNAPSHOT_EJEMPLO["generado"]
    assert json.loads(cache.read_text(encoding="utf-8"))["generado"] == datos["generado"]


def test_sin_red_usa_copia_local(tmp_path):
    cache = tmp_path / "snap.json"
    cache.write_text(json.dumps(SNAPSHOT_EJEMPLO), encoding="utf-8")
    datos, origen = cargar_snapshot(fetch=_fetch_falla, cache_path=cache)
    assert origen == "cache_local"
    assert datos["generado"] == SNAPSHOT_EJEMPLO["generado"]


def test_sin_red_ni_copia_devuelve_none(tmp_path):
    datos, origen = cargar_snapshot(fetch=_fetch_falla, cache_path=tmp_path / "no-existe.json")
    assert datos is None and origen is None


def test_copia_local_corrupta_no_rompe(tmp_path):
    cache = tmp_path / "snap.json"
    cache.write_text("{esto no es json", encoding="utf-8")
    datos, origen = cargar_snapshot(fetch=_fetch_falla, cache_path=cache)
    assert datos is None and origen is None
