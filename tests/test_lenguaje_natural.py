"""Lenguaje natural (Fase E, paso 1, ADR-0012): Gemini traduce, el código decide.

Gemini se reemplaza por un traductor falso que devuelve lo que el test le
dice; lo que importa es lo que hace el Secretario con eso: **nada se escribe
sin el *sí* de Franco**, una traducción que el parser no entiende se descarta,
y si Gemini no contesta se dice. El cliente real se prueba contra el Gemini de
mentira de `test_fotos.py`. Nombres inventados.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from core.api.gemini import ClienteGemini, GeminiNoDisponible, Traduccion
from places.finanzas.core.comandos import procesar
from places.finanzas.core.lenguaje import clasificar
from tests.test_conciliacion import AHORA, COMPRA, _extracto, _mandar, _txns, db  # noqa: F401
from tests.test_fotos import gemini_falso  # noqa: F401 — el fixture del Gemini de mentira

UID = 1
HOY = AHORA.date()


class TraductorFalso:
    def __init__(self, traduccion=None, error=None):
        self.traduccion, self.error, self.pedidos = traduccion, error, []

    def traducir(self, mensaje, contexto):
        self.pedidos.append((mensaje, contexto))
        if self.error:
            raise GeminiNoDisponible(self.error)
        return self.traduccion


def _orden(orden):
    return TraductorFalso(Traduccion("orden", orden=orden))


def _p(db, texto, traductor=None, cuando=AHORA):
    return procesar(db, texto, user_id=UID, ahora=cuando, traductor=traductor)


# ---------------------------------------------------------------- gastos

def test_sin_traductor_todo_sigue_igual(db):
    r = _p(db, "ayer gasté 5 lucas en el chino")
    assert r.resultado == "rechazado" and "No encontré monto y categoría" in r.texto


def test_lo_que_el_parser_entiende_no_llama_a_gemini(db):
    t = _orden("no debería usarse")
    assert _p(db, "5000, compras", t).resultado == "cargado"
    assert t.pedidos == []


def test_una_traduccion_no_carga_nada_hasta_el_si(db):
    t = _orden("ayer 5000, compras")
    r = _p(db, "ayer gasté 5 lucas en el chino", t)
    assert r.resultado == "pendiente"
    assert "Entendí:\nayer 5000, compras" in r.texto and "*sí*" in r.texto
    assert _txns(db) == []
    r = _p(db, "sí")
    assert r.resultado == "cargado" and r.transaccion_id
    assert [(x["fecha"], x["motivo"], x["pasivos"]) for x in _txns(db)] == [
        ((HOY - timedelta(days=1)).isoformat(), "Compras", 5000.0)]


def test_con_un_no_no_se_hace_nada(db):
    _p(db, "ayer gasté 5 lucas en el chino", _orden("ayer 5000, compras"))
    r = _p(db, "no")
    assert r.resultado == "rechazado" and "no hice nada" in r.texto
    assert _txns(db) == []


def test_la_traduccion_vence_como_cualquier_pregunta(db):
    _p(db, "ayer gasté 5 lucas en el chino", _orden("ayer 5000, compras"))
    r = _p(db, "sí", cuando=AHORA + timedelta(minutes=11))
    assert r.resultado == "rechazado" and _txns(db) == []


def test_una_categoria_nueva_le_pregunta_a_gemini(db):
    """«5000 en el chino»: el parser leía la categoría «En el chino»."""
    t = _orden("5000, compras")
    r = _p(db, "5000 en el chino", t)
    assert t.pedidos and "Entendí:\n5000, compras" in r.texto
    assert _p(db, "sí").resultado == "cargado"
    assert [x["motivo"] for x in _txns(db)] == ["Compras"]


def test_si_gemini_no_ayuda_con_la_categoria_queda_la_pregunta_de_siempre(db):
    r = _p(db, "5000 chino", _orden("5000, chino"))
    assert "La categoría *Chino* no existe" in r.texto
    assert _p(db, "sí").resultado == "cargado"
    assert [x["motivo"] for x in _txns(db)] == ["Chino"]


def test_varios_renglones_traducidos_pasan_por_la_propuesta(db):
    _p(db, "gasté 5 lucas en el chino y 20k de nafta", _orden("5000, compras\n20000, auto"))
    r = _p(db, "sí")
    assert r.resultado == "pendiente" and "Te cargo 2" in r.texto      # la propuesta de siempre
    assert _txns(db) == []


# ---------------------------------------------------------------- lo que no se acepta

def test_una_traduccion_que_el_parser_no_entiende_se_descarta(db):
    r = _p(db, "comprame acciones de YPF", _orden("comprar YPF"))
    assert r.resultado == "rechazado" and "No encontré monto y categoría" in r.texto
    assert _p(db, "sí").texto == "No tengo nada pendiente de confirmar."


def test_si_gemini_no_contesta_se_dice(db):
    r = _p(db, "ayer gasté 5 lucas", TraductorFalso(error="Gemini respondió 429"))
    assert "No encontré monto y categoría" in r.texto and "429" in r.texto


def test_no_entiendo_devuelve_la_respuesta_de_siempre(db):
    r = _p(db, "hola qué tal", TraductorFalso(Traduccion("no_entiendo")))
    assert r.resultado == "rechazado" and "No encontré monto y categoría" in r.texto


def test_una_pregunta_de_gemini_llega_a_franco(db):
    t = TraductorFalso(Traduccion("pregunta", texto="¿Cuánto gastaste en el chino?"))
    r = _p(db, "fui al chino", t)
    assert r.texto == "🤖 ¿Cuánto gastaste en el chino?" and _txns(db) == []


def test_una_pregunta_reemplaza_al_creo_la_categoria(db):
    t = TraductorFalso(Traduccion("pregunta", texto="¿En qué categoría va?"))
    _p(db, "5000 en el chino", t)
    assert _p(db, "sí").texto == "No tengo nada pendiente de confirmar."
    assert _txns(db) == []


# ---------------------------------------------------------------- consultas y órdenes delicadas

def test_una_consulta_corre_sin_pedir_el_si(db):
    r = _p(db, "cuánto llevo gastado este mes?", _orden("resumen"))
    assert r.resultado == "consulta" and r.texto.startswith("🤖 Entendí: *resumen*")


def test_deshacer_traducido_pide_confirmacion(db):
    r = _p(db, "borrá lo último que cargué", _orden("deshacer"))
    assert r.resultado == "pendiente" and "Entendí:\ndeshacer" in r.texto
    # Con el sí corre el `deshacer` de siempre (acá no hay mensajes de WhatsApp que deshacer).
    assert "No hay nada cargado por WhatsApp" in _p(db, "sí").texto


# ---------------------------------------------------------------- la conciliación

def _con_extracto(db):
    _mandar(db, _extracto([("20/10/2026", COMPRA.format("FERRETERIA INVENTADA"), -41200),
                           ("21/10/2026", COMPRA.format("KIOSCO INVENTADO"), -1500)]))


def test_gemini_ve_la_propuesta_abierta_y_las_categorias(db):
    _con_extracto(db)
    t = _orden("1 compras")
    _p(db, "la ferretería ponela en compras", t)
    _, contexto = t.pedidos[0]
    assert "PROPUESTA ABIERTA" in contexto and "FERRETERIA INVENTADA" in contexto
    assert "Compras" in contexto and "Salidas" in contexto
    assert "Hoy: miércoles 18/11/2026" in contexto


def test_un_ok_traducido_no_aplica_la_conciliacion_sin_el_si(db):
    _con_extracto(db)
    r = _p(db, "la ferretería es compras, el kiosco salidas y dale", _orden("1 compras, 2 salidas, ok"))
    assert r.resultado == "pendiente" and _txns(db) == []
    r = _p(db, "sí")
    assert r.resultado == "lote"
    assert sorted(x["motivo"] for x in _txns(db)) == ["Compras", "Salidas"]


def test_una_duda_sobre_la_propuesta_se_contesta(db):
    _con_extracto(db)
    t = TraductorFalso(Traduccion("respuesta", texto="El 1 es la ferretería del 20/10."))
    r = _p(db, "qué es el 1?", t)
    assert r.texto == "🤖 El 1 es la ferretería del 20/10." and _txns(db) == []


@pytest.mark.parametrize("orden", ["1500, compras\n3000, transportes",
                                   "fima 512.300 efectivo 98.000"])
def test_una_traduccion_no_tira_la_conciliacion_abierta(db, orden):
    """«Agregá el café y el uber» en medio de la conciliación: varios gastos (o los
    saldos) armarían otra propuesta y descartarían el extracto."""
    _con_extracto(db)
    r = _p(db, "agregá el café de 1500 y el uber de 3000", _orden(orden))
    assert r.resultado == "rechazado" and "reemplazaría la propuesta" in r.texto
    # El extracto sigue ahí: el sí es para él, como siempre.
    assert "Me falta la categoría de: 1, 2" in _p(db, "sí").texto


def test_un_gasto_suelto_traducido_no_toca_la_conciliacion(db):
    _con_extracto(db)
    _p(db, "agregá el café de 1500", _orden("1500, compras"))
    assert _p(db, "sí").resultado == "cargado"
    assert "Me falta la categoría de: 1, 2" in _p(db, "ok").texto       # sigue abierta


def test_el_lenguaje_natural_viene_apagado(monkeypatch):
    """Paso 1 sin probar contra Gemini de verdad: el deploy no lo prende solo."""
    import api

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.delenv("LENGUAJE_NATURAL", raising=False)
    assert api._traductor() is None
    monkeypatch.setenv("LENGUAJE_NATURAL", "1")
    assert api._traductor() == ClienteGemini("k")


def test_un_renglon_que_no_existe_no_es_una_orden(db):
    _con_extracto(db)
    r = _p(db, "el 9 es salidas", _orden("9 salidas"))
    assert r.resultado == "rechazado" and "Entendí" not in r.texto
    # Nada quedó esperando el sí: el próximo sí es para la propuesta, como siempre.
    assert "Me falta la categoría de: 1, 2" in _p(db, "sí").texto and _txns(db) == []


# ---------------------------------------------------------------- clasificar

@pytest.mark.parametrize("orden,cantidad,esperado", [
    ("resumen", 0, "consulta"),
    ("agenda", 0, "consulta"),
    ("deshacer", 0, "escribe"),
    ("ayer 5000, compras", 0, "escribe"),
    ("+404625, haberes ucema", 0, "escribe"),
    ("evento: viernes, 15:00, Dentista", 0, "escribe"),
    ("evento: el 31/02, algo", 0, None),
    ("fima 512.300 efectivo 98.000", 0, "propone"),
    ("1500, compras\n3000, transportes", 0, "propone"),
    ("1 compras, 2 no, ok", 3, "escribe"),
    ("1 compras", 0, None),                 # sin coma no es un gasto de $1: es un renglón
    ("9 salidas", 3, None),                 # un renglón que la propuesta no tiene
    ("comprar YPF", 0, None),
    ("", 0, None),
])
def test_clasificar(orden, cantidad, esperado):
    assert clasificar(orden, hoy=HOY, cantidad=cantidad) == esperado


# ---------------------------------------------------------------- el cliente real

def test_el_cliente_traduce_con_el_esquema(gemini_falso):  # noqa: F811
    gemini_falso["respuesta"] = {"candidates": [{"content": {"parts": [
        {"text": json.dumps({"tipo": "orden", "orden": " ayer 5000, compras "})}]}}]}
    t = ClienteGemini("k").traducir("ayer 5 lucas en el chino", "Hoy: martes")
    assert t == Traduccion("orden", orden="ayer 5000, compras")
    _, _, cuerpo = gemini_falso["pedidos"][0]
    assert cuerpo["generationConfig"]["responseSchema"]["properties"]["tipo"]["enum"] == [
        "orden", "pregunta", "respuesta", "no_entiendo"]
    textos = [p["text"] for p in cuerpo["contents"][0]["parts"]]
    assert textos[1] == "CONTEXTO\nHoy: martes" and textos[2].endswith("ayer 5 lucas en el chino")


def test_un_tipo_inventado_es_un_error(gemini_falso):  # noqa: F811
    gemini_falso["respuesta"] = {"candidates": [{"content": {"parts": [
        {"text": json.dumps({"tipo": "ejecutar"})}]}}]}
    with pytest.raises(GeminiNoDisponible, match="tipo"):
        ClienteGemini("k").traducir("x", "y")
