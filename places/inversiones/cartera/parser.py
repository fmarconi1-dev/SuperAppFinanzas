"""Parser del export de movimientos del broker — Fase 3a (Cartera nativa).

Maneja los DOS formatos del export (spec en `ESTADO.md`, diseño en ADR-0003):

- **Formato viejo** (8 columnas): Operación | Concertación | Liquidación |
  Descripción | Monto | Cantidad | Precio | Moneda.
- **Formato nuevo** (desde ~mayo 2026, 7 columnas, SIN "Operación"): arranca
  en Concertación; el tipo de operación se infiere de monto/cantidad/desc.

La detección de formato es **por fila** (el crudo del Excel mezcla ambos).

Reglas portadas del Excel `Inversiones.xlsx` (LEEME + fórmulas de
`Movimientos Procesado` + `Config`):

- Mapeo Operación→Categoría idéntico a `Config!A5:B16` (12 categorías).
- Ticker crudo: pseudo-tickers para DEPOSITO/RETIRO/CC/REMUNERACION/OTROS;
  si no, se extrae de ``"TICKER | Descripción"`` (fórmula D de Procesado).
- Ticker base: mapping ARS↔USD tipo hoja Config (col E de Procesado).
- Espejo de dividendos (col M de Procesado): línea ARS de un instrumento
  cuyo ticker crudo es el BASE, con otra línea USD del mismo ticker base,
  misma fecha y misma categoría → se marca ``es_espejo`` (se ignora en los
  cálculos; regla del LEEME: "dividendos: solo la línea USD").
- Bonos/letras/ONs que cotizan "por 100": ``precio_normalizado`` = precio/100
  (regla del LEEME; el precio crudo se conserva en ``precio``).
- Saldos iniciales sintéticos ("(Saldo inicial" en la descripción): se
  conservan SIEMPRE (regla del LEEME: "NO eliminar").
- **Moneda: NO se confía en la columna del export** (hallazgo documentado en
  ESTADO.md: etiquetas del broker inconsistentes, p. ej. compras ARS marcadas
  USD). Se infiere de ticker (sufijo D / mapping Config), categoría y
  magnitudes; si difiere de la declarada se deja una advertencia en la fila.

Dedupe: hash sha256 de (fecha + categoría + descripción + monto + cantidad)
más un contador de ocurrencia para repetidos idénticos DENTRO del mismo
archivo (dos operaciones iguales el mismo día son legítimas; el dedupe
contra la DB descarta re-importaciones, no operaciones reales).

Este módulo es puro (sin DB, sin red): recibe filas, devuelve
:class:`Movimiento`. La carga a DB llega con la migración M9.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

__all__ = [
    "CATEGORIAS",
    "MAPA_OPERACION",
    "Instrumento",
    "Movimiento",
    "clave_dedupe",
    "hash_dedupe",
    "parse_filas",
    "parse_archivo_excel",
    "parse_archivo_csv",
]

# ---------------------------------------------------------------------------
# Constantes portadas del Excel
# ---------------------------------------------------------------------------

#: Las 12 categorías (idénticas a `Config!B5:B16` del Excel).
CATEGORIAS = (
    "COMPRA", "VENTA", "DIVIDENDO", "RETENCION", "RENTA", "AMORTIZACION",
    "CAUCION_COL", "CAUCION_VTO", "REMUNERACION", "DEPOSITO", "RETIRO",
    "OTROS",
)

#: Mapeo Operación Original → Categoría (portado de `Config!A5:B16`).
#: Claves normalizadas (minúsculas, sin tildes).
MAPA_OPERACION = {
    "compra": "COMPRA",
    "venta": "VENTA",
    "ingreso dividendo": "DIVIDENDO",
    "renta": "RENTA",
    "amortizacion": "AMORTIZACION",
    "retencion impositiva": "RETENCION",
    "vencimiento": "CAUCION_VTO",
    "caucion colocadora": "CAUCION_COL",
    "deposito": "DEPOSITO",
    "retiro": "RETIRO",
    "remuneracion": "REMUNERACION",
    "otros": "OTROS",
    # Pagarés / cheques de pago diferido: son una compra de instrumento. El
    # broker NO manda la cantidad en el movimiento (solo el monto pagado), así
    # que la tenencia aporta las unidades y de ahí sale el precio promedio.
    "compra cheque": "COMPRA",
    "venta cheque": "VENTA",
}

#: Categorías que usan pseudo-ticker en vez de extraerlo de la descripción
#: (fórmula D de Movimientos Procesado).
_PSEUDO_TICKERS = {
    "DEPOSITO": "DEPOSITO",
    "RETIRO": "RETIRO",
    "CAUCION_COL": "CC",
    "CAUCION_VTO": "CC",
    "REMUNERACION": "REMUNERACION",
    "OTROS": "OTROS",
}

#: Categorías que nunca son un instrumento (fórmula L de Procesado).
_CATEGORIAS_NO_INSTRUMENTO = {
    "CAUCION_COL", "CAUCION_VTO", "DEPOSITO", "RETIRO", "REMUNERACION",
    "OTROS",
}

#: Umbral heurístico de magnitudes: un monto en USD de una cuenta minorista
#: no supera esto; uno en ARS casi siempre lo supera (usado solo como
#: desempate cuando no hay información de ticker).
_UMBRAL_MONTO_USD = 20_000.0

# Epoch de los seriales de fecha de Excel (sistema 1900, con el bug del
# año bisiesto 1900 ya descontado: serial 1 = 1900-01-01).
_EXCEL_EPOCH = date(1899, 12, 30)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Instrumento:
    """Fila del mapping de instrumentos (equivalente a `Config!G:N`)."""

    ticker: str                  # ticker base (ARS), p. ej. "TSM"
    ticker_usd: str | None = None  # variante USD (sufijo D), p. ej. "TSMD"
    categoria_activo: str = ""   # Acciones / Bonos / Cedears / Letras / ONs / Cripto
    moneda_cotiz: str = "ARS"    # "ARS", "USD", "ARS/100", "USD/100"
    #: ``Config!I``. Se guardaba en `cartera_instrumentos` pero no viajaba en
    #: este objeto, así que el resto del código no la veía. **Tiene dato útil
    #: además del nombre:** la fecha de vencimiento de bonos, letras y ON está
    #: escrita ahí ("Bono Tesoro Nacional Vto. 30/11/2029") y es de donde la
    #: lee `vencimientos.py`.
    descripcion: str = ""
    #: ``Config!L`` ("Activo en cartera"). False = instrumento vencido o
    #: retirado: su tenencia ya no existe (amortizó / se canjeó), aunque los
    #: movimientos históricos sigan en la DB.
    activo: bool = True

    @property
    def divide_por_100(self) -> bool:
        """Bonos/letras que cotizan cada 100 nominales (regla del LEEME)."""
        return self.moneda_cotiz.endswith("/100")

    @property
    def moneda_base(self) -> str:
        return "USD" if self.moneda_cotiz.startswith("USD") else "ARS"


@dataclass
class Movimiento:
    """Un movimiento parseado y clasificado (fila de la futura `mov_cartera`)."""

    fecha_concertacion: date
    fecha_liquidacion: date | None
    categoria: str
    descripcion: str
    monto: float
    cantidad: float
    precio: float
    moneda: str                       # inferida ("ARS" / "USD")
    ticker_crudo: str
    ticker_base: str
    operacion_original: str | None    # None en formato nuevo (se infirió)
    formato: str                      # "viejo" | "nuevo"
    es_instrumento: bool = False
    es_espejo: bool = False           # línea ARS espejo de dividendo → ignorar
    es_saldo_inicial: bool = False
    precio_normalizado: float | None = None  # bonos: precio / 100
    moneda_declarada: str | None = None      # lo que decía el archivo
    advertencias: list[str] = field(default_factory=list)
    hash_dedupe: str = ""

    def _clave_dedupe(self) -> str:
        return clave_dedupe(self.fecha_concertacion, self.categoria,
                            self.descripcion, self.monto, self.cantidad)


# ---------------------------------------------------------------------------
# Utilidades de normalización
# ---------------------------------------------------------------------------

def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _norm(texto: str) -> str:
    return _sin_tildes(str(texto)).strip().lower()


def _parse_fecha(valor) -> date | None:
    """Fecha desde datetime/date, string (ISO o DD/MM/YYYY) o serial Excel."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        # Serial de Excel (rango razonable: 1990-2100)
        if 32874 <= valor <= 73415:  # serial Excel (rango ~1990-2100)
            return _EXCEL_EPOCH + timedelta(days=int(valor))
        return None
    texto = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto[:10], fmt).date()
        except ValueError:
            continue
    return None


