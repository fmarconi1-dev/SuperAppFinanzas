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
    costo_ars: float                # costo de la TENENCIA (promedio ponderado)
    ppc_ars: float | None
    # --- componentes del rendimiento (regla del LEEME) -------------------
    invertido_ars: float = 0.0      # costo total invertido (histórico)
    invertido_usd: float = 0.0      # ídem al TC de cada compra
    realizado_ars: float = 0.0      # resultado de las ventas ya hechas
    realizado_usd: float = 0.0
    flujos_ars: float = 0.0         # amortizaciones + rentas + dividendos
    flujos_usd: float = 0.0
    valor_usd_actual: float | None = None   # tenencia valuada al MEP de hoy
    costo_usd_tenencia: float = 0.0         # costo de la tenencia en USD hist.
    cerrada: bool = False           # vencida/canjeada: ya no hay tenencia
    #: Costo del capital que amortizó al vencer. La amortización devuelve
    #: capital + interés, así que hay que descontarlo para medir rendimiento
    #: (igual que el costo se descuenta en una venta).
    costo_amortizado_ars: float = 0.0
    costo_amortizado_usd: float = 0.0

    # --- no realizado (posición viva) ------------------------------------
    @property
    def no_realizado_ars(self) -> float | None:
        if self.valor_ars is None:
            return None
        return self.valor_ars - self.costo_ars

    @property
    def no_realizado_usd(self) -> float | None:
        if self.valor_usd_actual is None:
            return None
        return self.valor_usd_actual - self.costo_usd_tenencia

    # --- rendimiento total: realizado + no realizado + flujos ------------
    @property
    def resultado_ars(self) -> float | None:
        """Resultado total: ventas + cobros + no realizado − capital amortizado.

        Si la posición está cerrada no hay componente no realizado: todo el
        retorno ya se cobró.
        """
        nr = self.no_realizado_ars
        if nr is None and not self.cerrada:
            return None
        return (
            self.realizado_ars + self.flujos_ars + (nr or 0.0)
            - self.costo_amortizado_ars
        )

    @property
    def resultado_usd(self) -> float | None:
        nr = self.no_realizado_usd
        if nr is None and not self.cerrada:
            return None
        return (
            self.realizado_usd + self.flujos_usd + (nr or 0.0)
            - self.costo_amortizado_usd
        )

    @property
    def rendimiento_pct(self) -> float | None:
        r = self.resultado_ars
        if r is None or not self.invertido_ars:
            return None
        return r / self.invertido_ars * 100.0

    @property
    def rendimiento_usd_pct(self) -> float | None:
        """Rendimiento en dólares: usa el MEP del día de cada operación."""
        r = self.resultado_usd
        if r is None or not self.invertido_usd:
            return None
        return r / self.invertido_usd * 100.0

    def valor_usd(self, mep: float | None) -> float | None:
        if self.valor_ars is None or not mep:
            return None
        return self.valor_ars / mep


