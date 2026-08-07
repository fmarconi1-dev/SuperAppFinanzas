"""Ajustes de tenencia: lo que el broker no informa.

**Por qué existe este módulo.** El export de movimientos de inviu no alcanza
para reconstruir la cartera (trampa #4 del proyecto). Hay tres agujeros que se
repiten y que no se pueden tapar leyendo mejor el archivo, porque el dato
sencillamente no está:

* **Splits y dividendos en acciones.** BYMA pasó de 9 a 18 unidades en 2025 sin
  generar ningún movimiento. El ledger veía una venta de 18 con 9 registradas y
  cerraba 9 sin costo.
* **Ajustes de ratio de CEDEAR.** Mismo caso.
* **Papeles anteriores al registro.** Las 300 TXAR vendidas el 10/7/2025 nunca
  tuvieron compra: ya estaban ahí cuando arrancó el Excel.
* **Cupones y canjes recibidos por tenencia.** Los 100 GGALX vinieron gratis por
  tener GGAL. Se vendieron por $1.494 y eso es ganancia íntegra, pero el ledger
  no tenía de dónde sacar las unidades.

Un solo primitivo cubre los cuatro: **un delta de cantidad y un delta de costo,
con fecha y ticker.** Un split es (+9, $0); un saldo inicial es (+300, su
costo); un cupón gratis es (+100, $0).

---

## La identidad contable

Este es el punto que hace al módulo peligroso si se implementa a la ligera.

El rendimiento total se mide por el **método del patrimonio** (trampa #1):

    resultado = (tenencia + efectivo) − (depósitos − retiros)

Un ajuste que agrega **costo** describe plata que entró a la cartera antes de
que arrancara el registro. Si se carga el costo sin registrar ese aporte, la
venta de esas unidades entra al efectivo como **ganancia pura**: las 300 TXAR
sumarían $186.751 de resultado inventado.

Por eso :func:`aporte_sintetico` existe y `posiciones.capital_aportado()` la
consume. La regla es una sola y no la decide el usuario:

    **el depósito sintético es igual al costo del ajuste**

Costo 0 → aporte 0, que es exactamente lo correcto para un split: no entró ni
salió plata, las mismas unidades valen lo mismo repartidas en más papeles. Es
el mismo mecanismo que la fila "Saldo inicial sintetico" del Excel, pero
explícito y verificado por tests en vez de a mano.

---

## `estimado`

Un costo despejado de un rendimiento recordado ("la vendí como a −20%") no es
un costo verificado contra el resumen del broker. Los dos son números y se ven
igual en una tabla; la única forma de poder distinguirlos dentro de seis meses
es guardar cuál era cuál. La app los muestra marcados.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

__all__ = [
    "TIPOS", "Ajuste", "listar", "agregar", "eliminar", "tickers_conocidos",
    "parecidos", "eventos_desde_ajustes", "aporte_sintetico",
    "costo_desde_rendimiento",
]


#: Los cuatro casos que aparecieron en datos reales, con su etiqueta y si el
#: costo se espera distinto de cero. La app usa esto para guiar la carga.
TIPOS: dict[str, dict] = {
    "SPLIT": {
        "etiqueta": "Split o dividendo en acciones",
        "ayuda": "Te dieron más unidades sin poner plata. El costo total no "
                 "cambia: se reparte en más papeles y el precio promedio baja.",
        "espera_costo": False,
    },
    "SALDO_INICIAL": {
        "etiqueta": "Ya lo tenías antes del registro",
        "ayuda": "Unidades compradas antes de que arrancara el historial. "
                 "Necesitan su costo real: sin él, venderlas figura como "
                 "ganancia pura.",
        "espera_costo": True,
    },
    "CANJE": {
        "etiqueta": "Canje o cupón recibido",
        "ayuda": "Unidades que llegaron por tener otro papel (cupones de "
                 "suscripción, escisiones). Si no pagaste nada, el costo es 0.",
        "espera_costo": False,
    },
    "RATIO": {
        "etiqueta": "Ajuste de ratio de CEDEAR",
        "ayuda": "El emisor cambió cuántos CEDEAR equivalen a una acción. "
                 "Cambia la cantidad, no lo que invertiste.",
        "espera_costo": False,
    },
    "NOMINALES": {
        "etiqueta": "El movimiento vino sin la cantidad",
        "ayuda": "El export trae el monto pero no los nominales — pasa con los "
                 "pagarés y cheques. El costo ya entró con la compra: acá va "
                 "solo la cantidad, que sale de la tenencia del broker.",
        "espera_costo": False,
    },
}


@dataclass(frozen=True)
class Ajuste:
    """Un delta de tenencia con su motivo."""

    fecha: date
    ticker: str
    tipo: str
    cantidad: float = 0.0
    costo_ars: float = 0.0
    costo_usd: float | None = None
    estimado: bool = False
    nota: str = ""
    id: int | None = None

    @property
    def etiqueta_tipo(self) -> str:
        return TIPOS.get(self.tipo, {}).get("etiqueta", self.tipo)

    @property
    def mueve_capital(self) -> bool:
        """True si el ajuste describe plata que entró a la cartera.

        Es la condición para que genere depósito sintético.
        """
        return abs(self.costo_ars) > 1e-9


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def _a_fecha(valor) -> date | None:
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def listar(conn, user_id: int, ticker: str | None = None) -> list[Ajuste]:
    """Los ajustes del usuario, del más viejo al más nuevo."""
    sql = ("SELECT id, fecha, ticker, tipo, cantidad, costo_ars, costo_usd, "
           "       estimado, nota "
           "FROM cartera_ajustes WHERE user_id = ?")
    params: list = [user_id]
    if ticker:
        sql += " AND ticker = ?"
        params.append(ticker)
    sql += " ORDER BY fecha, id"

    out: list[Ajuste] = []
    for r in conn.execute(sql, params):
        f = _a_fecha(r["fecha"])
        if f is None:          # fila corrupta: se ignora, no se adivina
            continue
        out.append(Ajuste(
            id=r["id"], fecha=f, ticker=r["ticker"], tipo=r["tipo"],
            cantidad=r["cantidad"] or 0.0, costo_ars=r["costo_ars"] or 0.0,
            costo_usd=r["costo_usd"], estimado=bool(r["estimado"]),
            nota=r["nota"] or "",
        ))
    return out


def agregar(conn, user_id: int, ajuste: Ajuste) -> int | None:
    """Guarda un ajuste. Devuelve su id, o ``None`` si ya existía.

    El `UNIQUE` de la tabla hace de dedupe: cargar dos veces el mismo split
    no duplica las unidades. Es la misma disciplina que el `hash_dedupe` de
    los movimientos, con la clave puesta sobre lo que define al ajuste.
    """
    if ajuste.tipo not in TIPOS:
        raise ValueError(f"tipo de ajuste desconocido: {ajuste.tipo!r}")
    if abs(ajuste.cantidad) < 1e-12 and abs(ajuste.costo_ars) < 1e-9:
        raise ValueError("un ajuste que no mueve ni unidades ni costo no hace nada")

    cur = conn.execute(
        "INSERT OR IGNORE INTO cartera_ajustes "
        "(user_id, fecha, ticker, tipo, cantidad, costo_ars, costo_usd, "
        " estimado, nota) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, ajuste.fecha.isoformat(), ajuste.ticker.strip().upper(),
         ajuste.tipo, ajuste.cantidad, ajuste.costo_ars, ajuste.costo_usd,
         int(ajuste.estimado), ajuste.nota or None),
    )
    return cur.lastrowid if cur.rowcount else None


def tickers_conocidos(conn, user_id: int) -> set[str]:
    """Los tickers que aparecen en los movimientos del usuario.

    Sirve para avisar cuando un ajuste apunta a un papel que no existe. Pasó
    de verdad el 4/8/2026: se cargó el ajuste de los cupones con el ticker
    ``CUPONES GGALX`` en vez de ``GGALX``. Se guardó sin chistar, no corrigió
    nada y el aviso siguió apareciendo — **un ajuste mal tipeado no falla, no
    hace nada**, que es peor porque no deja rastro.
    """
    try:
        return {
            r[0] for r in conn.execute(
                "SELECT DISTINCT ticker_base FROM cartera_movimientos "
                "WHERE user_id = ? AND ticker_base IS NOT NULL", (user_id,))
        }
    except Exception:
        return set()


def parecidos(ticker: str, conocidos, n: int = 3) -> list[str]:
    """Tickers conocidos que se parecen al escrito, para sugerir.

    Además del parecido difuso, se prioriza que el ticker escrito **contenga**
    uno conocido: así `CUPONES GGALX` sugiere `GGALX` primero.
    """
    t = (ticker or "").strip().upper()
    if not t:
        return []
    contenidos = sorted(
        (c for c in conocidos if c and c in t and c != t),
        key=len, reverse=True,
    )
    import difflib
    difusos = difflib.get_close_matches(t, list(conocidos), n=n, cutoff=0.6)
    salida: list[str] = []
    for c in contenidos + difusos:
        if c not in salida and c != t:
            salida.append(c)
    return salida[:n]


def eliminar(conn, user_id: int, ajuste_id: int) -> bool:
    """Borra un ajuste. Devuelve si borró algo."""
    cur = conn.execute(
        "DELETE FROM cartera_ajustes WHERE id = ? AND user_id = ?",
        (ajuste_id, user_id),
    )
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Adaptadores hacia el resto del sistema
# ---------------------------------------------------------------------------

def eventos_desde_ajustes(ajustes) -> list:
    """Convierte ajustes en eventos del ledger.

    El `monto` va **negativo** porque el ledger lee el signo del export, donde
    lo que se compra sale de la caja. Así `Evento.importes` devuelve el costo
    con el mismo signo que una compra y `_ajustar()` lo trata igual.

    El USD se pasa ya resuelto en `tc_mep` cuando el usuario cargó los dos
    importes; si solo cargó pesos, queda en `None` y el ledger no inventa una
    conversión (ADR-0004: el MEP tiene fuente, no se estima).
    """
    from .ledger import Evento

    out = []
    for a in ajustes:
        tc = None
        if a.costo_usd not in (None, 0) and abs(a.costo_ars) > 1e-9:
            tc = a.costo_ars / a.costo_usd
        out.append(Evento(
            fecha=a.fecha, categoria="AJUSTE", ticker=a.ticker,
            cantidad=a.cantidad, monto=-a.costo_ars, moneda="ARS", tc_mep=tc,
        ))
    return out


def aporte_sintetico(ajustes) -> tuple[float, float]:
    """``(ars, usd)`` de capital que los ajustes declaran haber aportado.

    **Esto es lo que evita que el método del patrimonio mienta.** Ver la nota
    de identidad contable arriba: sin este aporte, vender un papel que ya
    tenías antes del registro figura como ganancia del 100%.

    Un ajuste sin costo (split, cupón gratis) aporta 0 y por eso no aparece
    acá: no hubo plata entrando.
    """
    ars = usd = 0.0
    for a in ajustes:
        ars += a.costo_ars
        if a.costo_usd is not None:
            usd += a.costo_usd
    return ars, usd


def costo_desde_rendimiento(ingreso: float, rendimiento_pct: float) -> float:
    """Despeja el costo a partir de lo cobrado y el rendimiento recordado.

    Cuando no se tiene el precio de compra pero sí se recuerda cómo salió la
    operación ("la vendí como a −20%"), el costo se despeja:

        resultado / costo = r        y        resultado = ingreso − costo
        ⇒ costo = ingreso / (1 + r)

    El número que sale de acá **siempre** se guarda con ``estimado=True``.
    """
    factor = 1.0 + rendimiento_pct / 100.0
    if abs(factor) < 1e-9:
        raise ValueError("un rendimiento de −100% no permite despejar el costo")
    return ingreso / factor
