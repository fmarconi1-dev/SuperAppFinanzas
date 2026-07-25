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


@dataclass
class Posicion:
    ticker: str
    cant_comprada: float = 0.0
    cant_vendida: float = 0.0
    costo_ars_compras: float = 0.0   # Σ -monto de compras en ARS
    costo_usd_hist: float = 0.0      # Σ -monto/TC de SU fecha (ADR-0003/0004)

    @property
    def cant_actual(self) -> float:
        return round(self.cant_comprada + self.cant_vendida, 8)

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


def _acumular(filas) -> dict[str, Posicion]:
    """Núcleo del cálculo. `filas`: iterable de tuplas
    (es_instrumento, categoria, ticker_base, cantidad, monto, moneda, tc_mep)."""
    pos: dict[str, Posicion] = {}
    for es_inst, categoria, base, cantidad, monto, moneda, tc in filas:
        if not es_inst or categoria not in ("COMPRA", "VENTA"):
            continue
        p = pos.get(base)
        if p is None:
            p = pos[base] = Posicion(base)
        if categoria == "COMPRA":
            p.cant_comprada += cantidad
            if moneda == "ARS":
                p.costo_ars_compras += -monto
                # Costo en USD al TC congelado de esa fecha (si ya se congeló).
                if tc:
                    p.costo_usd_hist += -monto / tc
            else:  # compra ya denominada en USD
                p.costo_usd_hist += -monto
                if tc:
                    p.costo_ars_compras += -monto * tc
        else:  # VENTA (cantidad negativa)
            p.cant_vendida += cantidad
    return pos


def posiciones(movimientos) -> dict[str, Posicion]:
    """Posiciones desde objetos :class:`Movimiento` del parser.

    Los objetos del parser no tienen TC (se congela al importar), así que el
    costo en USD queda en 0 salvo las compras ya denominadas en USD.
    """
    return _acumular(
        (m.es_instrumento, m.categoria, m.ticker_base, m.cantidad, m.monto,
         m.moneda, getattr(m, "tc_mep", None))
        for m in movimientos
    )


def posiciones_desde_db(conn, user_id: int) -> dict[str, Posicion]:
    """Posiciones desde `cartera_movimientos` para un usuario."""
    filas = conn.execute(
        "SELECT es_instrumento, categoria, ticker_base, cantidad, monto, moneda, "
        "       tc_mep "
        "FROM cartera_movimientos WHERE user_id = ?",
        (user_id,),
    )
    return _acumular(
        (bool(r["es_instrumento"]), r["categoria"], r["ticker_base"],
         r["cantidad"], r["monto"], r["moneda"], r["tc_mep"])
        for r in filas
    )