def _parse_numero(valor, advertencias: list[str] | None = None,
                  campo: str = "número") -> float:
    """Número desde float/int o string con formato argentino ('1.234,56').

    Si trae los dos separadores y el **último es el punto** (``1,234.56``), es
    formato de EE.UU.: las comas son miles. Hasta el 22/9/2026 se leía como
    ``1,23456`` — mil veces menos, sin error (trampa 6).

    Un texto ilegible da 0.0 **y se anota en `advertencias`**: un cero
    silencioso no se distingue de un cero real.
    """
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    texto = str(valor).strip().replace("$", "").replace(" ", "")
    if not texto:
        return 0.0
    if "," in texto and "." in texto and texto.rfind(".") > texto.rfind(","):
        texto = texto.replace(",", "")                      # 1,234.56
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")    # 1.234,56
    try:
        return float(texto)
    except ValueError:
        if advertencias is not None:
            advertencias.append(f"{campo} ilegible: {str(valor).strip()!r} → 0")
        return 0.0


def _extraer_ticker(descripcion: str) -> str:
    """``"TSMD | Taiwan Semi..." → "TSMD"`` (fórmula D de Procesado).

    Los pagarés/cheques usan otro formato, sin el separador habitual::

        "Boleto / 2529140 / CCHDIF / 1 / #UMV060770008 / U$S" → "#UMV060770008"

    Su identificador es el token que arranca con ``#``.
    """
    texto = str(descripcion)
    if "#" in texto:
        for token in texto.replace("|", "/").split("/"):
            t = token.strip()
            if t.startswith("#"):
                return t
    return texto.split("|")[0].strip()


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

