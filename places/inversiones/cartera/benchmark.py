"""¿Te fue mejor o peor que el mercado? — comparación **money-weighted**.

## Por qué no alcanza con comparar rendimientos

La tentación es: *"la cartera hizo +36,5%, el SPY hizo +52%, perdí"*. Está mal,
y el motivo es el mismo que obligó a calcular la TIR por bisección en vez de un
rendimiento simple: **Franco no puso toda la plata el primer día.** Aportó en
24 momentos distintos a lo largo de 602 días. El índice, en cambio, "aportó"
todo el día uno.

Comparar los acumulados le pregunta a los dos algo distinto. La pregunta justa
es contrafáctica y tiene una sola forma honesta:

> *Si hubieras puesto **la misma plata**, en **las mismas fechas**, en el
> índice — ¿cuánto tendrías hoy?*

Eso es lo que hace `simular()`: recorre los aportes reales, compra unidades del
índice al cierre de **cada** fecha, y valúa el total al cierre de hoy. El
resultado es comparable contra el patrimonio real porque las dos series
recibieron el mismo dinero en el mismo momento.

## Las reglas que evitan un número lindo y falso

* **Cada índice se compara contra los flujos de SU moneda.** SPY contra los
  aportes en dólares, Merval contra los aportes en pesos. Cruzarlos repetiría
  la trampa nº 1 del proyecto: pasar importes de una moneda a otra con el TC de
  cada fecha hace que la devaluación aparezca como rendimiento.
* **Un flujo sin precio no se estima: se informa.** Si un aporte cae antes de
  donde arranca la serie del índice, no se inventa un cierre — el flujo queda
  en `sin_precio` y la vista dice cuántos quedaron afuera. Un contrafáctico con
  agujeros tapados es peor que uno incompleto declarado.
* **La TIR del índice se calcula con el mismo motor** (`posiciones.tir`, la
  bisección) y sobre los mismos flujos. Si se midiera la cartera con TIR y el
  benchmark con rendimiento simple, la comparación no diría nada.
* **Nadie puede vender lo que no tiene.** Si un retiro supera las unidades
  acumuladas, se clampea en cero y queda `sobregiro=True`, en vez de arrastrar
  unidades negativas que darían un valor final absurdo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from core.market_data.indices import valor_en

from .posiciones import tir as _tir

__all__ = ["Comparacion", "flujos_en", "simular", "comparar"]


@dataclass(frozen=True)
class Comparacion:
    """Qué habría pasado con la misma plata puesta en el índice."""

    indice: str
    moneda: str
    #: Unidades del índice acumuladas por los aportes.
    unidades: float
    #: Cuánto valdrían hoy.
    valor_final: float
    #: Capital neto puesto (depósitos − retiros), en la moneda del índice.
    aportado: float
    resultado: float
    #: Sobre el aportado. ``None`` si no se aportó nada (no se divide por cero).
    rendimiento: float | None
    #: Anualizada, por bisección, sobre los mismos flujos.
    tir: float | None
    #: Cuántos flujos se pudieron mapear a un cierre.
    n_flujos: int = 0
    #: Los que no: su fecha cae fuera de la serie del índice.
    sin_precio: list[date] = field(default_factory=list)
    #: Un retiro pidió más unidades de las acumuladas.
    sobregiro: bool = False

    @property
    def completa(self) -> bool:
        """¿La simulación pudo usar todos los flujos?"""
        return not self.sin_precio


def flujos_en(flujos, moneda: str) -> list[tuple[date, float]]:
    """De ``[(fecha, ars, usd)]`` a ``[(fecha, monto)]`` en una sola moneda.

    Es la salida de `posiciones.flujos_de_capital()`, que trae las dos monedas
    en la misma fila. Los ceros se descartan: un aporte en dólares tiene su
    contravalor en pesos, pero uno que quedó en 0 (sin TC congelado) no es un
    flujo, es un dato faltante — y sumarlo como 0 diría que ese día no entró
    plata.
    """
    i = 2 if str(moneda).upper() == "USD" else 1
    return [(f[0], f[i]) for f in (flujos or []) if abs(f[i] or 0.0) > 1e-9]


def simular(flujos, serie: dict, hoy: date | None = None,
            indice: str = "SPY", moneda: str = "USD") -> Comparacion | None:
    """La cartera contrafáctica: los mismos flujos, puestos en el índice.

    `flujos`: ``[(fecha, monto)]`` con el signo de la óptica del inversor
    (aportar es **negativo**), tal como los devuelve `flujos_en()`.

    Devuelve ``None`` si no hay serie o no quedó ningún flujo utilizable: es
    preferible no mostrar nada a mostrar una comparación vacía disfrazada de
    cero.
    """
    hoy = hoy or date.today()
    if not serie or not flujos:
        return None

    unidades = 0.0
    aportado = 0.0
    usados: list[tuple[date, float]] = []
    sin_precio: list[date] = []
    sobregiro = False

    for fecha, monto in sorted(flujos, key=lambda x: x[0]):
        if not monto:
            continue
        precio = valor_en(serie, fecha)
        if precio is None:
            sin_precio.append(fecha)
            continue

        # Aportar (monto<0) compra unidades; retirar (monto>0) las vende.
        delta = -monto / precio
        if unidades + delta < 0:
            delta, sobregiro = -unidades, True

        unidades += delta
        aportado += -monto
        usados.append((fecha, monto))

    if not usados:
        return None

    precio_hoy = valor_en(serie, hoy)
    if precio_hoy is None:
        return None

    valor_final = unidades * precio_hoy
    resultado = valor_final - aportado
    rendimiento = (resultado / aportado) if abs(aportado) > 1e-9 else None

    # Mismo motor que la cartera: los flujos más el valor final como cobro.
    return Comparacion(
        indice=indice,
        moneda=moneda,
        unidades=unidades,
        valor_final=valor_final,
        aportado=aportado,
        resultado=resultado,
        rendimiento=rendimiento,
        tir=_tir(usados + [(hoy, valor_final)]),
        n_flujos=len(usados),
        sin_precio=sin_precio,
        sobregiro=sobregiro,
    )


def comparar(sim: Comparacion | None, valor_real: float | None,
             aportado_real: float | None = None) -> dict | None:
    """Tu cartera contra el contrafáctico, lado a lado.

    `valor_real`: el patrimonio de hoy en la moneda del índice (tenencia +
    efectivo), el mismo número que muestra el KPI de la cartera.

    La **diferencia** es lo único que importa acá: cuánta plata de más (o de
    menos) tenés por haber elegido tus papeles en lugar del índice.
    """
    if sim is None or valor_real is None:
        return None

    aportado = aportado_real if aportado_real is not None else sim.aportado
    resultado_real = valor_real - aportado
    rend_real = (resultado_real / aportado) if abs(aportado) > 1e-9 else None

    return {
        "indice": sim.indice,
        "moneda": sim.moneda,
        "aportado": aportado,
        "valor_real": valor_real,
        "valor_indice": sim.valor_final,
        "resultado_real": resultado_real,
        "resultado_indice": sim.resultado,
        "rendimiento_real": rend_real,
        "rendimiento_indice": sim.rendimiento,
        "tir_indice": sim.tir,
        # >0 = le ganaste al índice.
        "diferencia": valor_real - sim.valor_final,
        "ganaste": valor_real > sim.valor_final,
        "sin_precio": sim.sin_precio,
        "completa": sim.completa,
    }
