"""Renta fija: cuándo cobrás, cuánto rinde y cuánto riesgo de tasa tiene.

Lo que el cronograma (M15) destraba, en tres preguntas:

1. **¿Cuándo cobro y cuánto?** — el calendario de pagos futuros, escalado a la
   tenencia real. Para un bono amortizable es *la* pregunta: el AE38 no vence
   hasta 2038 pero empieza a devolver capital el **12/7/2027**.
2. **¿Cuánto rinde si lo llevo al final?** — la TIR esperada, con el precio de
   hoy contra los pagos que faltan.
3. **¿Cuánto me mueve una suba de tasas?** — la duration.

---

## ⚠️ La moneda: el error fácil de cometer acá

Los flujos vienen **en la moneda del bono**. Para un `HARD_DOLLAR` como el AE38
son **dólares por cada 100 nominales**, y el precio con el que hay que
compararlos es el de la variante **D** — no el precio en pesos.

Mezclarlos da una TIR sin sentido, y **una TIR sin sentido no se nota**: sale un
número plausible. Por eso `tir_esperada()` **exige que le pasen el precio y su
moneda** en vez de adivinarlos, y la vista es la que decide cuál corresponde.

## ⚠️ Precio limpio o sucio

La TIR compara el precio contra los flujos futuros, así que **el precio tiene
que incluir los intereses corridos** (precio "sucio"). Si el proveedor de
precios diera el limpio, la TIR saldría **sobreestimada**.

Los soberanos argentinos se operan sucios, así que el precio de `data912`
debería servir tal cual — pero **eso es un supuesto, no un hecho verificado**.
La forma de comprobarlo es contrastar nuestra TIR contra la que calcula el
propio proveedor del cronograma: `scripts/verificar_docta.py --tir`. Es la
disciplina de la identidad contable independiente aplicada a un cálculo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from places.inversiones.cartera.posiciones import tir as _tir_biseccion

__all__ = [
    "PagoFuturo", "calendario", "resumen_calendario",
    "tir_esperada", "duration", "Riesgo",
]


@dataclass(frozen=True)
class PagoFuturo:
    """Un cobro que viene, ya escalado a la tenencia real."""

    fecha: date
    ticker: str
    capital: float = 0.0
    interes: float = 0.0
    total: float = 0.0
    #: Moneda del flujo — la del bono, no la de la cartera.
    moneda: str = "USD"

    @property
    def es_amortizacion(self) -> bool:
        return abs(self.capital) > 1e-9

    @property
    def concepto(self) -> str:
        if not self.es_amortizacion:
            return "Cupón"
        return "Amortización" if abs(self.interes) > 1e-9 else "Capital"

    def dias(self, hoy: date | None = None) -> int:
        return (self.fecha - (hoy or date.today())).days


# ---------------------------------------------------------------------------
# Calendario de cobros
# ---------------------------------------------------------------------------

def calendario(cronogramas: dict, tenencias: dict,
               hoy: date | None = None, hasta: date | None = None
               ) -> list[PagoFuturo]:
    """Los pagos que vienen, de todos los bonos, ordenados por fecha.

    `cronogramas`: ``{ticker: Cronograma}`` (por 100 nominales, como se cachea).
    `tenencias`: ``{ticker: nominales}`` — cuánto tenés de cada uno.

    **Solo entra lo que todavía tenés.** Un bono vendido no te paga nada, por
    más que su cronograma siga existiendo.
    """
    hoy = hoy or date.today()
    pagos: list[PagoFuturo] = []

    for ticker, cron in (cronogramas or {}).items():
        nominales = float((tenencias or {}).get(ticker) or 0.0)
        if nominales <= 0 or cron is None:
            continue
        base = float(getattr(cron, "nominales", 100.0) or 100.0)
        escala = nominales / base
        moneda = "USD" if (cron.clase or "").upper().startswith("HARD") else "ARS"

        for f in cron.flujos:
            if f.fecha < hoy or (hasta and f.fecha > hasta):
                continue
            pagos.append(PagoFuturo(
                fecha=f.fecha, ticker=ticker,
                capital=f.capital * escala,
                interes=f.interes * escala,
                total=f.total * escala,
                moneda=moneda,
            ))
    return sorted(pagos, key=lambda p: (p.fecha, p.ticker))


def resumen_calendario(pagos, hoy: date | None = None,
                       dias: int = 365) -> dict:
    """Cuánto entra en los próximos `dias`, separado por moneda.

    **Separado por moneda a propósito.** Sumar dólares y pesos en un solo
    número repetiría la trampa #1 del proyecto: al convertir con el TC de cada
    fecha futura —que además no se conoce— el total diría cualquier cosa.
    """
    hoy = hoy or date.today()
    limite = date.fromordinal(hoy.toordinal() + dias)
    pronto = [p for p in pagos if hoy <= p.fecha <= limite]

    por_moneda: dict[str, dict] = {}
    for p in pronto:
        m = por_moneda.setdefault(p.moneda, {"total": 0.0, "capital": 0.0,
                                             "interes": 0.0, "n": 0})
        m["total"] += p.total
        m["capital"] += p.capital
        m["interes"] += p.interes
        m["n"] += 1

    return {
        "n_pagos": len(pronto),
        "por_moneda": por_moneda,
        "proximo": min(pagos, key=lambda p: p.fecha) if pagos else None,
        "n_total": len(pagos),
    }


# ---------------------------------------------------------------------------
# TIR esperada y duration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Riesgo:
    """TIR y duration de un bono, con el supuesto que las sostiene."""

    ticker: str
    tir: float | None = None                 # anual efectiva, decimal
    duration: float | None = None            # Macaulay, en años
    duration_modificada: float | None = None
    moneda: str = "USD"
    #: Precio usado. Se guarda para que el número sea auditable: una TIR sin
    #: el precio contra el que se calculó no se puede verificar.
    precio: float | None = None

    @property
    def tir_pct(self) -> float | None:
        return None if self.tir is None else self.tir * 100.0

    def variacion_por_100pb(self) -> float | None:
        """Cuánto cae el precio (%) si la tasa sube 1 punto porcentual.

        Es la lectura útil de la duration modificada: *"si el rendimiento sube
        de 10% a 11%, este bono vale X% menos"*.
        """
        if self.duration_modificada is None:
            return None
        return -self.duration_modificada


def tir_esperada(cron, precio: float, nominales: float = 100.0,
                 moneda: str = "USD", hoy: date | None = None) -> float | None:
    """TIR anual efectiva: el precio de hoy contra los pagos que faltan.

    `precio` es **por la misma cantidad de nominales** que `nominales`, y en la
    **misma moneda** que los flujos del bono. Se piden explícitos porque
    adivinarlos es el error que no se nota: mezclar el precio en pesos con
    flujos en dólares da un número plausible y equivocado.

    Devuelve ``None`` si no hay pagos futuros o si el precio no es positivo —
    nunca lanza y nunca inventa.
    """
    if cron is None or not precio or precio <= 0:
        return None
    hoy = hoy or date.today()
    base = float(getattr(cron, "nominales", 100.0) or 100.0)
    escala = float(nominales) / base

    flujos: list[tuple[date, float]] = [(hoy, -abs(float(precio)))]
    for f in cron.flujos:
        if f.fecha <= hoy:
            continue
        flujos.append((f.fecha, f.total * escala))

    if len(flujos) < 2:
        return None
    return _tir_biseccion(flujos)


def duration(cron, tasa: float | None, nominales: float = 100.0,
             hoy: date | None = None) -> tuple[float | None, float | None]:
    """``(Macaulay, modificada)`` en años, descontando a `tasa`.

    **Macaulay** es el plazo promedio de los pagos, ponderado por su valor
    presente: cuánto tarda en promedio en volver la plata. **Modificada** es la
    sensibilidad: cuánto se mueve el precio ante un cambio de tasa.

    Sin una `tasa` no hay duration posible — descontar a cero trataría un pago
    de 2038 igual que uno de mañana. Devuelve ``(None, None)``.
    """
    if cron is None or tasa is None:
        return None, None
    hoy = hoy or date.today()
    base = float(getattr(cron, "nominales", 100.0) or 100.0)
    escala = float(nominales) / base

    vp_total = 0.0
    vp_por_tiempo = 0.0
    for f in cron.flujos:
        if f.fecha <= hoy:
            continue
        anios = (f.fecha - hoy).days / 365.0
        try:
            vp = (f.total * escala) / ((1.0 + tasa) ** anios)
        except (OverflowError, ZeroDivisionError):
            return None, None
        vp_total += vp
        vp_por_tiempo += vp * anios

    if vp_total <= 0:
        return None, None
    macaulay = vp_por_tiempo / vp_total
    return macaulay, macaulay / (1.0 + tasa)


def riesgo(cron, precio: float | None, nominales: float = 100.0,
           moneda: str = "USD", hoy: date | None = None) -> Riesgo:
    """TIR + duration de un bono, juntas.

    **Van juntas a propósito**: la duration se descuenta a la TIR, así que una
    duration calculada con otra tasa no es comparable con esa TIR. Separarlas
    invitaría a mezclarlas.
    """
    ticker = getattr(cron, "ticker", "") if cron is not None else ""
    if cron is None or not precio:
        return Riesgo(ticker=ticker, moneda=moneda, precio=precio)

    t = tir_esperada(cron, precio, nominales, moneda, hoy)
    mac, mod = duration(cron, t, nominales, hoy)
    return Riesgo(ticker=ticker, tir=t, duration=mac,
                  duration_modificada=mod, moneda=moneda, precio=precio)