def parse_filas(
    filas,
    instrumentos: dict[str, Instrumento] | None = None,
) -> list[Movimiento]:
    """Parsea filas crudas del export del broker (ambos formatos, mezclables).

    :param filas: iterable de secuencias (celdas). Se ignoran filas de
        encabezado y filas vacías.
    :param instrumentos: mapping ticker→:class:`Instrumento` (base Y variante
        USD indexadas). Opcional: sin él, la inferencia usa solo heurísticas.
    :return: lista de :class:`Movimiento` en el orden del archivo.
    """
    idx = _indexar_instrumentos(instrumentos or {})
    movimientos: list[Movimiento] = []
    for fila in filas:
        celdas = list(fila) if fila is not None else []
        if _es_fila_vacia(celdas) or _es_encabezado(celdas):
            continue
        mov = _parse_fila(celdas, idx)
        if mov is not None:
            movimientos.append(mov)

    _marcar_espejos(movimientos)
    _asignar_hashes(movimientos)
    return movimientos


def _indexar_instrumentos(
    instrumentos: dict[str, Instrumento],
) -> dict[str, Instrumento]:
    """Indexa cada instrumento por su ticker base Y por su variante USD."""
    idx: dict[str, Instrumento] = {}
    for inst in instrumentos.values():
        idx[inst.ticker] = inst
        if inst.ticker_usd:
            idx[inst.ticker_usd] = inst
    return idx


def _es_fila_vacia(celdas: list) -> bool:
    return all(c is None or str(c).strip() == "" for c in celdas)


def _es_encabezado(celdas: list) -> bool:
    primera = _norm(celdas[0]) if celdas and celdas[0] is not None else ""
    return primera in ("operacion", "concertacion")


