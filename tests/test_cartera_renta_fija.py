"""Calendario de cobros, TIR esperada y duration.

Los casos se arman sobre el **cronograma real del AE38** verificado el
5/8/2026: cupón semestral y 22 amortizaciones del 4,5455% (= 100/22) a partir
del 12/7/2027. Sus importes por 100 nominales:

    2027-01-11   capital 0.0000   interes 2.5342   total 2.5342
    2027-07-12   capital 4.5455   interes 2.4932   total 7.0387
    2028-01-10   capital 4.5455   interes 2.3798   total 6.9253

Lo que más se cuida es que **la moneda no se mezcle**: los flujos vienen en la
moneda del bono, y comparar un precio en pesos contra flujos en dólares da una
TIR plausible y equivocada — el peor tipo de error, porque no se nota.
"""

from __future__ import annotations

from datetime import date

import pytest

from places.inversiones.cartera import renta_fija as rf

HOY = date(2026, 8, 5)


class _Flujo:
    def __init__(self, fecha, capital=0.0, interes=0.0, total=None):
        self.fecha = fecha
        self.capital = capital
        self.interes = interes
        self.total = total if total is not None else capital + interes


class _Cron:
    """Lo mínimo que `renta_fija` necesita de un Cronograma."""

    def __init__(self, ticker="AE38", nominales=100.0, flujos=None,
                 clase="HARD_DOLLAR"):
        self.ticker = ticker
        self.nominales = nominales
        self.flujos = flujos or []
        self.clase = clase


def _ae38() -> _Cron:
    """Los tres primeros pagos reales del AE38, por 100 nominales."""
    return _Cron(flujos=[
        _Flujo(date(2027, 1, 11), 0.0, 2.5342, 2.5342),
        _Flujo(date(2027, 7, 12), 4.5455, 2.4932, 7.0387),
        _Flujo(date(2028, 1, 10), 4.5455, 2.3798, 6.9253),
    ])


# ---------------------------------------------------------------------------
# Calendario
# ---------------------------------------------------------------------------

def test_escala_los_pagos_a_la_tenencia_real():
    """El cronograma se cachea por 100 nominales; Franco tiene 3.604."""
    pagos = rf.calendario({"AE38": _ae38()}, {"AE38": 3604}, HOY)
    assert len(pagos) == 3
    assert pagos[0].interes == pytest.approx(2.5342 * 36.04)
    assert pagos[1].capital == pytest.approx(4.5455 * 36.04)


def test_lo_que_no_tenes_no_te_paga():
    """Un bono vendido no paga nada, por más que su cronograma exista."""
    assert rf.calendario({"AE38": _ae38()}, {"AE38": 0}, HOY) == []
    assert rf.calendario({"AE38": _ae38()}, {}, HOY) == []


def test_lo_ya_pagado_no_aparece():
    pagos = rf.calendario({"AE38": _ae38()}, {"AE38": 100},
                          hoy=date(2027, 8, 1))
    assert [p.fecha for p in pagos] == [date(2028, 1, 10)]


def test_los_pagos_salen_ordenados_por_fecha():
    otro = _Cron("AN29", flujos=[_Flujo(date(2026, 11, 30), 0.0, 3.5)])
    pagos = rf.calendario({"AE38": _ae38(), "AN29": otro},
                          {"AE38": 100, "AN29": 100}, HOY)
    assert [p.ticker for p in pagos][0] == "AN29"      # 30/11/2026 va primero
    assert [p.fecha for p in pagos] == sorted(p.fecha for p in pagos)


def test_distingue_el_cupon_de_la_amortizacion():
    """La diferencia importa: el cupón es renta, la amortización te devuelve
    capital. Confundirlos es la trampa #3 del proyecto."""
    pagos = rf.calendario({"AE38": _ae38()}, {"AE38": 100}, HOY)
    assert pagos[0].concepto == "Cupón"
    assert not pagos[0].es_amortizacion
    assert pagos[1].concepto == "Amortización"
    assert pagos[1].es_amortizacion


def test_la_moneda_sale_de_la_clase_del_bono():
    pagos = rf.calendario({"AE38": _ae38()}, {"AE38": 100}, HOY)
    assert pagos[0].moneda == "USD"

    en_pesos = _Cron("TZX28", clase="CER",
                     flujos=[_Flujo(date(2027, 1, 1), 0.0, 5.0)])
    assert rf.calendario({"TZX28": en_pesos}, {"TZX28": 100},
                         HOY)[0].moneda == "ARS"


