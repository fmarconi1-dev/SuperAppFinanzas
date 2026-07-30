"""Rendimientos de la caja: cauciones, cuenta remunerada y dividendos.

**Qué problema resuelve.** La plata que no está invertida en un instrumento
igual rinde: Franco coloca cauciones casi todos los días y cobra dividendos.
Ese rendimiento **ya está dentro del patrimonio** (engorda el efectivo), pero
hasta ahora era invisible: las cauciones no son instrumentos —`es_instrumento`
es False, pseudo-ticker ``CC``— así que ni aparecían en la tabla de posiciones
ni tenían una tasa propia. Este módulo las hace visibles y les pone número.

⚠️ **Esto es atribución, no plata nueva.** El interés de las cauciones y la
remuneración ya están contados en el efectivo, y los dividendos ya están en
los flujos de cada instrumento. Mostrarlos acá **no** cambia el patrimonio ni
el resultado total: explica de dónde viene una parte.

**Cómo vienen los datos** (verificado sobre los 585 movimientos reales):

* La colocación (``CAUCION_COL``, monto negativo) y su vencimiento
  (``CAUCION_VTO``, monto positivo) **comparten la fecha de concertación**;
  lo que cambia es la de liquidación, y esa diferencia **es el plazo**.
  101 pares, sin una sola huérfana.
* El interés es ``cobrado − colocado``. Los plazos reales son de 1, 2, 3 y 5
  días (fines de semana y feriados).

**La tasa se pondera por capital y tiempo.** Promediar las TNA de cada caución
daría el mismo peso a una de $20.000 por un día que a una de $2,7 millones por
cinco. La tasa honesta es ``interés total / (Σ capital × días / 365)``.

Módulo puro: sin DB ni red. Los adaptadores solo traducen filas a eventos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

__all__ = [
    "Caucion", "ResumenCauciones", "DividendoTicker",
    "cauciones", "resumir_cauciones", "dividendos_por_ticker",
    "total_remuneracion", "cauciones_desde_db", "flujos_caja_desde_db",
]


@dataclass
class Caucion:
    """Una colocación con su vencimiento apareado."""

    fecha: date                      # concertación (la comparten ambas patas)
    capital: float                   # lo colocado, positivo
    cobrado: float                   # lo que volvió al vencer
    moneda: str = "ARS"
    dias: int | None = None          # entre las dos fechas de liquidación
    tc_mep: float | None = None      # MEP del día, para el plano en dólares
    #: Colocada pero todavía sin vencimiento en los movimientos: o está viva,
    #: o el export se cortó antes. No se le puede calcular tasa.
    abierta: bool = False

    @property
    def interes(self) -> float:
        return self.cobrado - self.capital

    @property
    def tna(self) -> float | None:
        """Tasa nominal anual de ESTA caución.

        Ojo al leerla de a una: en montos chicos y plazos de un día, unos pesos
        de redondeo mueven la tasa decenas de puntos. La medida representativa
        de la cartera es la ponderada de :class:`ResumenCauciones`.
        """
        if self.abierta or not self.dias or not self.capital:
            return None
        return (self.interes / self.capital) * (365.0 / self.dias)

    @property
    def interes_usd(self) -> float | None:
        if not self.tc_mep:
            return None
        return self.interes / self.tc_mep if self.moneda == "ARS" else self.interes


@dataclass
class ResumenCauciones:
    """Totales de las cauciones. La tasa va ponderada por capital y tiempo."""

    n: int = 0
    abiertas: int = 0
    capital_rotado: float = 0.0      # suma de lo colocado (NO es capital propio)
    interes: float = 0.0
    interes_usd: float = 0.0
    #: Σ capital × días / 365 — el denominador correcto de la tasa.
    base_capital_tiempo: float = 0.0
    primera: date | None = None
    ultima: date | None = None
    por_anio: dict[int, tuple[int, float, float | None]] = field(
        default_factory=dict)   # {año: (n, interés, tna_ponderada)}

    @property
    def tna_ponderada(self) -> float | None:
        """La tasa que realmente se ganó, pesando cada caución por su tamaño
        y su plazo. Es la única comparable contra un plazo fijo."""
        if not self.base_capital_tiempo:
            return None
        return self.interes / self.base_capital_tiempo


@dataclass
class DividendoTicker:
    """Dividendos de un instrumento, brutos y netos de retención."""

    ticker: str
    n: int = 0
    bruto: float = 0.0
    retencion: float = 0.0           # negativa
    bruto_usd: float = 0.0
    retencion_usd: float = 0.0
    monedas: set = field(default_factory=set)

    @property
    def neto(self) -> float:
        return self.bruto + self.retencion

    @property
    def neto_usd(self) -> float:
        return self.bruto_usd + self.retencion_usd

    @property
    def retencion_pct(self) -> float | None:
        if not self.bruto:
            return None
        return abs(self.retencion) / self.bruto * 100.0


# ---------------------------------------------------------------------------
# Cauciones
# ---------------------------------------------------------------------------

def cauciones(filas) -> list[Caucion]:
    """Aparea colocaciones con vencimientos.

    `filas`: iterable de tuplas ``(categoria, fecha_concertacion,
    fecha_liquidacion, monto, moneda, tc_mep)``.

    **Regla de apareo: la fecha de concertación**, que ambas patas comparten
    (verificado en los 101 pares reales). Si algún día hubiera **varias** en la
    misma fecha, se aparean ordenadas por monto — la de mayor capital con el
    mayor cobro —, que es la única correspondencia posible sin más datos.

    Nunca inventa la contraparte: una colocación sin vencimiento queda
    ``abierta`` (está viva o el export se cortó), y un vencimiento sin
    colocación —una caución colocada antes del inicio del registro— se
    **descarta con el resto**, porque sin capital no hay tasa que calcular.
    """
    col: dict[date, list] = {}
    vto: dict[date, list] = {}
    for categoria, f_con, f_liq, monto, moneda, tc in filas:
        f_con = _a_fecha(f_con)
        if f_con is None:
            continue
        destino = col if categoria == "CAUCION_COL" else (
            vto if categoria == "CAUCION_VTO" else None)
        if destino is None:
            continue
        destino.setdefault(f_con, []).append(
            (abs(monto or 0.0), _a_fecha(f_liq), moneda or "ARS", tc))

    out: list[Caucion] = []
    for f in sorted(col):
        cs = sorted(col[f], key=lambda x: -x[0])
        vs = sorted(vto.get(f, []), key=lambda x: -x[0])
        for i, (capital, liq_c, moneda, tc) in enumerate(cs):
            if i < len(vs):
                cobrado, liq_v, _, _ = vs[i]
                dias = ((liq_v - liq_c).days
                        if (liq_v is not None and liq_c is not None) else None)
                out.append(Caucion(f, capital, cobrado, moneda, dias, tc))
            else:
                out.append(Caucion(f, capital, capital, moneda, None, tc,
                                   abierta=True))
    return out


def resumir_cauciones(cs: list[Caucion]) -> ResumenCauciones:
    r = ResumenCauciones(n=len(cs))
    por_anio: dict[int, list[Caucion]] = {}
    for c in cs:
        por_anio.setdefault(c.fecha.year, []).append(c)
        if c.abierta:
            r.abiertas += 1
            continue
        r.capital_rotado += c.capital
        r.interes += c.interes
        r.interes_usd += c.interes_usd or 0.0
        if c.dias:
            r.base_capital_tiempo += c.capital * c.dias / 365.0
    fechas = [c.fecha for c in cs]
    if fechas:
        r.primera, r.ultima = min(fechas), max(fechas)
    for anio, lista in sorted(por_anio.items()):
        vivas = [c for c in lista if not c.abierta and c.dias]
        interes = sum(c.interes for c in vivas)
        base = sum(c.capital * c.dias / 365.0 for c in vivas)
        r.por_anio[anio] = (len(lista), interes, (interes / base) if base else None)
    return r


# ---------------------------------------------------------------------------
# Dividendos y cuenta remunerada
# ---------------------------------------------------------------------------

def dividendos_por_ticker(filas) -> dict[str, DividendoTicker]:
    """Dividendos cobrados por instrumento, **netos de retención**.

    `filas`: ``(categoria, ticker_base, monto, moneda, tc_mep, es_espejo)``.

    La retención se resta del bruto del mismo ticker: el dividendo que entra a
    la cuenta es el neto, y mostrar solo el bruto sobreestima lo cobrado. Los
    espejos en pesos de los dividendos en dólares se ignoran (regla del LEEME).
    """
    out: dict[str, DividendoTicker] = {}

    def _d(t: str) -> DividendoTicker:
        d = out.get(t)
        if d is None:
            d = out[t] = DividendoTicker(t)
        return d

    for categoria, ticker, monto, moneda, tc, espejo in filas:
        if espejo or categoria not in ("DIVIDENDO", "RETENCION"):
            continue
        monto = monto or 0.0
        if moneda == "USD":
            ars, usd = (monto * tc if tc else 0.0), monto
        else:
            ars, usd = monto, (monto / tc if tc else 0.0)
        d = _d(ticker)
        d.monedas.add(moneda)
        if categoria == "DIVIDENDO":
            d.n += 1
            d.bruto += ars
            d.bruto_usd += usd
        else:
            d.retencion += ars
            d.retencion_usd += usd
    return out


def total_remuneracion(filas) -> tuple[float, float, int]:
    """Rendimiento de la cuenta remunerada: ``(ars, usd, cantidad)``.

    `filas`: ``(categoria, monto, moneda, tc_mep)``.
    """
    ars = usd = 0.0
    n = 0
    for categoria, monto, moneda, tc in filas:
        if categoria != "REMUNERACION":
            continue
        n += 1
        monto = monto or 0.0
        if moneda == "USD":
            usd += monto
            ars += monto * tc if tc else 0.0
        else:
            ars += monto
            usd += monto / tc if tc else 0.0
    return ars, usd, n


# ---------------------------------------------------------------------------
# Adaptadores
# ---------------------------------------------------------------------------

def cauciones_desde_db(conn, user_id: int) -> list[Caucion]:
    filas = conn.execute(
        "SELECT categoria, fecha_concertacion, fecha_liquidacion, monto, "
        "       moneda, tc_mep "
        "FROM cartera_movimientos "
        "WHERE user_id = ? AND categoria IN ('CAUCION_COL', 'CAUCION_VTO')",
        (user_id,),
    )
    return cauciones(
        (r["categoria"], r["fecha_concertacion"], r["fecha_liquidacion"],
         r["monto"], r["moneda"], r["tc_mep"])
        for r in filas
    )


def flujos_caja_desde_db(conn, user_id: int):
    """``(dividendos_por_ticker, (rem_ars, rem_usd, n))`` en una sola pasada."""
    filas = conn.execute(
        "SELECT categoria, ticker_base, monto, moneda, tc_mep, es_espejo "
        "FROM cartera_movimientos "
        "WHERE user_id = ? AND categoria IN "
        "      ('DIVIDENDO', 'RETENCION', 'REMUNERACION')",
        (user_id,),
    ).fetchall()
    divs = dividendos_por_ticker(
        (r["categoria"], r["ticker_base"], r["monto"], r["moneda"],
         r["tc_mep"], bool(r["es_espejo"])) for r in filas
    )
    rem = total_remuneracion(
        (r["categoria"], r["monto"], r["moneda"], r["tc_mep"]) for r in filas
    )
    return divs, rem


def _a_fecha(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