def _parse_fila(celdas: list, idx: dict[str, Instrumento]) -> Movimiento | None:
    """Detecta el formato de la fila y la parsea. None si no es parseable."""
    primera = celdas[0] if celdas else None
    operacion = None

    if _parse_fecha(primera) is not None and not isinstance(primera, str):
        formato = "nuevo"
    elif isinstance(primera, str) and _parse_fecha(primera) is not None:
        formato = "nuevo"
    elif isinstance(primera, str) and _norm(primera) in MAPA_OPERACION:
        formato = "viejo"
        operacion = str(primera).strip()
    elif isinstance(primera, str) and primera.strip():
        # Operación desconocida → formato viejo, categoría OTROS
        formato = "viejo"
        operacion = str(primera).strip()
    else:
        return None

    if formato == "viejo":
        campos = celdas[1:8]
    else:
        campos = celdas[0:7]
    # campos: Concertación | Liquidación | Descripción | Monto | Cantidad
    #         | Precio | Moneda
    campos = list(campos) + [None] * (7 - len(campos))
    f_conc = _parse_fecha(campos[0])
    if f_conc is None:
        return None
    f_liq = _parse_fecha(campos[1])
    descripcion = str(campos[2] or "").strip()
    advertencias: list[str] = []
    monto = _parse_numero(campos[3], advertencias, "Monto")
    cantidad = _parse_numero(campos[4], advertencias, "Cantidad")
    precio = _parse_numero(campos[5], advertencias, "Precio")
    moneda_decl = str(campos[6]).strip().upper() if campos[6] else None

    if formato == "viejo":
        categoria = MAPA_OPERACION.get(_norm(operacion), "OTROS")
        if categoria == "OTROS" and _norm(operacion) not in MAPA_OPERACION:
            advertencias.append(f"Operación desconocida: '{operacion}' → OTROS")
        # "Vencimiento" es caución solo si la descripción es de caución;
        # cualquier otro vencimiento se trata como AMORTIZACION.
        if categoria == "CAUCION_VTO" and not _es_desc_caucion(descripcion):
            categoria = "AMORTIZACION"
    else:
        categoria = _inferir_categoria(descripcion, monto, cantidad, idx,
                                       advertencias)

    ticker_crudo = _PSEUDO_TICKERS.get(categoria) or _extraer_ticker(descripcion)
    inst = idx.get(ticker_crudo)
    ticker_base = inst.ticker if inst else ticker_crudo
    es_instrumento = _es_instrumento(categoria, ticker_crudo, idx)
    es_saldo_inicial = "saldo inicial" in _norm(descripcion)

    if es_saldo_inicial:
        # Los saldos iniciales sintéticos están denominados en USD: sus
        # precios lo delatan (AE38D 0,6158 de paridad; BTC 98.094,78; GGAL
        # 4,49 — imposible en pesos) y las compras iniciales suman EXACTO el
        # depósito sintético que las cubre, así que todo el bloque comparte
        # moneda. El export no trae la columna Moneda en esas filas, y
        # tratarlas como ARS subvaluaba el capital inicial ~1.000 veces.
        moneda = "USD"
    else:
        moneda = _inferir_moneda(
            categoria, ticker_crudo, inst, monto, moneda_decl, advertencias,
        )

    precio_norm = None
    if precio and inst is not None and inst.divide_por_100:
        precio_norm = precio / 100.0

    return Movimiento(
        fecha_concertacion=f_conc,
        fecha_liquidacion=f_liq,
        categoria=categoria,
        descripcion=descripcion,
        monto=monto,
        cantidad=cantidad,
        precio=precio,
        moneda=moneda,
        ticker_crudo=ticker_crudo,
        ticker_base=ticker_base,
        operacion_original=operacion,
        formato=formato,
        es_instrumento=es_instrumento,
        es_saldo_inicial=es_saldo_inicial,
        precio_normalizado=precio_norm,
        moneda_declarada=moneda_decl,
        advertencias=advertencias,
    )


def _es_desc_caucion(descripcion: str) -> bool:
    d = _norm(descripcion)
    return d.startswith("cc |") or d.startswith("cc|") or "caucion" in d


def _inferir_categoria(
    descripcion: str,
    monto: float,
    cantidad: float,
    idx: dict[str, Instrumento],
    advertencias: list[str],
) -> str:
    """Inferencia de categoría para el formato nuevo (spec de ESTADO.md)."""
    d = _norm(descripcion)

    if _es_desc_caucion(descripcion):
        return "CAUCION_COL" if monto < 0 else "CAUCION_VTO"
    if "rendimiento diario" in d:
        return "REMUNERACION"
    if "recibo de cobro" in d:
        return "DEPOSITO"
    if "comprobante de pago" in d:
        return "RETIRO"

    if cantidad > 0 and monto < 0:
        return "COMPRA"
    if cantidad < 0 and monto > 0:
        return "VENTA"

    if not cantidad:
        # Sin cantidad: dividendo / retención según signo. Refinamiento:
        # si el ticker es un bono/letra/ON conocido, el cobro es RENTA
        # (los bonos no pagan "dividendos").
        inst = idx.get(_extraer_ticker(descripcion))
        if inst and inst.categoria_activo in ("Bonos", "Letras", "ONs"):
            return "RENTA" if monto > 0 else "RETENCION"
        return "DIVIDENDO" if monto > 0 else "RETENCION"

    advertencias.append(
        f"No se pudo inferir la operación (monto={monto}, cantidad={cantidad})"
        " → OTROS"
    )
    return "OTROS"


