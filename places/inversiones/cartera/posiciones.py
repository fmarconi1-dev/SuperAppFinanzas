"""Posiciones de cartera a partir de los movimientos (replica Resumen Cartera).

Regla portada del Excel (hoja `Resumen Cartera`, columnas E/F/G):

    Cant Comprada = Σ cantidad   sobre (categoría=COMPRA, es_instrumento)
    Cant Vendida  = Σ cantidad   sobre (categoría=VENTA,  es_instrumento)   [<0]
    Cant Actual   = Comprada + Vendida

Todo agrupado por ``ticker_base``. Los espejos de dividendo no afectan la
cantidad (no son COMPRA/VENTA). Los saldos iniciales sintéticos SÍ cuentan
(entran como COMPRA). El costo en ARS se acumula como referencia; el costo en
USD con TC MEP histórico llega con el paso 3 (market_data).

Módulo puro: no toca la DB. `posiciones()` opera sobre objetos del parser;
`posiciones_desde_db()` sobre filas de `cartera_movimientos`.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Posicion", "posiciones", "posiciones_desde_db"]


#: Flujos cobrados que son rendimiento del instrumento (regla del LEEME:
#: "Rendimiento = Realizado en ventas + No realizado + Dividendos +
#: Amortizaciones / Costo total invertido"). Los espejos ARS de dividendo se
#: excluyen antes de llegar acá.
CATEGORIAS_FLUJO = ("AMORTIZACION", "RENTA", "DIVIDENDO")


@dataclass
class Posicion:
    ticker: str
    cant_comprada: float = 0.0
    cant_vendida: float = 0.0
    costo_ars_compras: float = 0.0   # Σ -monto de compras en ARS
    costo_usd_hist: float = 0.0      # Σ -monto/TC de SU fecha (ADR-0003/0004)
    ingreso_ars_ventas: float = 0.0  # Σ monto de ventas (ARS)
    ingreso_usd_ventas: float = 0.0  # ídem al TC de cada venta
    flujos_ars: float = 0.0          # amortizaciones + rentas + dividendos
    flujos_usd: float = 0.0          # ídem al TC de cada cobro
    #: False cuando el instrumento está marcado inactivo en Config
    #: (vencido/canjeado): su tenencia ya no existe aunque los movimientos
    #: históricos sigan en la DB.
    activo: bool = True

    @property
    def cant_remanente(self) -> float:
        """Unidades compradas menos vendidas, sin considerar vencimientos."""
        return round(self.cant_comprada + self.cant_vendida, 8)

    @property
    def cant_actual(self) -> float:
        """Unidades en cartera. Un instrumento vencido no tiene tenencia:
        amortizó (devolvió el capital) sin registrar una venta que descuente
        cantidad — el broker manda AMORTIZACION con cantidad 0."""
        if not self.activo:
            return 0.0
        return self.cant_remanente

    @property
    def cant_amortizada(self) -> float:
        """Unidades que se cerraron por vencimiento (no por venta)."""
        return 0.0 if self.activo else self.cant_remanente

    @property
    def costo_amortizado_ars(self) -> float:
        """Costo del capital que amortizó al vencer.

        La amortización devuelve **capital + interés**: para medir rendimiento
        hay que restarle el capital que se había invertido en esas unidades,
        igual que se descuenta el costo en una venta.
        """
        return (self.ppc_ars or 0.0) * self.cant_amortizada

    @property
    def costo_amortizado_usd(self) -> float:
        return (self.ppc_usd_hist or 0.0) * self.cant_amortizada

    @property
    def ppc_ars(self) -> float | None:
        """Precio promedio ponderado de compra en ARS (costo promedio: ADR-0003)."""
        if not self.cant_comprada:
            return None
        return self.costo_ars_compras / self.cant_comprada

    @property
    def ppc_usd_hist(self) -> float | None:
        """PPC en USD usando el TC de cada compra (más fiel que el MEP único)."""
        if not self.cant_comprada:
            return None
        return self.costo_usd_hist / self.cant_comprada

    @property
    def costo_ars_posicion(self) -> float:
        """Costo de lo que TODAVÍA se tiene, a costo promedio ponderado."""
        ppc = self.ppc_ars
        return (ppc or 0.0) * self.cant_actual

    @property
    def costo_usd_posicion(self) -> float:
        ppc = self.ppc_usd_hist
        return (ppc or 0.0) * self.cant_actual


def _acumular(filas, instrumentos: dict | None = None) -> dict[str, Posicion]:
    """Núcleo del cálculo. `filas`: iterable de tuplas
    (es_instrumento, categoria, ticker_base, cantidad, monto, moneda, tc_mep,
     es_espejo).

    Cada importe se acumula en ARS y en USD **al TC de su propia fecha**
    (ADR-0003/0004): así el rendimiento en dólares refleja el tipo de cambio
    del día de cada compra, venta y cobro.
    """
    instrumentos = instrumentos or {}
    pos: dict[str, Posicion] = {}

    def _p(base: str) -> Posicion:
        p = pos.get(base)
        if p is None:
            inst = instrumentos.get(base)
            p = pos[base] = Posicion(
                base, activo=True if inst is None else bool(getattr(inst, "activo", True))
            )
        return p

    for es_inst, categoria, base, cantidad, monto, moneda, tc, es_espejo in filas:
        if not es_inst or es_espejo:
            continue
        if categoria == "COMPRA":
            p = _p(base)
            p.cant_comprada += cantidad
            if moneda == "ARS":
                p.costo_ars_compras += -monto
                if tc:
                    p.costo_usd_hist += -monto / tc
            else:  # compra ya denominada en USD
                p.costo_usd_hist += -monto
                if tc:
                    p.costo_ars_compras += -monto * tc
        elif categoria == "VENTA":
            p = _p(base)
            p.cant_vendida += cantidad          # negativa
            if moneda == "ARS":
                p.ingreso_ars_ventas += monto
                if tc:
                    p.ingreso_usd_ventas += monto / tc
            else:
                p.ingreso_usd_ventas += monto
                if tc:
                    p.ingreso_ars_ventas += monto * tc
        elif categoria in CATEGORIAS_FLUJO:
            # Cobros del instrumento: amortización (capital), renta (cupón) y
            # dividendos. Son rendimiento, no cambian la cantidad.
            p = _p(base)
            if moneda == "ARS":
                p.flujos_ars += monto
                if tc:
                    p.flujos_usd += monto / tc
            else:
                p.flujos_usd += monto
                if tc:
                    p.flujos_ars += monto * tc
    return pos


def posiciones(movimientos, instrumentos: dict | None = None) -> dict[str, Posicion]:
    """Posiciones desde objetos :class:`Movimiento` del parser.

    Los objetos del parser no tienen TC (se congela al importar), así que los
    importes en USD quedan en 0 salvo los ya denominados en USD.
    """
    return _acumular(
        ((m.es_instrumento, m.categoria, m.ticker_base, m.cantidad, m.monto,
          m.moneda, getattr(m, "tc_mep", None), m.es_espejo)
         for m in movimientos),
        instrumentos,
    )


def posiciones_desde_db(
    conn, user_id: int, instrumentos: dict | None = None
) -> dict[str, Posicion]:
    """Posiciones desde `cartera_movimientos` para un usuario.

    Si no se pasan `instrumentos`, se leen de `cartera_instrumentos` para
    saber cuáles están vencidos/inactivos (columna `activo`).
    """
    if instrumentos is None:
        instrumentos = {
            r["ticker"]: _InstrumentoMin(bool(r["activo"]))
            for r in conn.execute(
                "SELECT ticker, activo FROM cartera_instrumentos WHERE user_id = ?",
                (user_id,),
            )
        }
    filas = conn.execute(
        "SELECT es_instrumento, categoria, ticker_base, cantidad, monto, moneda, "
        "       tc_mep, es_espejo "
        "FROM cartera_movimientos WHERE user_id = ?",
        (user_id,),
    )
    return _acumular(
        ((bool(r["es_instrumento"]), r["categoria"], r["ticker_base"],
          r["cantidad"], r["monto"], r["moneda"], r["tc_mep"],
          bool(r["es_espejo"])) for r in filas),
        instrumentos,
    )


@dataclass(frozen=True)
class _InstrumentoMin:
    """Lo mínimo que `_acumular` necesita saber de un instrumento."""
    activo: bool = True


@dataclass
class CapitalAportado:
    """Plata que entró y salió de la cuenta — el capital REAL del inversor.

    No confundir con la suma de compras: si se compra, se vende y se vuelve a
    comprar, esa suma cuenta la misma plata varias veces (capital *rotado*).
    El denominador honesto del rendimiento es lo aportado neto.

    Incluye los saldos iniciales sintéticos: representan lo que ya se tenía
    al abrir el registro, y también es capital propio.
    """
    depositos_ars: float = 0.0
    depositos_usd: float = 0.0
    retiros_ars: float = 0.0      # negativo
    retiros_usd: float = 0.0      # negativo

    @property
    def neto_ars(self) -> float:
        return self.depositos_ars + self.retiros_ars

    @property
    def neto_usd(self) -> float:
        return self.depositos_usd + self.retiros_usd


def saldos_efectivo(conn, user_id: int) -> tuple[float, float]:
    """Efectivo en la cuenta (ARS, USD), reconstruido desde los movimientos.

    Cada movimiento mueve plata de una sola moneda: se suman por separado.
    Verificado contra la tenencia real del broker (ARS $27.530 calculado vs
    $26.068 informado; USD 71 vs 54,5) — el desvío es el ruido de los
    movimientos que el export no detalla.
    """
    ars = usd = 0.0
    for r in conn.execute(
        "SELECT moneda, SUM(monto) s FROM cartera_movimientos "
        "WHERE user_id = ? AND es_espejo = 0 GROUP BY moneda",
        (user_id,),
    ):
        if r["moneda"] == "USD":
            usd += r["s"] or 0.0
        else:
            ars += r["s"] or 0.0
    return ars, usd


def capital_aportado(conn, user_id: int) -> CapitalAportado:
    """Depósitos y retiros del usuario, en ARS y en USD al TC de cada fecha."""
    cap = CapitalAportado()
    filas = conn.execute(
        "SELECT categoria, moneda, monto, tc_mep FROM cartera_movimientos "
        "WHERE user_id = ? AND categoria IN ('DEPOSITO', 'RETIRO')",
        (user_id,),
    )
    for r in filas:
        monto, tc, moneda = r["monto"], r["tc_mep"], r["moneda"]
        if moneda == "USD":
            usd, ars = monto, (monto * tc if tc else 0.0)
        else:
            ars, usd = monto, (monto / tc if tc else 0.0)
        if r["categoria"] == "DEPOSITO":
            cap.depositos_ars += ars
            cap.depositos_usd += usd
        else:
            cap.retiros_ars += ars
            cap.retiros_usd += usd
    return cap
