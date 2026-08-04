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

from core.db import backup_db

from .parser import Instrumento, Movimiento

__all__ = [
    "instrumentos_desde_config",
    "cargar_instrumentos_en_db",
    "importar_movimientos",
    "congelar_tc_mep",
    "remapear_tickers_base",
    "movimientos_de_ticker",
    "corregir_movimiento",
    "detectar_tipo",
    "TIPO_MOVIMIENTOS",
    "TIPO_TENENCIA",
    "TIPO_EXCEL_PROPIO",
    "TIPO_EXPORT_APP",
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

    **Saca una copia de seguridad antes de empezar.** Un import masivo es la
    operación más destructiva de la app: si el archivo está mal, entran cientos
    de filas equivocadas y el dedupe hace que reimportar el bueno no las
    arregle. Hasta la Fase 4 solo las escrituras de Finanzas Personales
    disparaban backup, así que cargar 585 movimientos de cartera no dejaba
    ningún punto de retorno.
    """
    backup_db()
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
TIPO_EXPORT_APP = "export_app"        # el "Cartera - Resumen" que genera la app
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
        # El export que genera la app: se confunde fácil con el Excel propio
        # porque queda en la misma carpeta y su nombre también arranca con
        # "Cartera". Reconocerlo permite dar un mensaje útil en vez de
        # "no reconocido".
        if "Resumen Cartera" in hojas and "Config" not in hojas:
            ws0 = wb["Resumen Cartera"]
            if str(ws0.cell(1, 1).value or "").startswith("CARTERA DE INVERSIONES"):
                return TIPO_EXPORT_APP
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


def remapear_tickers_base(conn, instrumentos: dict, user_id: int) -> int:
    """Recalcula ``ticker_base`` de los movimientos ya importados.

    **Por qué existe (bug real en producción):** ``ticker_base`` se resuelve
    *al importar*, usando el mapa de instrumentos. Si se importan movimientos
    **sin** ese mapa, las variantes en dólares quedan sin plegar — ``SPYD``,
    ``GOGLD``, ``NVDAD``… figuran como posiciones propias en vez de sumarse a
    ``SPY``, ``GOOGL``, ``NVDA``. Y como el dedupe salta las filas ya
    existentes, **reimportar con el Excel no lo corregía**: el error quedaba
    grabado, inflando el costo y las posiciones.

    Es idempotente: solo toca las filas cuyo ``ticker_base`` no coincide con el
    mapping actual. Devuelve cuántas corrigió.
    """
    if not instrumentos:
        return 0
    # ticker (base o variante USD) → ticker base canónico
    canonico: dict[str, str] = {}
    for inst in instrumentos.values():
        canonico[inst.ticker] = inst.ticker
        if inst.ticker_usd:
            canonico[inst.ticker_usd] = inst.ticker

    filas = conn.execute(
        "SELECT id, ticker_crudo, ticker_base FROM cartera_movimientos "
        "WHERE user_id = ?", (user_id,),
    ).fetchall()
    corregidas = 0
    conn.execute("BEGIN")
    try:
        for f in filas:
            esperado = canonico.get(f["ticker_crudo"])
            if esperado and esperado != f["ticker_base"]:
                conn.execute(
                    "UPDATE cartera_movimientos SET ticker_base = ? WHERE id = ?",
                    (esperado, f["id"]),
                )
                corregidas += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return corregidas


def movimientos_de_ticker(conn, user_id: int, ticker: str) -> list[dict]:
    """Movimientos de un ticker (base o crudo), del más nuevo al más viejo."""
    t = (ticker or "").strip().upper()
    if not t:
        return []
    filas = conn.execute(
        "SELECT id, fecha_concertacion, categoria, descripcion, ticker_crudo, "
        "       ticker_base, monto, cantidad, precio, moneda "
        "FROM cartera_movimientos "
        "WHERE user_id = ? AND (ticker_base = ? OR ticker_crudo = ?) "
        "ORDER BY fecha_concertacion DESC, id DESC",
        (user_id, t, t),
    ).fetchall()
    return [dict(f) for f in filas]


def corregir_movimiento(
    conn, user_id: int, mov_id: int, *,
    monto: float | None = None,
    cantidad: float | None = None,
    precio: float | None = None,
) -> bool:
    """Corrige un movimiento ya importado y **recalcula su `hash_dedupe`**.

    **Por qué existe.** El broker se equivoca: en el caso real que la motivó,
    inviu informó una compra de ASML de 9 unidades a **$60,10** cuando fueron
    a **$6.010** — dos ceros de menos. Ese dato ya importado no se puede
    arreglar solo editando el Excel: el hash de dedupe se calcula sobre el
    monto, así que la fila corregida entraría como **movimiento nuevo** y
    quedarían las dos (18 unidades de ASML en vez de 9). Es la misma trampa
    que el `ticker_base` del 30/7.

    Por eso la corrección **recalcula el hash con la regla del parser**
    (`parser.hash_dedupe`): después de corregir acá y corregir el Excel con
    los mismos valores, reimportar el Excel **dedupea** en vez de duplicar.

    Si el hash resultante ya existe (había otra operación idéntica), se prueba
    con la siguiente ocurrencia, igual que hace el parser dentro de un archivo.

    El `precio_normalizado` (bonos que cotizan por 100) se reescala en la
    misma proporción que el precio, para no perder la regla del LEEME.
    Devuelve ``True`` si corrigió algo.
    """
    from places.inversiones.cartera.parser import hash_dedupe

    backup_db()
    f = conn.execute(
        "SELECT * FROM cartera_movimientos WHERE id = ? AND user_id = ?",
        (mov_id, user_id),
    ).fetchone()
    if f is None:
        return False

    nuevo_monto = f["monto"] if monto is None else float(monto)
    nueva_cant = f["cantidad"] if cantidad is None else float(cantidad)
    nuevo_precio = f["precio"] if precio is None else float(precio)
    if (nuevo_monto == f["monto"] and nueva_cant == f["cantidad"]
            and nuevo_precio == f["precio"]):
        return False

    # El precio normalizado guarda la misma relación con el precio crudo
    # (÷100 en bonos): se reescala en vez de recalcularse a ciegas.
    norm = f["precio_normalizado"]
    if norm is not None and f["precio"]:
        norm = norm * (nuevo_precio / f["precio"])
    elif norm is not None:
        norm = nuevo_precio

    usados = {
        r["hash_dedupe"] for r in conn.execute(
            "SELECT hash_dedupe FROM cartera_movimientos "
            "WHERE user_id = ? AND id <> ?", (user_id, mov_id))
    }
    for ocurrencia in range(100):
        nuevo_hash = hash_dedupe(
            f["fecha_concertacion"], f["categoria"], f["descripcion"],
            nuevo_monto, nueva_cant, ocurrencia,
        )
        if nuevo_hash not in usados:
            break
    else:  # pragma: no cover - 100 operaciones idénticas es imposible
        raise RuntimeError("no se pudo generar un hash de dedupe libre")

    conn.execute(
        "UPDATE cartera_movimientos SET monto = ?, cantidad = ?, precio = ?, "
        "       precio_normalizado = ?, hash_dedupe = ? "
        "WHERE id = ? AND user_id = ?",
        (nuevo_monto, nueva_cant, nuevo_precio, norm, nuevo_hash, mov_id,
         user_id),
    )
    return True