def _es_instrumento(
    categoria: str, ticker_crudo: str, idx: dict[str, Instrumento],
) -> bool:
    """Fórmula L de Procesado: instrumento si no es cash y el ticker existe."""
    if categoria in _CATEGORIAS_NO_INSTRUMENTO:
        return False
    # Pagarés / cheques de pago diferido: son instrumentos aunque no estén en
    # el mapping de Config (el Excel nunca los tuvo). Su identificador
    # arranca con "#" — ver `_extraer_ticker`.
    if ticker_crudo.startswith("#"):
        return True
    if idx:
        return ticker_crudo in idx
    # Sin mapping: heurística por categoría.
    return categoria in (
        "COMPRA", "VENTA", "DIVIDENDO", "RENTA", "RETENCION", "AMORTIZACION",
    )


def _inferir_moneda(
    categoria: str,
    ticker_crudo: str,
    inst: Instrumento | None,
    monto: float,
    moneda_decl: str | None,
    advertencias: list[str],
) -> str:
    """Moneda inferida por reglas; la columna del export NO es confiable.

    Hallazgo (ESTADO.md): el broker etiqueta mal la moneda (compras ARS
    marcadas USD, dividendos USD marcados ARS). Precedencia:

    1. Instrumento conocido operado con su ticker USD (sufijo D) → USD;
       con su ticker base → moneda de cotización del instrumento.
    2. BITCOIN → USD.
    3. Cash (cauciones, remuneración, depósitos/retiros) → declarada si
       existe, con desempate por magnitud; sin declarar → ARS.
    4. Resto → declarada, con desempate por magnitud.
    """
    decl = moneda_decl if moneda_decl in ("ARS", "USD", "USD.C") else None
    decl_base = "USD" if decl in ("USD", "USD.C") else ("ARS" if decl else None)

    if inst is not None:
        if inst.ticker_usd and ticker_crudo == inst.ticker_usd:
            moneda = "USD"
        elif ticker_crudo == inst.ticker == inst.ticker_usd:
            moneda = inst.moneda_base  # p. ej. BITCOIN
        else:
            moneda = "ARS" if inst.moneda_base == "ARS" else inst.moneda_base
            # Bonos hard-dollar (USD/100) operados con ticker base: el broker
            # opera el base en ARS; la variante D es la línea USD.
            if inst.divide_por_100 and inst.moneda_cotiz == "USD/100":
                moneda = "ARS"
        if decl_base and decl_base != moneda:
            advertencias.append(
                f"Moneda declarada '{decl}' difiere de la inferida "
                f"'{moneda}' (ticker {ticker_crudo}); se usa la inferida."
            )
        return moneda

    if ticker_crudo == "BITCOIN":
        return "USD"

    # Sin instrumento conocido: partir de la declarada y validar magnitud.
    if decl_base == "USD" and abs(monto) > _UMBRAL_MONTO_USD:
        advertencias.append(
            f"Moneda declarada USD con monto {monto:,.2f} (magnitud de ARS); "
            "se usa ARS."
        )
        return "ARS"
    if decl_base:
        return decl_base
    return "ARS"