def test_el_resumen_separa_por_moneda():
    """⚠️ Sumar dólares y pesos en un número repetiría la trampa #1: habría que
    convertir con un TC futuro que **no se conoce**."""
    usd = _ae38()
    ars = _Cron("TZX28", clase="CER",
                flujos=[_Flujo(date(2026, 12, 1), 0.0, 500.0)])
    pagos = rf.calendario({"AE38": usd, "TZX28": ars},
                          {"AE38": 100, "TZX28": 100}, HOY)

    r = rf.resumen_calendario(pagos, HOY, dias=365)
    assert set(r["por_moneda"]) == {"USD", "ARS"}
    assert r["por_moneda"]["ARS"]["total"] == pytest.approx(500.0)
    # En 365 días entran los pagos del 11/1/2027 y del 12/7/2027.
    assert r["por_moneda"]["USD"]["total"] == pytest.approx(2.5342 + 7.0387)
    assert r["proximo"].ticker == "TZX28"


def test_el_resumen_solo_cuenta_la_ventana_pedida():
    pagos = rf.calendario({"AE38": _ae38()}, {"AE38": 100}, HOY)
    assert rf.resumen_calendario(pagos, HOY, dias=90)["n_pagos"] == 0
    assert rf.resumen_calendario(pagos, HOY, dias=365)["n_pagos"] == 2
    assert rf.resumen_calendario(pagos, HOY, dias=800)["n_pagos"] == 3


# ---------------------------------------------------------------------------
# TIR esperada
# ---------------------------------------------------------------------------

def test_comprar_por_debajo_de_lo_que_va_a_pagar_rinde_positivo():
    """⚠️ **El fixture tiene solo los 3 primeros pagos del AE38** (el bono real
    tiene 34), así que suman **16,4982** y no ~100. La referencia para "caro" o
    "barato" es esa suma, no el valor par.

    Pagar 12 por 16,50 repartidos en año y medio tiene que dar TIR positiva.
    """
    t = rf.tir_esperada(_ae38(), precio=12.0, hoy=HOY)
    assert t is not None and t > 0


def test_pagar_mas_de_lo_que_va_a_pagar_da_tir_negativa():
    """A 20 por 16,4982 se pierde plata, y el número tiene que decirlo en vez
    de disimularlo."""
    t = rf.tir_esperada(_ae38(), precio=20.0, hoy=HOY)
    assert t is not None and t < 0


def test_la_tir_se_calcula_sobre_los_pagos_que_FALTAN():
    """Un cupón ya cobrado no puede mejorar el rendimiento de lo que queda."""
    completa = rf.tir_esperada(_ae38(), precio=12.0, hoy=HOY)
    parcial = rf.tir_esperada(_ae38(), precio=12.0, hoy=date(2027, 8, 1))
    assert completa != parcial


def test_escalar_los_nominales_no_cambia_la_tir():
    """La TIR es una tasa: comprar el doble al doble de precio rinde igual.
    Si cambiara, habría un error de escala escondido."""
    chica = rf.tir_esperada(_ae38(), precio=12.0, nominales=100, hoy=HOY)
    grande = rf.tir_esperada(_ae38(), precio=12.0 * 36.04, nominales=3604,
                             hoy=HOY)
    assert chica == pytest.approx(grande, rel=1e-6)


@pytest.mark.parametrize("precio", [0, None, -50.0])
def test_sin_precio_valido_no_hay_tir(precio):
    """Nunca inventa: sin precio no hay rendimiento que calcular."""
    assert rf.tir_esperada(_ae38(), precio=precio, hoy=HOY) is None


def test_sin_pagos_futuros_no_hay_tir():
    assert rf.tir_esperada(_ae38(), precio=12.0, hoy=date(2030, 1, 1)) is None
    assert rf.tir_esperada(None, precio=12.0, hoy=HOY) is None


# ---------------------------------------------------------------------------
# Duration
# ---------------------------------------------------------------------------

def test_la_duration_cae_entre_el_primer_y_el_ultimo_pago():
    """Es un promedio ponderado de plazos: no puede estar fuera del rango."""
    mac, _ = rf.duration(_ae38(), tasa=0.10, hoy=HOY)
    primer = (date(2027, 1, 11) - HOY).days / 365.0
    ultimo = (date(2028, 1, 10) - HOY).days / 365.0
    assert primer < mac < ultimo


def test_la_modificada_es_menor_que_la_macaulay():
    """Por definición: modificada = Macaulay / (1 + tasa)."""
    mac, mod = rf.duration(_ae38(), tasa=0.10, hoy=HOY)
    assert mod == pytest.approx(mac / 1.10)
    assert mod < mac


def test_a_mayor_tasa_menor_duration():
    """Descontar más fuerte le da menos peso a los pagos lejanos."""
    baja, _ = rf.duration(_ae38(), tasa=0.05, hoy=HOY)
    alta, _ = rf.duration(_ae38(), tasa=0.30, hoy=HOY)
    assert alta < baja


def test_sin_tasa_no_hay_duration():
    """Descontar a cero trataría un pago de 2038 igual que uno de mañana."""
    assert rf.duration(_ae38(), tasa=None, hoy=HOY) == (None, None)
    assert rf.duration(None, tasa=0.1, hoy=HOY) == (None, None)


