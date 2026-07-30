"""Carga de la cartera nativa: instrumentos (mapa Config) y movimientos.

Dos entradas:

  * ``cargar_instrumentos_en_db``  — lee la hoja ``Config`` del Excel y hace
    UPSERT en ``cartera_instrumentos`` (mapa ticker↔variante USD, categoría de
    activo, panel, moneda de cotización, divisor).
  * ``importar_movimientos``       — inserta objetos :class:`Movimiento` del
    parser en ``cartera_movimientos`` con ``INSERT OR IGNORE`` (dedupe por
    ``UNIQUE(user_id, hash_dedupe)``): re-importar el mismo export no duplica.

``instrumentos_desde_config`` devuelve el mapa ``dict[str, Instrumento]`` que
el parser necesita (mínimo: ticker, variante USD, categoría, moneda cotiz).

Todas las funciones reciben una conexión abierta y NO hacen commit salvo que
se indique: el caller controla la transacción (patrón de ``core/db.set_config``).
"""

from __future__ import annotations

from typing import Iterable

from .parser import Instrumento, Movimiento

__all__ = [
    "instrumentos_desde_config",
    "cargar_instrumentos_en_db",
    "importar_movimientos",
    "congelar_tc_mep",
    "detectar_tipo",
    "TIPO_MOVIMIENTOS",
    "TIPO_TENENCIA",
    "TIPO_EXCEL_PROPIO",
    "TIPO_DESCONOCIDO",
]

# Índices 0-based de las columnas de Config (G..N).
_G, _H, _I, _J, _K, _L, _M, _N = 6, 7, 8, 9, 10, 11, 12, 13


def _filas_config(ruta_excel):
    """Yield de filas (tuplas) de la hoja Config desde la 5 (datos)."""
    import openpyxl  # import perezoso
    wb = openpyxl.load_workbook(ruta_excel, data_only=True, read_only=True)
    try:
        ws = wb["Config"]
        for fila in ws.iter_rows(min_row=5, values_only=True):
            if len(fila) > _G and fila[_G] not in (None, ""):
                yield fila
    finally:
        wb.close()


def instrumentos_desde_config(ruta_excel) -> dict[str, Instrumento]:
    """Mapa ticker→:class:`Instrumento` para el parser (desde Config!G:N)."""
    insts: dict[str, Instrumento] = {}
    for fila in _filas_config(ruta_excel):
        ticker = str(fila[_G]).strip()
        insts[ticker] = Instrumento(
            ticker=ticker,
            ticker_usd=str(fila[_H]).strip() if fila[_H] else None,
            categoria_activo=str(fila[_J] or "").strip(),
            moneda_cotiz=str(fila[_M] or "ARS").strip(),
            # Config!L "Activo en cartera": NO = vencido/canjeado (sin tenencia).
            activo=str(fila[_L]).strip().upper() != "NO",
        )
    return insts


def cargar_instrumentos_en_db(conn, ruta_excel, user_id: int) -> int:
    """UPSERT de todos los instrumentos de Config en ``cartera_instrumentos``.

    Devuelve la cantidad de instrumentos cargados. No hace commit.
    """
    n = 0
    for fila in _filas_config(ruta_excel):
        conn.execute(
            "INSERT INTO cartera_instrumentos "
            "(ticker, user_id, ticker_usd, descripcion, categoria_activo, "
            " panel_precio, moneda_cotiz, divisor_usd, activo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(ticker, user_id) DO UPDATE SET "
            "  ticker_usd=excluded.ticker_usd, descripcion=excluded.descripcion, "
            "  categoria_activo=excluded.categoria_activo, "
            "  panel_precio=excluded.panel_precio, moneda_cotiz=excluded.moneda_cotiz, "
            "  divisor_usd=excluded.divisor_usd, activo=excluded.activo",
            (
                str(fila[_G]).strip(),
                user_id,
                str(fila[_H]).strip() if fila[_H] else None,
                str(fila[_I]).strip() if fila[_I] else None,
                str(fila[_J]).strip() if fila[_J] else None,
                str(fila[_K]).strip() if fila[_K] else None,
                str(fila[_M] or "ARS").strip(),
                float(fila[_N]) if isinstance(fila[_N], (int, float)) else None,
                0 if str(fila[_L]).strip().upper() == "NO" else 1,
            ),
        )
        n += 1
    return n


def _fecha(d) -> str | None:
    return d.isoformat() if d is not None else None