def _marcar_espejos(movimientos: list[Movimiento]) -> None:
    """Regla del LEEME / fórmula M: la línea ARS espejo de un dividendo o
    renta de un CEDEAR/bono se ignora — solo cuenta la línea USD.

    Estructura del export (ambos formatos): el ingreso se parte en dos filas
    de la misma fecha y mismo instrumento — la línea de la variante USD
    (ticker con sufijo D, positiva) que se CONSERVA, y la línea del ticker
    BASE en ARS (negativa) que es el ESPEJO a ignorar.

    En el formato viejo ambas patas comparten operación ("Ingreso dividendo"
    / "Renta") → misma categoría. En el nuevo NO hay operación y la categoría
    se infiere por signo, así que la pata base (negativa) cae en RETENCION y
    la USD (positiva) en DIVIDENDO/RENTA. Por eso el apareo NO exige misma
    categoría: se aparea por (fecha, ticker_base) contra una línea USD de
    ingreso (DIVIDENDO/RENTA) del mismo instrumento.

    Nota: un dividendo ARS real de una sola línea (p. ej. GGAL) no tiene
    contraparte USD → NO se marca espejo (se conserva), que es lo correcto.
    """
    ingresos_usd = {
        (m.fecha_concertacion, m.ticker_base)
        for m in movimientos
        if m.moneda == "USD"
        and m.es_instrumento
        and m.categoria in ("DIVIDENDO", "RENTA")
    }
    for m in movimientos:
        if (
            m.moneda == "ARS"
            and m.es_instrumento
            and m.ticker_crudo == m.ticker_base
            and m.categoria in ("DIVIDENDO", "RENTA", "RETENCION")
            and (m.fecha_concertacion, m.ticker_base) in ingresos_usd
        ):
            m.es_espejo = True


def clave_dedupe(fecha, categoria: str, descripcion: str, monto: float,
                 cantidad: float) -> str:
    """La regla de identidad de un movimiento, en **un solo lugar**.

    Vive acá y no en cada llamador porque cualquier corrección posterior de un
    movimiento ya importado tiene que producir **exactamente** el hash que
    generaría re-parsear el archivo corregido. Si no, el dedupe no lo
    reconoce, la reimportación lo inserta de nuevo y quedan los dos — la
    misma trampa que costó los dos bugs del 30/7.
    """
    fecha_txt = fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha)[:10]
    return "|".join([
        fecha_txt,
        categoria,
        (descripcion or "").strip(),
        f"{monto:.2f}",
        f"{cantidad:.6f}",
    ])


def hash_dedupe(fecha, categoria: str, descripcion: str, monto: float,
                cantidad: float, ocurrencia: int = 0) -> str:
    """Hash de dedupe de un movimiento. `ocurrencia` distingue filas idénticas
    dentro del mismo archivo (dos operaciones iguales el mismo día son
    legítimas)."""
    clave = clave_dedupe(fecha, categoria, descripcion, monto, cantidad)
    return hashlib.sha256(f"{clave}|#{ocurrencia}".encode()).hexdigest()


def _asignar_hashes(movimientos: list[Movimiento]) -> None:
    """Hash de dedupe (ESTADO.md: fecha+operación+descripción+monto) con
    contador de ocurrencia para idénticos dentro del mismo archivo."""
    vistos: dict[str, int] = {}
    for m in movimientos:
        clave = m._clave_dedupe()
        n = vistos.get(clave, 0)
        vistos[clave] = n + 1
        m.hash_dedupe = hash_dedupe(
            m.fecha_concertacion, m.categoria, m.descripcion, m.monto,
            m.cantidad, n,
        )


# ---------------------------------------------------------------------------
# Loaders de conveniencia
# ---------------------------------------------------------------------------

def parse_archivo_excel(
    ruta,
    hoja: str | None = None,
    instrumentos: dict[str, Instrumento] | None = None,
) -> list[Movimiento]:
    """Parsea un export .xlsx del broker (primera hoja por defecto)."""
    import openpyxl  # import perezoso: solo si se usa este loader

    wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    try:
        ws = wb[hoja] if hoja else wb.worksheets[0]
        filas = [[c for c in fila] for fila in ws.iter_rows(values_only=True)]
    finally:
        wb.close()
    return parse_filas(filas, instrumentos)


def parse_archivo_csv(
    ruta,
    instrumentos: dict[str, Instrumento] | None = None,
    encoding: str = "utf-8-sig",
) -> list[Movimiento]:
    """Parsea un export .csv del broker (separador ',' o ';')."""
    import csv

    with open(ruta, newline="", encoding=encoding) as fh:
        muestra = fh.read(4096)
        fh.seek(0)
        try:
            dialecto = csv.Sniffer().sniff(muestra, delimiters=",;")
        except csv.Error:
            dialecto = csv.excel
        filas = list(csv.reader(fh, dialecto))
    return parse_filas(filas, instrumentos)
