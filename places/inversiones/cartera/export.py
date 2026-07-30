"""Export de la cartera a Excel — hoja "Resumen Cartera" con formato.

Toma la estética de la planilla de Franco (encabezados azul ``1F4E78`` con
texto blanco, totales en gris ``F2F2F2``) y le suma lo que le falta:

  * **formatos de número reales** — en el Excel original todas las celdas del
    Resumen están en "General", así que los importes salen crudos;
  * **colores semánticos** en ganancia/pérdida, siempre con signo (nunca color
    solo: regla de accesibilidad de `ui-ux-web-moderno`);
  * **cifras alineadas a la derecha** y fuente monoespaciada en los números;
  * **bloque de KPIs** arriba: patrimonio, capital aportado, resultado y la
    **TIR anualizada** en pesos y dólares;
  * **subtotales por tipo de activo** y peso de cada posición en la cartera;
  * panel congelado y autofiltro para trabajar la tabla larga.

Los valores derivados van como **fórmulas de Excel** (no como números
calculados en Python), así la planilla sigue viva: si se cambia un precio, todo
recalcula.
"""

from __future__ import annotations

from datetime import date

__all__ = ["exportar_cartera", "PALETA"]

#: Paleta: la identidad de la planilla de Franco + semánticos accesibles.
PALETA = {
    "encabezado": "1F4E78",     # azul de sus encabezados
    "encabezado_txt": "FFFFFF",
    "titulo": "0F2C47",         # un paso más oscuro, para la barra de título
    "subtotal": "F2F2F2",       # gris de sus totales
    "total": "D9E2F3",          # azul muy claro para el total general
    "banda": "FAFBFC",          # zebra sutil
    "positivo": "107C41",       # verde
    "negativo": "C00000",       # rojo
    "muted": "6B7280",
    "borde": "BFBFBF",
}

_FMT_ARS = '"$"#,##0;("$"#,##0);-'
_FMT_ARS_2 = '"$"#,##0.00;("$"#,##0.00);-'
_FMT_USD = '"US$"#,##0;("US$"#,##0);-'
_FMT_USD_2 = '"US$"#,##0.00;("US$"#,##0.00);-'
_FMT_PCT = '0.0%;(0.0%);-'
_FMT_CANT = '#,##0.####;(#,##0.####);-'
_FMT_CANT_CRIPTO = '#,##0.00000000'

_COLS = [
    ("Ticker", 14), ("Descripción", 30), ("Tipo", 12), ("Cantidad", 13),
    ("PPC ARS", 13), ("Precio actual", 14), ("Valor ARS", 15),
    ("Valor USD", 13), ("% cartera", 11), ("Costo ARS", 15),
    ("Ganancia ARS", 15), ("Rend %", 10), ("Rend USD %", 11),
    ("Precio de", 14),
]


def _estilos():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    borde = Side(style="thin", color=PALETA["borde"])
    return {
        "Font": Font, "PatternFill": PatternFill, "Alignment": Alignment,
        "Border": Border, "Side": Side, "borde_fino": Border(bottom=borde),
    }