def importar_movimientos(
    conn, movimientos: Iterable[Movimiento], user_id: int
) -> tuple[int, int]:
    """Inserta movimientos en ``cartera_movimientos`` (dedupe por hash).

    Devuelve ``(insertados, saltados)``. Envuelve el bulk en una transacción
    y commitea al final (la carga recurrente es una unidad atómica).
    """
    insertados = saltados = 0
    conn.execute("BEGIN")
    try:
        for m in movimientos:
            cur = conn.execute(
                "INSERT OR IGNORE INTO cartera_movimientos "
                "(user_id, fecha_concertacion, fecha_liquidacion, categoria, "
                " descripcion, monto, cantidad, precio, moneda, ticker_crudo, "
                " ticker_base, operacion_original, formato, es_instrumento, "
                " es_espejo, es_saldo_inicial, precio_normalizado, tc_mep, "
                " hash_dedupe) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    user_id,
                    _fecha(m.fecha_concertacion),
                    _fecha(m.fecha_liquidacion),
                    m.categoria,
                    m.descripcion,
                    m.monto,
                    m.cantidad,
                    m.precio,
                    m.moneda,
                    m.ticker_crudo,
                    m.ticker_base,
                    m.operacion_original,
                    m.formato,
                    int(m.es_instrumento),
                    int(m.es_espejo),
                    int(m.es_saldo_inicial),
                    m.precio_normalizado,
                    None,  # tc_mep: lo congela market_data (paso 3)
                    m.hash_dedupe,
                ),
            )
            if cur.rowcount == 1:
                insertados += 1
            else:
                saltados += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return insertados, saltados


def congelar_tc_mep(conn, serie_mep: dict[str, float], user_id: int,
                    solo_faltantes: bool = True) -> tuple[int, list[str]]:
    """Graba en cada movimiento el MEP de SU fecha (ADR-0003 / ADR-0004).

    El TC queda **congelado por fila**: una caída futura de la fuente no
    altera los movimientos ya importados. Para fechas sin cotización
    (fin de semana, feriado) se usa el último día hábil anterior.

    :param serie_mep: ``{'YYYY-MM-DD': valor}`` (inyectada: esta función no
        toca la red; la trae `core.market_data.serie_mep_con_fallback`).
    :param solo_faltantes: si es True (default) solo completa filas con
        ``tc_mep`` NULL → idempotente y no pisa lo ya congelado.
    :return: ``(actualizados, fechas_sin_dato)``.
    """
    from core.market_data.mep import mep_para_fecha  # import diferido

    sql = (
        "SELECT id, fecha_concertacion FROM cartera_movimientos WHERE user_id = ?"
    )
    if solo_faltantes:
        sql += " AND tc_mep IS NULL"
    filas = conn.execute(sql, (user_id,)).fetchall()

    actualizados = 0
    sin_dato: list[str] = []
    conn.execute("BEGIN")
    try:
        for fila in filas:
            tc = mep_para_fecha(serie_mep, fila["fecha_concertacion"])
            if tc is None:
                sin_dato.append(fila["fecha_concertacion"])
                continue
            conn.execute(
                "UPDATE cartera_movimientos SET tc_mep = ? WHERE id = ?",
                (float(tc), fila["id"]),
            )
            actualizados += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return actualizados, sorted(set(sin_dato))


# ---------------------------------------------------------------------------
# Carga inicial en un paso: detectar qué es cada archivo
# ---------------------------------------------------------------------------

#: Tipos que la carga inicial sabe reconocer.
TIPO_MOVIMIENTOS = "movimientos"
TIPO_TENENCIA = "tenencia"
TIPO_EXCEL_PROPIO = "excel_propio"     # Inversiones.xlsx (Config + crudo)
TIPO_DESCONOCIDO = "desconocido"


def detectar_tipo(archivo) -> str:
    """Reconoce qué archivo es, por su estructura — no por el nombre.

    Así Franco puede arrastrar los tres juntos sin decir cuál es cuál:

    * **Excel propio** (`Inversiones.xlsx`): tiene las hojas ``Config`` y
      ``Movimientos Crudo``. Es el que trae los **saldos iniciales sintéticos**,
      así que su crudo debe importarse primero (ver nota en ESTADO.md).
    * **Tenencia** del broker: la cabecera dice "Fecha de valuación" y
      "TC USD MEP".
    * **Movimientos** del broker: encabezados Operación / Concertación /
      Descripción.
    """
    import openpyxl

    try:
        wb = openpyxl.load_workbook(archivo, data_only=True, read_only=True)
    except Exception:
        return TIPO_DESCONOCIDO
    try:
        hojas = set(wb.sheetnames)
        if {"Config", "Movimientos Crudo"} <= hojas:
            return TIPO_EXCEL_PROPIO
        ws = wb.worksheets[0]
        primeras = []
        for i, fila in enumerate(ws.iter_rows(values_only=True)):
            primeras.append(" ".join(str(c) for c in fila if c is not None))
            if i >= 12:
                break
        texto = " ".join(primeras)
        if "Fecha de valuación" in texto or "TC USD MEP" in texto:
            return TIPO_TENENCIA
        if "Concertación" in texto and "Descripción" in texto:
            return TIPO_MOVIMIENTOS
        return TIPO_DESCONOCIDO
    finally:
        wb.close()
        try:                      # el uploader de Streamlit se puede rebobinar
            archivo.seek(0)
        except Exception:
            pass
