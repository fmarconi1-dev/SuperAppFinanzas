"""Parser del export de **Tenencias** del broker (foto de la cartera).

Por qué existe: el export de *movimientos* NO alcanza para reconstruir la
cartera. Casos reales comprobados:

  * **Ajuste de ratio de CEDEAR** (SPY): el broker cambia la relación y ajusta
    el saldo **sin postear un movimiento**.
  * **Pagarés / cheques** (``#UMV060770008``): el movimiento ("Compra cheque")
    trae el monto pagado pero **no la cantidad**, así que la posición no se
    puede derivar. En la cartera de Franco esto era el 35% del total.

Por eso la app usa dos fuentes complementarias, como cualquier sistema serio
de cartera: los **movimientos** dan el histórico (costos, aportes, rendimiento)
y la **tenencia** da la foto actual (cantidades y precios de referencia). La
diferencia entre ambas es justamente la reconciliación contra el custodio.

Formato del archivo (inviu): un bloque por tipo de activo, cada uno con su
fila de encabezados; las dos primeras filas de "Moneda" son el efectivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from core.db import backup_db

__all__ = [
    "Tenencia",
    "FotoCartera",
    "parse_tenencias",
    "parse_filas_tenencias",
    "guardar_foto",
    "ultima_foto",
    "comparar_con_movimientos",
    "set_tenencia_manual",
    "tenencias_manuales",
    "FECHA_MANUAL",
]

_PREFIJO_TIPO = "Tipo de Activo:"


@dataclass
class Tenencia:
    ticker: str
    nombre: str
    cantidad: float
    precio: float | None
    moneda: str = "ARS"
    tipo_activo: str = ""
    costo_ppc: float | None = None

    @property
    def valor(self) -> float | None:
        if self.precio is None:
            return None
        return self.cantidad * self.precio


@dataclass
class FotoCartera:
    """Tenencia completa a una fecha, ya separada en posiciones y efectivo."""
    fecha_valuacion: date | None = None
    mep: float | None = None
    ccl: float | None = None
    posiciones: list[Tenencia] = field(default_factory=list)
    efectivo_ars: float = 0.0
    efectivo_usd: float = 0.0

    @property
    def valor_posiciones_ars(self) -> float:
        return sum(t.valor or 0.0 for t in self.posiciones)

    def total_ars(self) -> float:
        usd_en_ars = self.efectivo_usd * self.mep if self.mep else 0.0
        return self.valor_posiciones_ars + self.efectivo_ars + usd_en_ars

    def total_usd(self) -> float | None:
        if not self.mep:
            return None
        return self.total_ars() / self.mep

    @property
    def cantidades(self) -> dict[str, float]:
        return {t.ticker: t.cantidad for t in self.posiciones}


def _num(v) -> float | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str):
        t = v.strip().replace("$", "").replace(" ", "")
        if not t:
            return None
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        try:
            return float(t)
        except ValueError:
            return None
    return None


def _fecha(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S"):
            try:
                return datetime.strptime(v.strip()[:10], fmt[:8] if len(fmt) > 8 else fmt).date()
            except ValueError:
                continue
    return None


def parse_tenencias(ruta, hoja: str | None = None) -> FotoCartera:
    """Lee el export de Tenencias y devuelve la :class:`FotoCartera`."""
    import openpyxl

    wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    try:
        ws = wb[hoja] if hoja else wb.worksheets[0]
        filas = [list(f) for f in ws.iter_rows(values_only=True)]
    finally:
        wb.close()
    return parse_filas_tenencias(filas)


def parse_filas_tenencias(filas) -> FotoCartera:
    """Igual que :func:`parse_tenencias` pero sobre filas ya leídas."""
    foto = FotoCartera()
    tipo_actual = ""
    for celdas in filas:
        if not celdas:
            continue
        c0 = str(celdas[0]).strip() if celdas[0] is not None else ""

        # Cabecera del archivo: fecha de valuación y tipos de cambio.
        if c0.startswith("Fecha de valuación"):
            foto.fecha_valuacion = _fecha(celdas[1] if len(celdas) > 1 else None)
            continue
        if c0.startswith("TC USD MEP"):
            foto.mep = _num(celdas[1] if len(celdas) > 1 else None)
            continue
        if c0.startswith("TC USD CCL"):
            foto.ccl = _num(celdas[1] if len(celdas) > 1 else None)
            continue

        if c0.startswith(_PREFIJO_TIPO):
            tipo_actual = c0[len(_PREFIJO_TIPO):].strip()
            continue
        if c0 == "Ticker":          # fila de encabezados de cada bloque
            continue

        cantidad = _num(celdas[4] if len(celdas) > 4 else None)   # "Disponibles"
        precio = _num(celdas[6] if len(celdas) > 6 else None)
        if not c0 or cantidad is None:
            continue

        # Las dos filas de "Moneda" son el efectivo de la cuenta.
        if tipo_actual.lower() == "moneda" or c0 in ("ARS", "USD"):
            if c0 == "ARS":
                foto.efectivo_ars += cantidad
            elif c0 == "USD":
                foto.efectivo_usd += cantidad
            continue

        foto.posiciones.append(
            Tenencia(
                ticker=c0,
                nombre=str(celdas[1] or "").strip() if len(celdas) > 1 else "",
                cantidad=cantidad,
                precio=precio,
                moneda=str(celdas[5] or "ARS").strip() if len(celdas) > 5 else "ARS",
                tipo_activo=tipo_actual,
                costo_ppc=_num(celdas[9] if len(celdas) > 9 else None),
            )
        )
    return foto


# ---------------------------------------------------------------------------
# Persistencia y reconciliación
# ---------------------------------------------------------------------------

def guardar_foto(conn, foto: FotoCartera, user_id: int) -> int:
    """Guarda la foto en `cartera_tenencia` (+ meta). Idempotente por fecha.

    Devuelve la cantidad de posiciones guardadas. Commitea al final.

    Saca una copia previa: la foto del broker **manda sobre las cantidades**
    derivadas de movimientos, así que importar la equivocada altera todas las
    valuaciones.
    """
    backup_db()
    if foto.fecha_valuacion is None:
        raise ValueError("La tenencia no trae fecha de valuación")
    fecha = foto.fecha_valuacion.isoformat()
    conn.execute("BEGIN")
    try:
        conn.execute(
            "DELETE FROM cartera_tenencia WHERE user_id = ? AND fecha_valuacion = ?",
            (user_id, fecha),
        )
        for t in foto.posiciones:
            conn.execute(
                "INSERT INTO cartera_tenencia (user_id, fecha_valuacion, ticker, "
                " nombre, cantidad, precio, moneda, tipo_activo, costo_ppc) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (user_id, fecha, t.ticker, t.nombre, t.cantidad, t.precio,
                 t.moneda, t.tipo_activo, t.costo_ppc),
            )
        conn.execute(
            "INSERT INTO cartera_tenencia_meta (user_id, fecha_valuacion, mep, "
            " ccl, efectivo_ars, efectivo_usd) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(user_id, fecha_valuacion) DO UPDATE SET "
            "  mep=excluded.mep, ccl=excluded.ccl, "
            "  efectivo_ars=excluded.efectivo_ars, "
            "  efectivo_usd=excluded.efectivo_usd, "
            "  importado_en=datetime('now')",
            (user_id, fecha, foto.mep, foto.ccl, foto.efectivo_ars,
             foto.efectivo_usd),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return len(foto.posiciones)


def ultima_foto(conn, user_id: int) -> FotoCartera | None:
    """Recupera la foto más reciente guardada, o None si no hay ninguna."""
    meta = conn.execute(
        "SELECT * FROM cartera_tenencia_meta WHERE user_id = ? "
        "ORDER BY fecha_valuacion DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if meta is None:
        return None
    foto = FotoCartera(
        fecha_valuacion=_fecha(meta["fecha_valuacion"]),
        mep=meta["mep"],
        ccl=meta["ccl"],
        efectivo_ars=meta["efectivo_ars"] or 0.0,
        efectivo_usd=meta["efectivo_usd"] or 0.0,
    )
    for r in conn.execute(
        "SELECT * FROM cartera_tenencia WHERE user_id = ? AND fecha_valuacion = ?",
        (user_id, meta["fecha_valuacion"]),
    ):
        foto.posiciones.append(
            Tenencia(
                ticker=r["ticker"], nombre=r["nombre"] or "",
                cantidad=r["cantidad"], precio=r["precio"],
                moneda=r["moneda"] or "ARS", tipo_activo=r["tipo_activo"] or "",
                costo_ppc=r["costo_ppc"],
            )
        )
    return foto


def comparar_con_movimientos(foto: FotoCartera, posiciones: dict) -> list[dict]:
    """Reconciliación contra el custodio: broker vs lo derivado de movimientos.

    Devuelve una fila por ticker con diferencia, ordenada por magnitud. Es el
    control que detecta ajustes de ratio, pagarés y movimientos faltantes.
    """
    difs = []
    del_broker = foto.cantidades
    tickers = set(del_broker) | {
        t for t, p in posiciones.items() if abs(p.cant_actual) > 1e-9
    }
    for tk in tickers:
        broker = del_broker.get(tk, 0.0)
        propia = posiciones[tk].cant_actual if tk in posiciones else 0.0
        if abs(broker - propia) > 1e-6:
            difs.append({
                "ticker": tk,
                "broker": broker,
                "movimientos": propia,
                "diferencia": broker - propia,
            })
    difs.sort(key=lambda d: -abs(d["diferencia"]))
    return difs


#: Fecha reservada para las tenencias cargadas a mano (activos fuera del
#: broker). Se usa una fecha propia para no mezclarlas con las fotos del
#: custodio ni perderlas al reimportar una tenencia.
FECHA_MANUAL = "manual"


def set_tenencia_manual(
    conn, user_id: int, ticker: str, cantidad: float,
    nombre: str = "", tipo_activo: str = "Externo",
) -> None:
    """Registra la cantidad de un activo que el broker no informa.

    Caso real: el **Bitcoin** de Franco vive en Binance, así que no aparece en
    la tenencia de inviu. Su cantidad real (0,00316847) no se puede derivar de
    los movimientos — el Excel solo tenía el saldo inicial (0,003), que
    subvaluaba la posición.
    """
    conn.execute(
        "INSERT INTO cartera_tenencia (user_id, fecha_valuacion, ticker, "
        " nombre, cantidad, precio, moneda, tipo_activo, costo_ppc) "
        "VALUES (?, ?, ?, ?, ?, NULL, 'ARS', ?, NULL) "
        "ON CONFLICT(user_id, fecha_valuacion, ticker) DO UPDATE SET "
        "  cantidad = excluded.cantidad, nombre = excluded.nombre, "
        "  tipo_activo = excluded.tipo_activo",
        (user_id, FECHA_MANUAL, ticker, nombre or ticker, float(cantidad),
         tipo_activo),
    )


def tenencias_manuales(conn, user_id: int) -> dict[str, float]:
    """Cantidades cargadas a mano (activos fuera del broker)."""
    return {
        r["ticker"]: r["cantidad"]
        for r in conn.execute(
            "SELECT ticker, cantidad FROM cartera_tenencia "
            "WHERE user_id = ? AND fecha_valuacion = ?",
            (user_id, FECHA_MANUAL),
        )
    }