def exportar_cartera(
    ruta,
    valuadas,
    kpis,
    fecha_valuacion: date | None = None,
    mep: float | None = None,
    fuente_precios: str = "",
    nombres: dict | None = None,
    tipos: dict | None = None,
    efectivo_ars: float = 0.0,
    efectivo_usd: float = 0.0,
    nombre_hoja: str = "Resumen Cartera",
):
    """Escribe el Excel de la cartera y devuelve la ruta.

    :param valuadas: lista de ``PosicionValuada`` (de `kpis.valuar`).
    :param kpis: ``KPIs`` ya completado con `completar_patrimonio`.
    :param nombres: ``{ticker: nombre}`` para la columna Descripción (sale de
        la tenencia del broker).
    :param tipos: ``{ticker: tipo}`` para clasificar lo que no está en Config
        (los pagarés, por ejemplo, que el Excel nunca tuvo).
    :param efectivo_ars/efectivo_usd: saldos en la cuenta. Van como dos filas
        más de la tabla, así el TOTAL coincide con el patrimonio de los KPIs
        (si no, la suma de posiciones da menos y parece un error).
    """
    nombres = nombres or {}
    tipos = tipos or {}
    import openpyxl
    from openpyxl.formatting.rule import DataBarRule
    from openpyxl.utils import get_column_letter

    e = _estilos()
    Font, Fill, Align = e["Font"], e["PatternFill"], e["Alignment"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = nombre_hoja
    ws.sheet_view.showGridLines = False

    base = Font(name="Arial", size=10)
    mono = Font(name="Consolas", size=10)
    fecha = fecha_valuacion or date.today()

    # ---- Título -----------------------------------------------------------
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(_COLS))
    t = ws.cell(1, 1, f"CARTERA DE INVERSIONES · valuación al {fecha:%d/%m/%Y}")
    t.font = Font(name="Arial", size=14, bold=True, color="FFFFFF")
    t.fill = Fill("solid", fgColor=PALETA["titulo"])
    t.alignment = Align(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 30

    sub = ws.cell(2, 1, fuente_precios)
    sub.font = Font(name="Arial", size=9, italic=True, color=PALETA["muted"])
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=6)
    # El MEP vive en su propia celda (amarilla, editable) y TODAS las columnas
    # en dólares la referencian: cambiarlo recalcula la planilla entera.
    ws.cell(2, 7, "MEP usado →").font = Font(name="Arial", size=9, bold=True)
    ws.cell(2, 7).alignment = Align(horizontal="right")
    cmep = ws.cell(2, 8, mep)
    cmep.number_format = _FMT_ARS_2
    cmep.font = Font(name="Consolas", size=10, bold=True, color="0000FF")
    cmep.fill = Fill("solid", fgColor="FFFF00")
    cmep.alignment = Align(horizontal="right")

    # ---- KPIs -------------------------------------------------------------
    fila = 4
    ws.cell(fila, 1, "CÓMO VIENE LA CARTERA").font = Font(
        name="Arial", size=11, bold=True, color=PALETA["encabezado"])
    fila += 1
    tot_ars, tot_usd = kpis.resultado_total_ars, kpis.resultado_total_usd
    kpi_defs = [
        ("Patrimonio hoy", kpis.patrimonio_ars, _FMT_ARS, kpis.patrimonio_usd, _FMT_USD, None),
        ("Capital aportado", kpis.aportado_ars, _FMT_ARS, kpis.aportado_usd, _FMT_USD, None),
        ("Resultado", tot_ars, _FMT_ARS, tot_usd, _FMT_USD, "semaforo"),
        ("Rendimiento acumulado",
         (kpis.rendimiento_total_pct or 0) / 100, _FMT_PCT,
         (kpis.rendimiento_total_usd_pct or 0) / 100, _FMT_PCT, "semaforo"),
        ("Rendimiento anual (TIR)", kpis.tir_ars, _FMT_PCT, kpis.tir_usd, _FMT_PCT, "semaforo"),
    ]
    ws.cell(fila, 2, "en pesos").font = Font(name="Arial", size=9, bold=True,
                                             color=PALETA["muted"])
    ws.cell(fila, 3, "en dólares").font = Font(name="Arial", size=9, bold=True,
                                               color=PALETA["muted"])
    fila += 1
    fila_kpi_ini = fila
    for etiqueta, v_ars, f_ars, v_usd, f_usd, tono in kpi_defs:
        c = ws.cell(fila, 1, etiqueta)
        c.font = Font(name="Arial", size=10, bold=True)
        for col, val, fmt in ((2, v_ars, f_ars), (3, v_usd, f_usd)):
            cc = ws.cell(fila, col, val if val is not None else None)
            cc.number_format = fmt
            color = None
            if tono == "semaforo" and isinstance(val, (int, float)):
                color = PALETA["positivo"] if val >= 0 else PALETA["negativo"]
            cc.font = Font(name="Consolas", size=10, bold=True, color=color)
            cc.alignment = Align(horizontal="right")
        fila += 1

    ws.cell(fila, 1, f"Período: {kpis.dias} días ({kpis.meses:.1f} meses)").font = \
        Font(name="Arial", size=9, italic=True, color=PALETA["muted"])
    fila += 2

    # ---- Tabla de posiciones ---------------------------------------------
    fila_hdr = fila
    for i, (titulo, ancho) in enumerate(_COLS, start=1):
        c = ws.cell(fila_hdr, i, titulo)
        c.font = Font(name="Arial", size=10, bold=True, color=PALETA["encabezado_txt"])
        c.fill = Fill("solid", fgColor=PALETA["encabezado"])
        c.alignment = Align(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = ancho
    ws.row_dimensions[fila_hdr].height = 28

    # Agrupadas por tipo de activo, cada grupo con su subtotal.
    vivas = [p for p in valuadas if not p.cerrada and p.valor_ars]
    vivas.sort(key=lambda p: (tipos.get(p.ticker) or p.categoria_activo
                              or "Otros", -(p.valor_ars or 0)))
    fila = fila_hdr + 1
    fila_datos_ini = fila
    filas_subtotal: list[int] = []
    grupo_actual = None
    grupo_ini = fila

    def _escribir_subtotal(desde: int, hasta: int, etiqueta: str) -> int:
        nonlocal fila
        for col in range(1, len(_COLS) + 1):
            c = ws.cell(fila, col)
            c.fill = Fill("solid", fgColor=PALETA["subtotal"])
            c.font = Font(name="Arial", size=10, bold=True)
        ws.cell(fila, 1, f"Subtotal {etiqueta}")
        for col, fmt in ((7, _FMT_ARS), (8, _FMT_USD), (10, _FMT_ARS),
                         (11, _FMT_ARS)):
            L = get_column_letter(col)
            c = ws.cell(fila, col, f"=SUM({L}{desde}:{L}{hasta})")
            c.number_format = fmt
            c.font = Font(name="Consolas", size=10, bold=True)
            c.alignment = Align(horizontal="right")
        # Rend % del grupo (ganancia sobre costo) — el % de cartera se
        # completa al final, cuando existe la fila del total.
        c = ws.cell(fila, 12, f"=IFERROR(K{fila}/J{fila},0)")
        c.number_format = _FMT_PCT
        c.font = Font(name="Consolas", size=10, bold=True)
        c.alignment = Align(horizontal="right")
        filas_subtotal.append(fila)
        fila += 1
        return fila

    for p in vivas:
        tipo = tipos.get(p.ticker) or p.categoria_activo or "Otros"
        if grupo_actual is not None and tipo != grupo_actual:
            fila = _escribir_subtotal(grupo_ini, fila - 1, grupo_actual)
            grupo_ini = fila
        grupo_actual = tipo

        f = fila
        ws.cell(f, 1, p.ticker).font = Font(name="Arial", size=10, bold=True)
        ws.cell(f, 2, nombres.get(p.ticker, "")).font = base
        ws.cell(f, 3, tipo).font = base
        for col, val, fmt in (
            (4, p.cantidad,
             _FMT_CANT_CRIPTO if abs(p.cantidad) < 1 else _FMT_CANT),
            (5, p.ppc_ars, _FMT_ARS_2),
            (6, p.precio, _FMT_ARS_2),
        ):
            c = ws.cell(f, col, val)
            c.number_format = fmt
            c.font = mono
            c.alignment = Align(horizontal="right")
        # Derivados como FÓRMULAS: la planilla sigue viva.
        c = ws.cell(f, 7, f"=D{f}*F{f}")            # Valor ARS
        c.number_format = _FMT_ARS; c.font = mono
        c = ws.cell(f, 8, f"=IFERROR(G{f}/$H$2,0)")   # Valor USD al MEP
        c.number_format = _FMT_USD; c.font = mono
        c = ws.cell(f, 9, None)                     # % cartera (se completa abajo)
        c.number_format = _FMT_PCT; c.font = mono
        c = ws.cell(f, 10, p.costo_ars)             # Costo ARS
        c.number_format = _FMT_ARS; c.font = mono
        c = ws.cell(f, 11, f"=G{f}-J{f}")           # Ganancia ARS
        c.number_format = _FMT_ARS; c.font = mono
        c = ws.cell(f, 12, f"=IFERROR(K{f}/J{f},0)")  # Rend %
        c.number_format = _FMT_PCT; c.font = mono
        c = ws.cell(f, 13, (p.rendimiento_usd_pct or 0) / 100
                    if p.rendimiento_usd_pct is not None else None)
        c.number_format = _FMT_PCT; c.font = mono
        c = ws.cell(f, 14, p.origen_precio)
        c.font = Font(name="Arial", size=9, color=PALETA["muted"])
        for col in range(4, 14):
            ws.cell(f, col).alignment = Align(horizontal="right")
        if (f - fila_datos_ini) % 2 == 1:
            for col in range(1, len(_COLS) + 1):
                if ws.cell(f, col).fill.start_color.rgb in (None, "00000000"):
                    ws.cell(f, col).fill = Fill("solid", fgColor=PALETA["banda"])
        fila += 1

    if grupo_actual is not None:
        fila = _escribir_subtotal(grupo_ini, fila - 1, grupo_actual)

    # Efectivo: dos filas más, para que el TOTAL sea el patrimonio completo.
    if efectivo_ars or efectivo_usd:
        grupo_ini = fila
        for etiqueta, monto, es_usd in (
            ("ARS", efectivo_ars, False), ("USD", efectivo_usd, True),
        ):
            if not monto:
                continue
            f = fila
            ws.cell(f, 1, etiqueta).font = Font(name="Arial", size=10, bold=True)
            ws.cell(f, 2, "Pesos en cuenta" if not es_usd
                    else "Dólares en cuenta").font = base
            ws.cell(f, 3, "Efectivo").font = base
            c = ws.cell(f, 4, monto)
            c.number_format = _FMT_CANT; c.font = mono
            c = ws.cell(f, 6, 1 if not es_usd else None)
            if not es_usd:
                c.number_format = _FMT_ARS_2; c.font = mono
            # Valor ARS: los dólares se pasan por el MEP de la celda H2.
            c = ws.cell(f, 7, f"=D{f}" if not es_usd else f"=D{f}*$H$2")
            c.number_format = _FMT_ARS; c.font = mono
            c = ws.cell(f, 8, f"=IFERROR(G{f}/$H$2,0)")
            c.number_format = _FMT_USD; c.font = mono
            c = ws.cell(f, 10, f"=G{f}")     # el efectivo no tiene resultado
            c.number_format = _FMT_ARS; c.font = mono
            c = ws.cell(f, 11, 0)
            c.number_format = _FMT_ARS; c.font = mono
            for col in range(4, 14):
                ws.cell(f, col).alignment = Align(horizontal="right")
            fila += 1
        fila = _escribir_subtotal(grupo_ini, fila - 1, "Efectivo")

    # ---- Total general ----------------------------------------------------
    fila_total = fila
    for col in range(1, len(_COLS) + 1):
        c = ws.cell(fila_total, col)
        c.fill = Fill("solid", fgColor=PALETA["total"])
        c.font = Font(name="Arial", size=11, bold=True)
    ws.cell(fila_total, 1, "TOTAL CARTERA")
    for col, fmt in ((7, _FMT_ARS), (8, _FMT_USD), (10, _FMT_ARS), (11, _FMT_ARS)):
        L = get_column_letter(col)
        partes = "+".join(f"{L}{fs}" for fs in filas_subtotal) or f"{L}{fila_datos_ini}"
        c = ws.cell(fila_total, col, f"={partes}")
        c.number_format = fmt
        c.font = Font(name="Consolas", size=11, bold=True)
        c.alignment = Align(horizontal="right")
    for col, formula in (
        (9, f"=IFERROR(G{fila_total}/G{fila_total},0)"),   # 100%
        (12, f"=IFERROR(K{fila_total}/J{fila_total},0)"),
    ):
        c = ws.cell(fila_total, col, formula)
        c.number_format = _FMT_PCT
        c.font = Font(name="Consolas", size=11, bold=True)
        c.alignment = Align(horizontal="right")

    # % de cartera de cada fila (posiciones Y subtotales), contra el total.
    for f in range(fila_datos_ini, fila_total):
        c = ws.cell(f, 9, f"=IFERROR(G{f}/$G${fila_total},0)")
        c.number_format = _FMT_PCT
        c.font = Font(name="Consolas", size=10, bold=f in filas_subtotal)
        c.alignment = Align(horizontal="right")

    # Barra de datos sobre el peso de cada posición: se lee de un vistazo.
    # (Solo si hay filas: con la cartera vacía el rango sería inválido.)
    if fila_total - 1 >= fila_datos_ini:
        ws.conditional_formatting.add(
            f"I{fila_datos_ini}:I{fila_total - 1}",
            DataBarRule(start_type="num", start_value=0, end_type="num",
                        end_value=1, color=PALETA["encabezado"], showValue=True),
        )

    ws.freeze_panes = ws.cell(fila_hdr + 1, 1)
    # Sin filas de datos el rango sería inválido (openpyxl lanza TypeError).
    if fila_total - 1 > fila_hdr:
        ws.auto_filter.ref = f"A{fila_hdr}:N{fila_total - 1}"

    # ---- Nota al pie: metodología (regla del skill: documentar supuestos) --
    nota = fila_total + 2
    for txt in (
        "Metodología:",
        "· Costo a precio promedio ponderado de compra (PPC).",
        "· El dólar de cada operación queda congelado a la fecha en que se hizo "
        "(serie MEP); el rendimiento en dólares usa ese TC, no el de hoy.",
        "· Resultado y rendimiento totales por método del patrimonio: "
        "(tenencia + efectivo) − (depósitos − retiros).",
        "· TIR: tasa anual que pondera cuánto tiempo estuvo invertido cada aporte.",
        "· 'Precio de' indica el origen: broker (tenencia importada), proveedor "
        "(mercado en vivo), override (fijado a mano) o última tenencia.",
    ):
        c = ws.cell(nota, 1, txt)
        c.font = Font(name="Arial", size=9, bold=txt.endswith(":"),
                      color=PALETA["muted"] if not txt.endswith(":") else "000000")
        nota += 1

    wb.save(ruta)
    return ruta