@dataclass
class KPIs:
    valor_total_ars: float = 0.0
    valor_total_usd: float | None = None
    costo_total_ars: float = 0.0     # costo de la tenencia viva
    posiciones_valuadas: int = 0
    posiciones_sin_precio: int = 0
    # Rendimiento total de la cartera (incluye lo ya cobrado y lo vendido).
    invertido_ars: float = 0.0
    invertido_usd: float = 0.0
    realizado_ars: float = 0.0
    realizado_usd: float = 0.0
    flujos_ars: float = 0.0
    flujos_usd: float = 0.0
    no_realizado_ars: float = 0.0
    no_realizado_usd: float = 0.0
    costo_amortizado_ars: float = 0.0   # capital devuelto por vencimientos
    costo_amortizado_usd: float = 0.0

    # --- no realizado (lo que se ve en la tenencia de hoy) ---------------
    @property
    def resultado_ars(self) -> float:
        """Resultado NO realizado de la tenencia viva (el que 'se mueve' hoy)."""
        return self.valor_total_ars - self.costo_total_ars

    @property
    def rendimiento_pct(self) -> float | None:
        if not self.costo_total_ars:
            return None
        return self.resultado_ars / self.costo_total_ars * 100.0

    # --- rendimiento total: MÉTODO DEL PATRIMONIO ------------------------
    # Es el único verificable: lo que hoy vale todo (tenencia + efectivo)
    # contra lo que realmente se aportó (depósitos − retiros). No depende de
    # sumar operación por operación, así que no acumula errores ni cuenta dos
    # veces la plata que rota (comprar, vender y volver a comprar).
    #
    # ⚠️ La suma por instrumento NO sirve como total de cartera: al convertir
    # importes en USD a pesos con el TC de cada fecha, la devaluación genera
    # "ganancias" nominales que no son ganancias reales. Se verificó con datos
    # reales: por componentes daba $9,9M contra $2,3M por patrimonio.
    patrimonio_ars: float = 0.0     # tenencia + efectivo, hoy
    patrimonio_usd: float = 0.0
    aportado_ars: float = 0.0       # depósitos − retiros, al TC de cada fecha
    aportado_usd: float = 0.0
    # --- horizonte temporal ---------------------------------------------
    dias: int = 0                   # del primer aporte a la valuación
    tir_ars: float | None = None    # tasa anual efectiva (pondera cada aporte)
    tir_usd: float | None = None

    @property
    def anios(self) -> float:
        return self.dias / 365.0

    @property
    def meses(self) -> float:
        return self.dias / 30.44

    @property
    def resultado_total_ars(self) -> float:
        return self.patrimonio_ars - self.aportado_ars

    @property
    def resultado_total_usd(self) -> float:
        return self.patrimonio_usd - self.aportado_usd

    @property
    def rendimiento_total_pct(self) -> float | None:
        if not self.aportado_ars:
            return None
        return self.resultado_total_ars / self.aportado_ars * 100.0

    @property
    def rendimiento_total_usd_pct(self) -> float | None:
        """Rendimiento en dólares: patrimonio de hoy contra el capital
        aportado, cada aporte convertido al MEP del día en que se hizo."""
        if not self.aportado_usd:
            return None
        return self.resultado_total_usd / self.aportado_usd * 100.0


def valuar(
    posiciones: dict,
    resolver,
    instrumentos: dict | None = None,
    solo_con_tenencia: bool = True,
    mep_actual: float | None = None,
) -> list[PosicionValuada]:
    """Valúa cada posición con el precio que devuelva `resolver(ticker, inst)`.

    :param posiciones: ``{ticker: Posicion}`` (de `posiciones.py`).
    :param resolver: callable ``(ticker, instrumento) -> (precio, origen)``.
        Se inyecta para no atar este módulo a la red ni a la DB.
    :param instrumentos: ``{ticker: Instrumento}`` para categoría de activo y
        la regla de bonos ``/100``.
    :param solo_con_tenencia: si es True, las posiciones sin tenencia (vendidas
        o vencidas) igual se devuelven cuando tuvieron resultado — su
        rendimiento ya realizado forma parte del total —, marcadas con
        ``cerrada=True``.
    :param mep_actual: para valuar la tenencia de hoy en dólares.
    """
    instrumentos = instrumentos or {}
    out: list[PosicionValuada] = []
    for ticker, pos in posiciones.items():
        cant = pos.cant_actual
        cerrada = abs(cant) < 1e-9
        # Realizado en ventas, a costo promedio ponderado (regla del Excel).
        vendidas = -pos.cant_vendida
        realizado_ars = pos.ingreso_ars_ventas - (pos.ppc_ars or 0.0) * vendidas
        realizado_usd = pos.ingreso_usd_ventas - (pos.ppc_usd_hist or 0.0) * vendidas
        if cerrada and solo_con_tenencia:
            # Sin tenencia: se muestra solo si dejó rendimiento (ventas/cobros).
            if abs(realizado_ars) < 1e-9 and abs(pos.flujos_ars) < 1e-9:
                continue

        inst = instrumentos.get(ticker)
        precio, origen = (None, "cerrada") if cerrada else resolver(ticker, inst)
        valor = precio * cant if isinstance(precio, (int, float)) else None
        costo_usd_ten = pos.costo_usd_posicion
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
                invertido_ars=pos.costo_ars_compras,
                invertido_usd=pos.costo_usd_hist,
                realizado_ars=realizado_ars,
                realizado_usd=realizado_usd,
                flujos_ars=pos.flujos_ars,
                flujos_usd=pos.flujos_usd,
                valor_usd_actual=(valor / mep_actual) if (valor and mep_actual) else None,
                costo_usd_tenencia=costo_usd_ten,
                cerrada=cerrada,
                costo_amortizado_ars=pos.costo_amortizado_ars,
                costo_amortizado_usd=pos.costo_amortizado_usd,
            )
        )
    out.sort(key=lambda p: (p.valor_ars is None, -(p.valor_ars or 0)))
    return out


