"""El evaluador de `scripts/probar_lenguaje.py` (Fase E, paso 2) califica bien.

El script corre contra Gemini de verdad y a mano; acá se prueba con un
traductor falso que su nota (BIEN / DUDOSA / MAL) es la que corresponde, sobre
todo que **nada que cargaría algo distinto salga como BIEN**.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

import core.db as core_db
from core.api.gemini import GeminiNoDisponible, Traduccion

_RUTA = Path(__file__).resolve().parents[1] / "scripts" / "probar_lenguaje.py"
_spec = importlib.util.spec_from_file_location("probar_lenguaje", _RUTA)
pl = importlib.util.module_from_spec(_spec)
sys.modules["probar_lenguaje"] = pl      # las dataclasses buscan su módulo acá
_spec.loader.exec_module(pl)


class Falso:
    def __init__(self, respuestas):
        self.respuestas = respuestas

    def traducir(self, mensaje, contexto):
        r = self.respuestas[mensaje]
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def _aislado(monkeypatch, tmp_path):
    # El script apunta DB_PATH y BACKUP_DIR a su carpeta temporal: que no quede así.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "x.db"))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")


def _notas(casos, respuestas):
    return [r.nota for r in pl.correr(Falso(respuestas), casos, pausa=0, salida=lambda s: None)]


def O(orden):  # noqa: N802
    return Traduccion("orden", orden=orden)


def test_gastos():
    casos = [pl.Caso("ayer gasté 5 lucas en el chino", gastos=[(1, 5000, {"Compras"}, False)])] * 4
    assert _notas(casos[:1], {casos[0].mensaje: O("ayer 5000, compras")}) == ["BIEN"]
    assert _notas(casos[:1], {casos[0].mensaje: O("ayer 500, compras")}) == ["MAL"]
    assert _notas(casos[:1], {casos[0].mensaje: O("5000, compras")}) == ["MAL"]      # otra fecha
    assert _notas(casos[:1], {casos[0].mensaje: O("ayer 5000, chino")}) == ["DUDOSA"]
    assert _notas(casos[:1], {casos[0].mensaje: Traduccion("pregunta", texto="¿?")}) == ["DUDOSA"]


def test_lo_que_no_tiene_que_escribir():
    caso = pl.Caso("fui al chino", no_escribe=True)
    assert _notas([caso], {caso.mensaje: Traduccion("pregunta", texto="¿Cuánto?")}) == ["BIEN"]
    assert _notas([caso], {caso.mensaje: O("5000, compras")}) == ["MAL"]


def test_correcciones_de_la_conciliacion():
    caso = pl.Caso("el del mecánico ponelo en auto", "extracto",
                   correcciones={"MECANICO INVENTADO": {"Auto"}})
    # El número del mecánico sale de la propuesta armada por el script.
    n = next(i for i, (_, _, c, _) in enumerate(pl.EXTRACTO) if c == "MECANICO INVENTADO")
    assert n                                                  # existe en el extracto
    notas = []
    for orden in ("{n} auto", "{n} auto, ok", "{n} salidas", "1 auto"):
        resultados = pl.correr(_ConNumero(caso.mensaje, orden), [caso], pausa=0,
                               salida=lambda s: None)
        notas.append(resultados[0].nota)
    assert notas[0] == "BIEN"
    assert notas[1] == "BIEN"       # el ok que Franco no dijo lo saca el código
    assert notas[2] == "MAL"        # otra categoría
    assert notas[3] in ("MAL", "BIEN") and notas[3] == (
        "BIEN" if _numero_del_mecanico() == 1 else "MAL")


def _numero_del_mecanico():
    return _numero_de("MECANICO INVENTADO")


def _numero_de(comercio):
    import tempfile
    from datetime import datetime

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ruta = pl._base(Path(tmp), "extracto", datetime.now(pl._zona()))
        conn = core_db.connect(ruta)
        try:
            return pl._numeros_por_comercio(conn)[comercio]
        finally:
            conn.close()


class _ConNumero:
    """Pone el número que tiene el mecánico en la propuesta en `{n}`."""

    def __init__(self, mensaje, plantilla):
        self.mensaje, self.plantilla = mensaje, plantilla

    def traducir(self, mensaje, contexto):
        n = next(l.split(".")[0].strip() for l in contexto.splitlines()
                 if "MECANICO INVENTADO" in l and l.strip()[:1].isdigit())
        return O(self.plantilla.replace("{n}", n))


def test_el_parser_solo_y_las_consultas():
    casos = [pl.Caso("va", "extracto", ok=True, parser=True),
             pl.Caso("cuánto llevo gastado este mes?", consulta="resumen")]
    assert _notas(casos, {casos[1].mensaje: O("resumen")}) == ["BIEN", "BIEN"]


def test_saldos_se_comparan_por_lo_que_valen():
    caso = pl.Caso("tengo 3,7 palos en el fima y 60 lucas en efectivo",
                   orden_exacta="fima 3700000 efectivo 60000")
    assert _notas([caso], {caso.mensaje: O("fima 3.700.000 efectivo 60.000")}) == ["BIEN"]
    assert _notas([caso], {caso.mensaje: O("fima 370000 efectivo 60000")}) == ["MAL"]
    # Fly, 4/11: con "caja" el bot no la entiende y la descarta: no cargaría nada.
    assert _notas([caso], {caso.mensaje: O("fima 3700000 efectivo 60000 caja 207287,49")}) == [
        "DUDOSA"]


def test_se_califica_lo_que_el_bot_muestra_sin_el_ok_agregado():
    caso = pl.Caso("la ferretería es compras", "extracto",
                   correcciones={"FERRETERIA INVENTADA": {"Compras"}})
    n = _numero_de("FERRETERIA INVENTADA")
    resultados = pl.correr(Falso({caso.mensaje: O(f"{n} compras, ok")}), [caso], pausa=0,
                           salida=lambda s: None)
    assert resultados[0].nota == "BIEN" and f"el bot muestra «{n} compras»" in resultados[0].detalle


def test_si_gemini_falla_se_ve_y_no_corta_la_prueba():
    """El 4/11 en Fly las 44 frases salieron "no consultó a Gemini": era Gemini fallando."""
    casos = [pl.Caso("nafta 20k", gastos=[(0, 20000, {"Auto"}, False)]),
             pl.Caso("taxi 7800", gastos=[(0, 7800, {"Transportes"}, False)])]
    lineas = []
    resultados = pl.correr(Falso({"nafta 20k": GeminiNoDisponible("Gemini respondió 400: x"),
                                  "taxi 7800": O("7800, transportes")}),
                           casos, pausa=0, salida=lineas.append)
    assert [r.nota for r in resultados] == ["FALLA", "BIEN"]
    assert "Gemini respondió 400: x" in resultados[0].detalle
    assert "1 FALLA" in lineas[-1]


def test_los_casos_del_script_estan_bien_armados():
    """Cada caso espera una sola cosa (si no, la nota no significa nada)."""
    for c in pl.CASOS:
        esperas = [bool(c.gastos), bool(c.correcciones) or c.ok is not None or c.cancelar,
                   bool(c.consulta), bool(c.orden_exacta), c.no_escribe]
        assert sum(esperas) == 1 or (c.parser and sum(esperas) <= 1), c.mensaje
    assert len(pl.CASOS) >= 45
