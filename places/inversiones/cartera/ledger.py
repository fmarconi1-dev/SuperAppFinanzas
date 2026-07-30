"""Motor cronológico de la cartera — la línea de tiempo (Fase 3b, paso 1).

**Por qué existe.** `posiciones.py` agrega *sin orden temporal*: suma todas las
compras, todas las ventas y todos los flujos, y recién al final divide para
obtener el precio promedio ponderado (PPC). Eso hace que el PPC con el que se
valúa una venta incluya **compras posteriores a esa venta**: si se compró,
se vendió y se volvió a comprar más caro, la recompra infla el costo de la
venta anterior y el resultado realizado queda mal atribuido.

El total de la cartera **no** depende de esto (el método del patrimonio es
inmune: patrimonio − aportado), pero la atribución por operación sí. Este
módulo recorre los movimientos **en orden de fecha** manteniendo un PPC
**móvil**, y emite una :class:`Realizacion` por cada cierre. Es la base común
de los cuatro puntos de la Fase 3b:

  1. amortizaciones parciales → un evento más de esta misma línea de tiempo;
  2. resultado realizado por operación → la salida directa de este módulo;
  3. cauciones y dividendos con su tasa → eventos fechados con capital y plazo;
  4. análisis por sector / tipo de renta → agrupaciones de lo anterior.

**Convención de amortización (dato de dominio, Franco 2026-07-30).** En
Argentina la amortización de un bono se refleja en el **precio**, nunca en los
nominales: el broker deja la cantidad quieta y el precio absorbe la devolución
de capital. Por eso AMORTIZACION **no** toca cantidad ni costo acá — solo
registra el cobro. Si algún día apareciera un custodio que reduce nominales,
la diferencia contra la foto del broker lo delataría en la reconciliación.

Módulo **puro**: no toca la DB ni la red. `recorrer()` opera sobre eventos;
los adaptadores solo traducen (objetos del parser o filas de
`cartera_movimientos`) a eventos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

__all__ = [
    "Evento", "Realizacion", "EstadoTicker", "Ledger",
    "recorrer", "eventos_desde_movimientos", "eventos_desde_db",
]


#: Cobros que no cambian la tenencia: son renta del instrumento, no capital
#: que entra o sale de la posición. (Ver la nota de convención en el módulo.)
CATEGORIAS_FLUJO = ("AMORTIZACION", "RENTA", "DIVIDENDO")

#: Orden dentro de un mismo día. El export del broker no trae hora, así que
#: ante empate se procesa primero lo que **aporta** unidades y después lo que
#: las consume: si no, una venta liquidada el mismo día que su compra quedaría
#: sin costo contra el cual medirse.
_PRIORIDAD = {"COMPRA": 0, "VENTA": 1}


@dataclass(frozen=True)
class Evento:
    """Un movimiento ya normalizado, listo para la línea de tiempo."""

    fecha: date
    categoria: str
    ticker: str
    cantidad: float          # + compras, − ventas (signo del export)
    monto: float             # − compras, + ventas/cobros (signo del export)
    moneda: str              # "ARS" | "USD"
    tc_mep: float | None     # MEP congelado de SU fecha (ADR-0004)

    @property
    def importes(self) -> tuple[float, float]:
        """El monto en (ARS, USD) al TC de su propia fecha.

        Devuelve el valor absoluto con el signo original: quien consume decide
        si lo suma como costo o como ingreso.
        """
        if self.moneda == "USD":
            return (self.monto * self.tc_mep if self.tc_mep else 0.0), self.monto
        return self.monto, (self.monto / self.tc_mep if self.tc_mep else 0.0)


@dataclass
class Realizacion:
    """Un cierre de posición: resultado ya materializado, con su fecha.

    El costo se libera al **PPC vigente al momento del cierre** — no al PPC
    de toda la historia. Esa es la diferencia con `posiciones.py`.
    """

    ticker: str
    fecha: date
    motivo: str                  # "VENTA" (más adelante: "AMORTIZACION")
    cantidad: float              # unidades cerradas (positivo)
    ingreso_ars: float = 0.0
    ingreso_usd: float = 0.0
    costo_ars: float = 0.0       # capital liberado (PPC móvil × cantidad)
    costo_usd: float = 0.0
    ppc_ars: float | None = None    # PPC vigente al cerrar
    ppc_usd: float | None = None
    #: Fecha de adquisición promedio ponderada por costo de las unidades que
    #: se cierran. Con costo promedio no hay "un" lote, así que el plazo de
    #: tenencia se mide contra ese promedio.
    fecha_compra_prom: date | None = None
    #: True si se vendió más de lo que la línea de tiempo tenía registrado
    #: (pagarés sin cantidad en el movimiento, ajustes de ratio de CEDEAR sin
    #: movimiento). El excedente se cierra a costo cero y queda marcado.
    descubierta: bool = False

    @property
    def resultado_ars(self) -> float:
        return self.ingreso_ars - self.costo_ars

    @property
    def resultado_usd(self) -> float:
        return self.ingreso_usd - self.costo_usd

    @property
    def rendimiento_pct(self) -> float | None:
        if not self.costo_ars:
            return None
        return self.resultado_ars / self.costo_ars * 100.0

    @property
    def rendimiento_usd_pct(self) -> float | None:
        if not self.costo_usd:
            return None
        return self.resultado_usd / self.costo_usd * 100.0

    @property
    def dias(self) -> int | None:
        """Plazo de tenencia contra la fecha de compra promedio."""
        if self.fecha_compra_prom is None:
            return None
        return (self.fecha - self.fecha_compra_prom).days


@dataclass
class EstadoTicker:
    """Lo que la línea de tiempo sabe de un ticker en un instante dado."""

    ticker: str
    cantidad: float = 0.0
    costo_ars: float = 0.0       # costo de lo que TODAVÍA se tiene
    costo_usd: float = 0.0
    #: Acumulador para la fecha de compra promedio (Σ costo × días).
    _peso_fecha: float = 0.0
    _origen: date | None = None
    #: Cobros del instrumento (no cambian la tenencia).
    flujos_ars: float = 0.0
    flujos_usd: float = 0.0
    #: Retenciones impositivas (negativas) — se guardan aparte para poder
    #: mostrar el dividendo bruto y el neto (punto 3 de la Fase 3b).
    retenciones_ars: float = 0.0
    retenciones_usd: float = 0.0
    realizaciones: list[Realizacion] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    @property
    def ppc_ars(self) -> float | None:
        if abs(self.cantidad) < 1e-12:
            return None
        return self.costo_ars / self.cantidad

    @property
    def ppc_usd(self) -> float | None:
        if abs(self.cantidad) < 1e-12:
            return None
        return self.costo_usd / self.cantidad

    @property
    def fecha_compra_prom(self) -> date | None:
        """Fecha de adquisición promedio ponderada por costo."""
        if self._origen is None or abs(self.costo_ars) < 1e-9:
            return None
        from datetime import timedelta
        return self._origen + timedelta(days=self._peso_fecha / self.costo_ars)

    @property
    def realizado_ars(self) -> float:
        return sum(r.resultado_ars for r in self.realizaciones)

    @property
    def realizado_usd(self) -> float:
        return sum(r.resultado_usd for r in self.realizaciones)


@dataclass
class Ledger:
    """Resultado de recorrer la línea de tiempo."""

    estados: dict[str, EstadoTicker] = field(default_factory=dict)
    realizaciones: list[Realizacion] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    @property
    def realizado_ars(self) -> float:
        return sum(r.resultado_ars for r in self.realizaciones)

    @property
    def realizado_usd(self) -> float:
        return sum(r.resultado_usd for r in self.realizaciones)

    def por_ticker(self, ticker: str) -> list[Realizacion]:
        return [r for r in self.realizaciones if r.ticker == ticker]


# ---------------------------------------------------------------------------
# El recorrido
# ---------------------------------------------------------------------------

def recorrer(eventos) -> Ledger:
    """Recorre los eventos **en orden de fecha** con PPC móvil.

    Reglas (portadas del Excel pero con cronología, que el Excel no tiene):

    * **COMPRA** — suma unidades y suma costo. Una compra sin cantidad
      (pagarés: el movimiento trae el monto pero no las unidades) suma costo
      igual y deja advertencia: sin unidades no hay PPC posible.
    * **VENTA** — libera ``PPC vigente × unidades vendidas`` y emite una
      :class:`Realizacion`. Si se vende más de lo registrado, se cierra lo que
      hay y el excedente se marca ``descubierta`` (nunca se inventa costo).
    * **AMORTIZACION / RENTA / DIVIDENDO** — se registran como cobro y **no**
      tocan la tenencia (convención argentina: la amortización va por precio).
    * **RETENCION** — se acumula aparte para poder netear el dividendo.

    El orden es estable: ante misma fecha, primero las compras.
    """
    led = Ledger()
    for ev in sorted(eventos, key=lambda e: (e.fecha, _PRIORIDAD.get(e.categoria, 2))):
        est = led.estados.get(ev.ticker)
        if est is None:
            est = led.estados[ev.ticker] = EstadoTicker(ev.ticker)
        ars, usd = ev.importes

        if ev.categoria == "COMPRA":
            _comprar(est, ev, -ars, -usd)
        elif ev.categoria == "VENTA":
            r = _vender(est, ev, ars, usd)
            if r is not None:
                led.realizaciones.append(r)
        elif ev.categoria in CATEGORIAS_FLUJO:
            est.flujos_ars += ars
            est.flujos_usd += usd
        elif ev.categoria == "RETENCION":
            est.retenciones_ars += ars
            est.retenciones_usd += usd

    for est in led.estados.values():
        led.advertencias.extend(f"{est.ticker}: {a}" for a in est.advertencias)
    return led


def _comprar(est: EstadoTicker, ev: Evento, costo_ars: float, costo_usd: float) -> None:
    if est._origen is None:
        est._origen = ev.fecha
    est._peso_fecha += costo_ars * (ev.fecha - est._origen).days
    est.cantidad += ev.cantidad
    est.costo_ars += costo_ars
    est.costo_usd += costo_usd
    if abs(ev.cantidad) < 1e-12 and abs(costo_ars) > 1e-9:
        est.advertencias.append(
            f"compra del {ev.fecha} sin cantidad en el movimiento "
            f"(costo {costo_ars:,.2f} ARS): el PPC necesita la tenencia del broker"
        )


def _vender(est: EstadoTicker, ev: Evento, ingreso_ars: float,
            ingreso_usd: float) -> Realizacion | None:
    unidades = -ev.cantidad            # el export trae las ventas en negativo
    if abs(unidades) < 1e-12:
        return None

    disponibles = est.cantidad
    descubierta = unidades - disponibles > 1e-9
    cerradas = min(unidades, disponibles) if disponibles > 0 else 0.0
    ppc_ars, ppc_usd = est.ppc_ars, est.ppc_usd
    costo_ars = (ppc_ars or 0.0) * cerradas
    costo_usd = (ppc_usd or 0.0) * cerradas

    if descubierta:
        est.advertencias.append(
            f"venta del {ev.fecha} de {unidades:,.4f} unidades con solo "
            f"{disponibles:,.4f} registradas: el excedente se cierra sin costo"
        )

    r = Realizacion(
        ticker=est.ticker, fecha=ev.fecha, motivo="VENTA", cantidad=unidades,
        ingreso_ars=ingreso_ars, ingreso_usd=ingreso_usd,
        costo_ars=costo_ars, costo_usd=costo_usd,
        ppc_ars=ppc_ars, ppc_usd=ppc_usd,
        fecha_compra_prom=est.fecha_compra_prom, descubierta=descubierta,
    )
    est.realizaciones.append(r)

    # El costo promedio no cambia al vender: se libera la parte proporcional.
    if est._origen is not None and abs(est.costo_ars) > 1e-9:
        est._peso_fecha -= est._peso_fecha * (costo_ars / est.costo_ars)
    est.cantidad -= unidades
    est.costo_ars -= costo_ars
    est.costo_usd -= costo_usd
    if abs(est.cantidad) < 1e-9:       # posición cerrada: no queda costo vivo
        est.cantidad = 0.0
        est.costo_ars = est.costo_usd = est._peso_fecha = 0.0
    return r


# ---------------------------------------------------------------------------
# Adaptadores (lo único que sabe de dónde vienen los datos)
# ---------------------------------------------------------------------------

def eventos_desde_movimientos(movimientos) -> list[Evento]:
    """Eventos desde objetos :class:`~...parser.Movimiento`."""
    return [
        Evento(
            fecha=m.fecha_concertacion, categoria=m.categoria,
            ticker=m.ticker_base, cantidad=m.cantidad, monto=m.monto,
            moneda=m.moneda, tc_mep=getattr(m, "tc_mep", None),
        )
        for m in movimientos
        if m.es_instrumento and not m.es_espejo
    ]


def eventos_desde_db(conn, user_id: int) -> list[Evento]:
    """Eventos desde `cartera_movimientos` (solo instrumentos, sin espejos)."""
    out: list[Evento] = []
    for r in conn.execute(
        "SELECT fecha_concertacion f, categoria, ticker_base, cantidad, monto, "
        "       moneda, tc_mep "
        "FROM cartera_movimientos "
        "WHERE user_id = ? AND es_instrumento = 1 AND es_espejo = 0",
        (user_id,),
    ):
        try:
            fecha = datetime.strptime(str(r["f"])[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        out.append(Evento(
            fecha=fecha, categoria=r["categoria"], ticker=r["ticker_base"],
            cantidad=r["cantidad"] or 0.0, monto=r["monto"] or 0.0,
            moneda=r["moneda"], tc_mep=r["tc_mep"],
        ))
    return out