def kpis_de(valuadas: list[PosicionValuada], mep: float | None = None) -> KPIs:
    """Totales de cartera.

    Dos planos, deliberadamente separados:

      * **tenencia viva** (`valor_total_ars`, `resultado_ars`): solo lo que
        tiene precio hoy — el costo de lo que no se pudo valuar tampoco suma,
        para no comparar valor parcial contra costo total;
      * **rendimiento total** (`resultado_total_*`): invertido, realizado en
        ventas, flujos cobrados y no realizado, en ARS y en USD al TC de cada
        fecha. Incluye posiciones ya cerradas (vencidas o vendidas).
    """
    k = KPIs()
    for p in valuadas:
        # Plano 1: tenencia viva valuada.
        if p.valor_ars is None:
            if not p.cerrada:
                k.posiciones_sin_precio += 1
        else:
            k.posiciones_valuadas += 1
            k.valor_total_ars += p.valor_ars
            k.costo_total_ars += p.costo_ars
            k.no_realizado_ars += p.no_realizado_ars or 0.0
            k.no_realizado_usd += p.no_realizado_usd or 0.0
        # Plano 2: rendimiento histórico total.
        k.invertido_ars += p.invertido_ars
        k.invertido_usd += p.invertido_usd
        k.realizado_ars += p.realizado_ars
        k.realizado_usd += p.realizado_usd
        k.flujos_ars += p.flujos_ars
        k.flujos_usd += p.flujos_usd
        k.costo_amortizado_ars += p.costo_amortizado_ars
        k.costo_amortizado_usd += p.costo_amortizado_usd
    k.valor_total_usd = (k.valor_total_ars / mep) if mep else None
    return k


def completar_patrimonio(
    k: KPIs, capital, cash_ars: float, cash_usd: float, mep: float | None,
    flujos=None, fecha_valuacion=None,
) -> KPIs:
    """Agrega a los KPIs el rendimiento por método de patrimonio.

    :param capital: :class:`CapitalAportado` (depósitos y retiros ya en ARS/USD
        al TC de cada fecha).
    :param cash_ars/cash_usd: efectivo en la cuenta, por moneda.
    :param flujos: ``[(fecha, ars, usd), ...]`` de aportes/retiros (signo del
        inversor). Con esto se calcula la **TIR**: el rendimiento acumulado
        solo no dice nada sin el tiempo, y anualizarlo dividiendo por los años
        sería incorrecto porque cada aporte estuvo invertido un plazo distinto.
    :param fecha_valuacion: fecha del patrimonio final.
    """
    from places.inversiones.cartera.posiciones import tir  # evita ciclo

    k.aportado_ars = capital.neto_ars
    k.aportado_usd = capital.neto_usd
    k.patrimonio_ars = k.valor_total_ars + cash_ars + (cash_usd * mep if mep else 0.0)
    k.patrimonio_usd = (
        (k.valor_total_usd or 0.0) + cash_usd + (cash_ars / mep if mep else 0.0)
    )

    if flujos and fecha_valuacion is not None:
        fechas = [f for f, _, _ in flujos]
        if fechas:
            k.dias = (fecha_valuacion - min(fechas)).days
            k.tir_ars = tir([(f, a) for f, a, _ in flujos]
                            + [(fecha_valuacion, k.patrimonio_ars)])
            k.tir_usd = tir([(f, u) for f, _, u in flujos]
                            + [(fecha_valuacion, k.patrimonio_usd)])
    return k


# ---------------------------------------------------------------------------
# Instrumentos sin mercado: valuación por devengamiento
# ---------------------------------------------------------------------------

def precio_devengado(
    costo_usd: float, cantidad: float, fecha_compra, fecha_valuacion,
    tasa_anual: float, mep: float,
) -> float | None:
    """Precio (en ARS por unidad) de un instrumento que devenga una tasa.

    Los pagarés y cheques de pago diferido **no cotizan**: rinden la tasa
    pactada al descontarlos. El "precio actual" que informa el broker no
    refleja ese devengamiento (en el caso real daba ~200% anualizado), así que
    se valúan capitalizando el costo a su tasa:

        valor_usd = costo_usd × (1 + tasa)^(días/365)

    y se pasa a pesos por el MEP para que conviva con el resto de la cartera.
    Devuelve ``None`` si falta algún dato.
    """
    if not (costo_usd and cantidad and tasa_anual and mep):
        return None
    try:
        dias = (fecha_valuacion - fecha_compra).days
    except TypeError:
        return None
    if dias < 0:
        return None
    valor_usd = costo_usd * ((1.0 + tasa_anual) ** (dias / 365.0))
    return valor_usd * mep / cantidad