def test_sin_pagos_futuros_no_hay_duration():
    assert rf.duration(_ae38(), tasa=0.1, hoy=date(2030, 1, 1)) == (None, None)


# ---------------------------------------------------------------------------
# Las dos juntas
# ---------------------------------------------------------------------------

def test_riesgo_descuenta_la_duration_a_la_propia_tir():
    """Van juntas a propósito: una duration calculada con otra tasa no es
    comparable con esa TIR."""
    r = rf.riesgo(_ae38(), precio=12.0, hoy=HOY)
    assert r.tir is not None and r.duration is not None
    esperada, _ = rf.duration(_ae38(), tasa=r.tir, hoy=HOY)
    assert r.duration == pytest.approx(esperada)


def test_el_riesgo_guarda_el_precio_que_uso():
    """Una TIR sin el precio contra el que se calculó no se puede auditar."""
    assert rf.riesgo(_ae38(), precio=12.0, hoy=HOY).precio == 12.0


def test_la_variacion_por_100pb_es_la_lectura_util():
    """*'Si el rendimiento sube 1 punto, este bono vale X% menos'*."""
    r = rf.riesgo(_ae38(), precio=12.0, hoy=HOY)
    assert r.variacion_por_100pb() == pytest.approx(-r.duration_modificada)
    assert r.variacion_por_100pb() < 0


def test_sin_precio_el_riesgo_queda_vacio_pero_no_rompe():
    r = rf.riesgo(_ae38(), precio=None, hoy=HOY)
    assert (r.tir, r.duration, r.duration_modificada) == (None, None, None)
    assert r.ticker == "AE38"


# ---------------------------------------------------------------------------
# El puente entre la posición valuada y la moneda del bono
# ---------------------------------------------------------------------------
#
# ⚠️ Es el punto donde la TIR se arruina en silencio. `PosicionValuada.precio`
# está **en pesos**; los flujos de un bono hard-dollar están **en dólares**.
# Compararlos da un número plausible y equivocado.
#
# Se testea por AST y no importando la vista, porque `view.py` trae Streamlit
# entero — el mismo criterio que `test_transacciones_formulario.py`.

import ast                                          # noqa: E402
from pathlib import Path                            # noqa: E402

VISTA = (Path(__file__).resolve().parents[1]
         / "places" / "inversiones" / "cartera" / "view.py")


def _nodo_de(nombre: str) -> ast.FunctionDef:
    arbol = ast.parse(VISTA.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
            return nodo
    raise AssertionError(f"no existe la función {nombre}() en view.py")


def _fuente_de(nombre: str) -> str:
    return ast.unparse(_nodo_de(nombre))


def _llamadas_de(nombre: str) -> set[str]:
    """Los nombres **llamados** dentro de la función.

    Por AST y no por subcadena: buscar el texto `refrescar_cronogramas` daba un
    falso positivo porque `_boton_refrescar_cronogramas` lo **contiene**. Un
    test que se equivoca así erosiona la confianza en todos los demás.
    """
    llamadas = set()
    for n in ast.walk(_nodo_de(nombre)):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name):
            llamadas.add(f.id)
        elif isinstance(f, ast.Attribute):
            llamadas.add(f.attr)
    return llamadas


def test_el_precio_de_un_bono_en_dolares_sale_del_valor_en_dolares():
    """No de `precio`, que está en pesos."""
    fuente = _fuente_de("_precio_por_100_en_moneda_del_bono")
    assert "valor_usd_actual" in fuente
    assert "USD" in fuente


def test_la_vista_pasa_la_moneda_del_bono_al_calculo():
    """`riesgo()` exige moneda explícita justamente para que quien llama tenga
    que decidirla. Si la vista dejara el default, el pedido se perdería."""
    fuente = _fuente_de("_renta_fija")
    assert "moneda=moneda" in fuente
    assert "HARD" in fuente          # de ahí sale si es USD o ARS


def test_la_vista_no_consulta_la_red_al_abrirse():
    """Con 15 consultas por día, pedir cronogramas al renderizar vaciaría la
    cuota con solo mirar la pantalla. Solo el botón consulta."""
    llamadas = _llamadas_de("_renta_fija")
    assert "leer_cronograma" in llamadas
    assert "refrescar_cronogramas" not in llamadas
    assert "traer_cronograma" not in llamadas
    assert "buscar_simbolo" not in llamadas


def test_solo_el_boton_refresca():
    llamadas = _llamadas_de("_boton_refrescar_cronogramas")
    assert "refrescar_cronogramas" in llamadas
    assert "button" in llamadas


def test_la_tabla_de_pagos_lleva_la_moneda_de_cada_pago():
    """Sin la columna, dos filas en monedas distintas se leerían como
    comparables. Un total único exigiría un TC futuro que no se conoce."""
    fuente = _fuente_de("_renta_fija")
    assert "'Moneda': p.moneda" in fuente
