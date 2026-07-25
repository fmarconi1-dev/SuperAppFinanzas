"""Valuación de la cartera y KPIs (Fase 3a, paso 4).

Toma las posiciones (cantidades, ya reconciliadas contra el Excel) y les
aplica precio de mercado para obtener valor, resultado y rendimiento.

Metodología (ADR-0003):
  * **Costo promedio ponderado** — el costo de lo que se tiene es
    ``PPC × cantidad_actual``.
  * **Dos vistas de USD**: la de la app usa el **TC histórico congelado** por
    operación (más fiel); el modo ``MEP actual`` replica la metodología del
    Excel y es el que se usa para reconciliar.

Módulo puro: recibe precios y TC ya resueltos (sin red, sin DB) → testeable.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PosicionValuada", "KPIs", "valuar", "kpis_de"]


@dataclass
class PosicionValuada:
    ticker: str
    categoria_activo: str
    cantidad: float
    precio: float | None            # precio de mercado (ARS, ya normalizado)
    origen_precio: str              # proveedor | cache | override | sin_dato
    valor_ars: float | None
    costo_ars: float                # a costo promedio ponderado
    ppc_ars: float | None

    @property
    def resultado_ars(self) -> float | None:
        if self.valor_ars is None:
            return None
        return self.valor_ars - self.costo_ars

    @property
    def rendimiento_pct(self) -> float | None:
        r = self.resultado_ars
        if r is None or not self.costo_ars:
            return None
        return r / self.costo_ars * 100.0

    def valor_usd(self, mep: float | None) -> float | None:
        if self.valor_ars is None or not mep:
            return None
        return self.valor_ars / mep


@dataclass
class KPIs:
    valor_total_ars: float = 0.0
    valor_total_usd: float | None = None
    costo_total_ars: float = 0.0
    posiciones_valuadas: int = 0
    posiciones_sin_precio: int = 0

    @property
    def resultado_ars(self) -> float:
        return self.valor_total_ars - self.costo_total_ars

    @property
    def rendimiento_pct(self) -> float | None:
        if not self.costo_total_ars:
            return None
        return self.resultado_ars / self.costo_total_ars * 100.0


def valuar(
    posiciones: dict,
    resolver,
    instrumentos: dict | None = None,
    solo_con_tenencia: bool = True,
) -> list[PosicionValuada]:
    """Valúa cada posición con el precio que devuelva `resolver(ticker, inst)`.

    :param posiciones: ``{ticker: Posicion}`` (de `posiciones.py`).
    :param resolver: callable ``(ticker, instrumento) -> (precio, origen)``.
        Se inyecta para no atar este módulo a la red ni a la DB.
    :param instrumentos: ``{ticker: Instrumento}`` para categoría de activo y
        la regla de bonos ``/100``.
    :param solo_con_tenencia: omite las posiciones cerradas (cantidad 0).
    """
    instrumentos = instrumentos or {}
    out: list[PosicionValuada] = []
    for ticker, pos in posiciones.items():
        cant = pos.cant_actual
        if solo_con_tenencia and abs(cant) < 1e-9:
            continue
        inst = instrumentos.get(ticker)
        precio, origen = resolver(ticker, inst)
        valor = precio * cant if isinstance(precio, (int, float)) else None
        out.append(
            PosicionValuada(
                ticker=ticker,
                categoria_activo=getattr(inst, "categoria_activo", "") or "Otros",
                cantidad=cant,
                precio=precio,
                origen_precio=origen,
                valor_ars=valor,
                costo_ars=pos.costo_ars_posicion,
                ppc_ars=pos.ppc_ars,
            )
        )
    out.sort(key=lambda p: (p.valor_ars is None, -(p.valor_ars or 0)))
    return out


def kpis_de(valuadas: list[PosicionValuada], mep: float | None = None) -> KPIs:
    """Totales de cartera. Solo suma costo de lo que tiene precio, para que
    el rendimiento no compare peras (valor parcial) con manzanas (costo total)."""
    k = KPIs()
    for p in valuadas:
        if p.valor_ars is None:
            k.posiciones_sin_precio += 1
            continue
        k.posiciones_valuadas += 1
        k.valor_total_ars += p.valor_ars
        k.costo_total_ars += p.costo_ars
    k.valor_total_usd = (k.valor_total_ars / mep) if mep else None
    return k
