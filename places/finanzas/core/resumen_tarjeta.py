"""Lector de los resúmenes AMEX y VISA de Galicia (PDF con texto). Fase D, paso 5.

Sin IA (ADR-0009): el formato se estudió con los 9 resúmenes reales de Franco
el 18/10/2026. Dos pasos, a propósito:

1. `palabras_del_pdf` — lo único que toca `pdfplumber`: el PDF → palabras con
   su posición (página, alto, x0, x1).
2. `leer_resumen` — puro: palabras → `Resumen`. Se prueba con listas de
   palabras armadas a mano, sin PDF.

Lo que importa del formato:

* **Pesos o dólares se decide por la columna** (la x del número contra la de
  los títulos PESOS y DÓLARES). Con el texto solo no alcanza:
  ``AIRBNB … USD 344,00 791072 344,00`` tiene dos números y uno solo es dólares.
* Se lee **desde CONSOLIDADO hasta TOTAL A PAGAR**. Lo de antes es el
  encabezado (nombre, dirección, CUIT, número de cuenta): **no se lee**. Lo de
  después (planes de cuotas, "Cuotas a vencer") tampoco.
* Una línea del detalle empieza con su fecha (``15-09-26``). Los consumos van
  agrupados por plástico y cada grupo cierra con ``TARJETA nnnn Total
  Consumos…``; después vienen IIBB, IVA y la percepción del 30%.
* **El resumen trae su propia cuenta y se verifica:** saldo anterior + todo
  lo del detalle = TOTAL A PAGAR, en pesos y en dólares, y cada subtotal de
  plástico = la suma de sus consumos. Si no cierra, `ResumenInvalido`: nunca
  se adivina un número.

Montos en **centavos enteros**.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8,
         "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}
_RE_FECHA_LARGA = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{2})$")
_RE_FECHA = re.compile(r"^(\d{2})-(\d{2})-(\d{2})$")
_RE_MONTO = re.compile(r"^(-?)(\d{1,3}(?:\.\d{3})+|\d+),(\d{2})$")
_RE_CUOTA = re.compile(r"^\d{2}/\d{2}$")
#: Distancia máxima (en puntos) entre el borde derecho de un número y el de su columna.
_TOLERANCIA_X = 25
#: Palabras de la misma línea: alto parecido.
_TOLERANCIA_ALTO = 3


class ResumenInvalido(ValueError):
    """El PDF no es un resumen que se pueda leer, o su cuenta no cierra. El texto va a Franco."""


@dataclass(frozen=True)
class Palabra:
    pagina: int
    alto: float      # `top` de pdfplumber
    x0: float
    x1: float
    texto: str


@dataclass(frozen=True)
class Consumo:
    fecha: date                 # la de la compra
    referencia: str
    pesos: int                  # centavos
    dolares: int                # centavos de dólar
    cuota: Optional[str] = None  # "03/12"
    plastico: Optional[str] = None  # los últimos 4 números de la tarjeta

    @property
    def comercio(self) -> str:
        """La referencia sin los códigos de cada compra: para aprender la categoría.

        ``AIRBNB * HM5YBSHC9H USD 344,00`` → ``AIRBNB``; ``ANTHROPIC* CLAUD in1UGK8DBUSD`` →
        ``ANTHROPIC* CLAUD``. Se cae todo token con un número y las monedas sueltas.
        """
        partes = [p for p in self.referencia.split()
                  if not any(c.isdigit() for c in p) and p not in {"USD", "EUR", "*"}]
        return " ".join(partes) or self.referencia


@dataclass(frozen=True)
class Linea:
    """Una línea con fecha que no es un consumo (pago, impuesto, percepción)."""

    fecha: date
    texto: str
    pesos: int
    dolares: int


@dataclass
class Resumen:
    tarjeta: str                       # "AMEX" | "VISA"
    cierre_anterior: date
    vencimiento_anterior: date
    cierre: date
    vencimiento: date
    cierre_proximo: date
    vencimiento_proximo: date
    saldo_anterior: tuple[int, int]    # (pesos, dólares)
    total: tuple[int, int]
    pagos: list[Linea] = field(default_factory=list)          # SU PAGO EN PESOS / USD
    devoluciones: list[Linea] = field(default_factory=list)   # DEV.IMP. RG 5617 (negativas)
    consumos: list[Consumo] = field(default_factory=list)
    cargos: list[Linea] = field(default_factory=list)         # IIBB, IVA, intereses…
    percepciones: list[Linea] = field(default_factory=list)   # DB.RG 5617 30%

    @property
    def pagado_en_pesos(self) -> int:
        """Lo que el resumen dice que se pagó del anterior (positivo)."""
        return -sum(p.pesos for p in self.pagos)

    @property
    def gastos_reales(self) -> int:
        """Consumos en pesos + IIBB + IVA (+ intereses o comisiones): lo que se gastó."""
        return sum(c.pesos for c in self.consumos) + sum(c.pesos for c in self.cargos)


# ---------------------------------------------------------------------------
# PDF → palabras (lo único que usa pdfplumber)
# ---------------------------------------------------------------------------

def palabras_del_pdf(datos: bytes) -> list[Palabra]:
    import pdfplumber  # diferido: solo hace falta acá
    from pdfminer.pdfparser import PDFSyntaxError

    try:
        pdf = pdfplumber.open(io.BytesIO(datos))
    except (PDFSyntaxError, ValueError, OSError) as e:
        raise ResumenInvalido(f"No pude abrir el PDF ({type(e).__name__}).") from None
    with pdf:
        return [Palabra(n, float(w["top"]), float(w["x0"]), float(w["x1"]), w["text"])
                for n, pagina in enumerate(pdf.pages, 1) for w in pagina.extract_words()]


# ---------------------------------------------------------------------------
# Palabras → Resumen (puro)
# ---------------------------------------------------------------------------

def _lineas(palabras: list[Palabra]) -> list[list[Palabra]]:
    lineas: list[list[Palabra]] = []
    for p in sorted(palabras, key=lambda p: (p.pagina, p.alto, p.x0)):
        if lineas and lineas[-1][0].pagina == p.pagina and abs(
                lineas[-1][0].alto - p.alto) <= _TOLERANCIA_ALTO:
            lineas[-1].append(p)
        else:
            lineas.append([p])
    return [sorted(l, key=lambda p: p.x0) for l in lineas]


def _centavos(texto: str) -> Optional[int]:
    m = _RE_MONTO.match(texto)
    if not m:
        return None
    signo, entero, dec = m.groups()
    valor = int(entero.replace(".", "")) * 100 + int(dec)
    return -valor if signo else valor


def _fecha(texto: str) -> Optional[date]:
    m = _RE_FECHA.match(texto)
    if not m:
        return None
    d, mes, a = (int(x) for x in m.groups())
    try:
        return date(2000 + a, mes, d)
    except ValueError:
        return None


def _fecha_larga(texto: str) -> Optional[date]:
    m = _RE_FECHA_LARGA.match(texto)
    if not m or m.group(2).upper() not in MESES:
        return None
    return date(2000 + int(m.group(3)), MESES[m.group(2).upper()], int(m.group(1)))


def _texto(linea: list[Palabra]) -> str:
    return " ".join(p.texto for p in linea)


def _norm(s: str) -> str:
    return s.upper().replace("Ó", "O").replace("É", "E").replace("Í", "I").replace("Á", "A")


def leer_resumen(palabras: list[Palabra]) -> Resumen:
    lineas = _lineas(palabras)
    tarjeta = None
    fechas: list[date] = []
    columnas: Optional[tuple[float, float]] = None
    for linea in lineas:
        t = _norm(_texto(linea))
        if tarjeta is None and "TARJETA CREDITO" in t:
            tarjeta = "AMEX" if "AMERICAN EXPRESS" in t else ("VISA" if "VISA" in t else None)
        if not fechas:
            largas = [f for f in (_fecha_larga(p.texto) for p in linea) if f]
            if len(largas) >= 6:
                fechas = largas[:6]
        if columnas is None and t.startswith("CONSOLIDADO"):
            pesos = next((p for p in linea if _norm(p.texto) == "PESOS"), None)
            dolares = next((p for p in linea if _norm(p.texto).startswith("DOLARES")), None)
            if pesos and dolares:
                columnas = (pesos.x1, dolares.x1)
    if tarjeta is None:
        raise ResumenInvalido("No encontré si es AMEX o VISA: ¿es un resumen de tarjeta de Galicia?")
    if not fechas:
        raise ResumenInvalido("No encontré las fechas de cierre y vencimiento.")
    if columnas is None:
        raise ResumenInvalido("No encontré las columnas de pesos y dólares.")

    def montos(linea: list[Palabra]) -> tuple[int, int, set[int]]:
        """(pesos, dólares, índices usados) según la columna de cada número."""
        pesos = dolares = 0
        usados = set()
        for i, p in enumerate(linea):
            c = _centavos(p.texto)
            if c is None:
                continue
            if abs(p.x1 - columnas[0]) <= _TOLERANCIA_X:
                pesos += c
                usados.add(i)
            elif abs(p.x1 - columnas[1]) <= _TOLERANCIA_X:
                dolares += c
                usados.add(i)
        return pesos, dolares, usados

    r = Resumen(tarjeta, *fechas, saldo_anterior=(0, 0), total=(0, 0))
    dentro = en_detalle = False
    total = None
    pendientes: list[Consumo] = []   # los consumos del plástico en curso
    cuota_x = None
    for linea in lineas:
        t = _norm(_texto(linea))
        if not dentro:
            dentro = t.startswith("CONSOLIDADO")
            continue
        if t.startswith("TOTAL A PAGAR"):
            pesos, dolares, _ = montos(linea)
            total = (pesos, dolares)
            break
        if t.startswith("SALDO ANTERIOR"):
            r.saldo_anterior = montos(linea)[:2]
            continue
        if t.startswith("DETALLE DEL CONSUMO") or t.startswith("FECHA REFERENCIA"):
            en_detalle = True
            cuota_x = next((p.x0 for p in linea if _norm(p.texto) == "CUOTA"), cuota_x)
            continue
        if t.startswith("TARJETA ") and "TOTAL CONSUMOS" in t:
            pesos, dolares, _ = montos(linea)
            plastico = linea[1].texto if len(linea) > 1 else None
            if (sum(c.pesos for c in pendientes), sum(c.dolares for c in pendientes)) != (
                    pesos, dolares):
                raise ResumenInvalido(
                    f"El subtotal de la tarjeta terminada en {plastico} no coincide con sus "
                    "consumos: no leí bien alguna línea.")
            r.consumos.extend(Consumo(c.fecha, c.referencia, c.pesos, c.dolares, c.cuota,
                                      plastico) for c in pendientes)
            pendientes = []
            continue
        fecha = _fecha(linea[0].texto)
        if fecha is None:
            continue   # encabezados de página, pies, textos sin fecha
        pesos, dolares, usados = montos(linea)
        cuerpo = [p for i, p in enumerate(linea[1:], 1) if i not in usados]
        texto = " ".join(p.texto for p in cuerpo)
        nt = _norm(texto)
        if "SU PAGO EN" in nt:
            r.pagos.append(Linea(fecha, texto, pesos, dolares))
        elif nt.startswith("DEV.IMP"):
            r.devoluciones.append(Linea(fecha, texto, pesos, dolares))
        elif nt.startswith("DB.RG") or nt.startswith("DB RG"):
            r.percepciones.append(Linea(fecha, texto, pesos, dolares))
        elif en_detalle and (pendientes or not _es_cargo(nt)):
            # Un consumo. Adelante puede venir una marca de una letra (``*``, ``K``,
            # ``E``) pegada a la fecha; después la referencia, la cuota y el comprobante.
            cuota = next((p.texto for p in cuerpo if _RE_CUOTA.match(p.texto)
                          and (cuota_x is None or p.x0 >= cuota_x - 15)), None)
            ref = [p.texto for p in cuerpo if p.texto != cuota
                   and not (len(p.texto) == 1 and p.x0 < linea[0].x1 + 20)]
            if ref and ref[-1].isdigit():   # el comprobante
                ref = ref[:-1]
            pendientes.append(Consumo(fecha, " ".join(ref), pesos, dolares, cuota))
        else:
            r.cargos.append(Linea(fecha, texto, pesos, dolares))
    if total is None:
        raise ResumenInvalido("No encontré el TOTAL A PAGAR.")
    if pendientes:
        raise ResumenInvalido("Quedaron consumos sin el subtotal de su tarjeta.")
    r.total = total

    cuenta = [r.saldo_anterior[k] + sum(x[k] for x in (
        [(l.pesos, l.dolares) for l in r.pagos + r.devoluciones + r.cargos + r.percepciones]
        + [(c.pesos, c.dolares) for c in r.consumos])) for k in (0, 1)]
    if tuple(cuenta) != r.total:
        raise ResumenInvalido(
            f"La cuenta del resumen no cierra: saldo anterior + movimientos da "
            f"{cuenta[0] / 100:.2f} / USD {cuenta[1] / 100:.2f} y el total a pagar es "
            f"{r.total[0] / 100:.2f} / USD {r.total[1] / 100:.2f}. No leí bien alguna línea.")
    return r


def _es_cargo(texto_norm: str) -> bool:
    """IIBB, IVA, intereses, comisiones: lo que el banco cobra aparte de los consumos."""
    return texto_norm.startswith(("IIBB", "IVA ", "PERCEP", "IMP.", "IMPUESTO", "INTERES",
                                  "COMISION", "CARGO", "PUNITORIO"))
