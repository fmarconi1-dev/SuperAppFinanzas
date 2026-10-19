"""Lector del extracto de la caja de ahorro de Galicia (`.xlsx`). Fase D, paso 4.

Puro y sin IA (ADR-0009): el formato se estudió con el archivo real de Franco
el 18/10/2026. Lo que importa de él:

* **Una hoja**, unas filas de encabezado y después las columnas Fecha ·
  Movimiento · Débito · Crédito · Saldo Parcial · Comentarios. Los títulos
  vienen con los acentos rotos, así que **se lee por posición** y los datos
  arrancan en la primera fila cuya columna A es una fecha ``dd/mm/aaaa``.
* **Todo viene como texto.** Débito y crédito con puntos de miles
  (``'-200.000,00'``), el saldo sin ellos (``'153263,01'``) y a veces con
  un solo decimal (``'709269,8'`` = 709.269,80).
* **Lo más nuevo primero, también dentro del día.** El saldo de cada fila es
  el de la fila de abajo más su monto: esa **cadena** se verifica entera, y es
  lo que después permite detectar un hueco entre dos extractos.
* **El tipo de movimiento es la primera línea** de "Movimiento" (a veces con
  un número de ticket al final, a veces en minúsculas). La segunda línea, para
  algunos tipos, es el comercio o la persona. **Las demás líneas (CUIT, CBU,
  números de cuenta y de tarjeta) no se leen**: no salen de acá.

Los montos van en **centavos enteros**: la cadena y el emparejamiento no
pueden depender del redondeo de un float.
"""

from __future__ import annotations

import io
import re
import unicodedata
import warnings
import zipfile
from dataclasses import dataclass
from datetime import date
from typing import Optional

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

#: Posición de cada columna (0 = A).
COL_FECHA, COL_MOVIMIENTO, COL_DEBITO, COL_CREDITO, COL_SALDO = 0, 1, 2, 3, 4

_RE_FECHA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_RE_MONTO = re.compile(r"^(-?)(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$")
_RE_COTIZACION = re.compile(r"cotizacion:\s*([\d.]+)", re.IGNORECASE)

#: Tipos cuya segunda línea es el comercio o la persona (normalizados, por prefijo).
_TIPOS_CON_COMERCIO = (
    "COMPRA DEBITO", "PAGO DE SERVICIOS", "DEB. AUTOM. DE SERV.", "PAGO CON TRANSFERENCIA",
    "PAGO EN TRANSPORTE", "TRANSFERENCIA A TERCEROS", "TRANSFERENCIA DE TERCEROS",
    "CREDITO TRANSFERENCIA", "HONORARIOS", "TRANSFERENCIAS CASH SUELDOS",
)


class ExtractoInvalido(ValueError):
    """El archivo no es un extracto de Galicia que se pueda leer. El texto va a Franco."""


@dataclass(frozen=True)
class FilaBanco:
    fecha: date
    #: En centavos: negativo = débito (salió plata), positivo = crédito.
    monto: int
    #: Saldo parcial después del movimiento, en centavos.
    saldo: int
    #: Primera línea de "Movimiento", normalizada (mayúsculas, sin acentos,
    #: sin el número de ticket): ``COMPRA DEBITO``, ``DEP.EFVO.AUTOSERVICIO TICKET:``.
    tipo: str
    #: Segunda línea, solo para los tipos donde es el comercio o la persona.
    comercio: Optional[str] = None
    #: Pesos por dólar, si la fila es una compra o venta de dólares.
    cotizacion: Optional[float] = None

    @property
    def saldo_antes(self) -> int:
        return self.saldo - self.monto


@dataclass(frozen=True)
class Extracto:
    #: De la más vieja a la más nueva (al revés que el archivo).
    filas: tuple[FilaBanco, ...]

    @property
    def desde(self) -> date:
        return self.filas[0].fecha

    @property
    def hasta(self) -> date:
        return self.filas[-1].fecha

    @property
    def saldo_final(self) -> int:
        return self.filas[-1].saldo


def normalizar_tipo(primera_linea: str) -> str:
    """``'Compra venta de dolares'`` → ``'COMPRA VENTA DE DOLARES'``;
    ``'DEP.EFVO.AUTOSERVICIO TICKET:  109477'`` → ``'DEP.EFVO.AUTOSERVICIO TICKET:'``;
    ``'PERCEPCION RG 5617/24'`` queda igual (el número no está suelto)."""
    s = "".join(c for c in unicodedata.normalize("NFKD", primera_linea)
                if not unicodedata.combining(c))
    s = re.sub(r"\s+\d+$", "", s.upper().strip())   # el número de ticket del final
    return " ".join(s.split())


def centavos(texto: object, *, que: str, fila: int) -> int:
    """``'-200.000,00'`` → -20000000 · ``'153263,01'`` → 15326301. Estricto."""
    s = str(texto if texto is not None else "").strip()
    m = _RE_MONTO.match(s)
    if not m:
        raise ExtractoInvalido(f"No entiendo el {que} de la fila {fila}: «{s}».")
    signo, entero, dec = m.groups()
    # El saldo a veces viene con un solo decimal ("709269,8" = 709.269,80).
    valor = int(entero.replace(".", "")) * 100 + int((dec or "0").ljust(2, "0"))
    return -valor if signo else valor


def _fecha(texto: object) -> Optional[date]:
    m = _RE_FECHA.match(str(texto or "").strip())
    if not m:
        return None
    d, mes, a = (int(x) for x in m.groups())
    try:
        return date(a, mes, d)
    except ValueError:
        return None


def _comercio(tipo: str, lineas: list[str]) -> Optional[str]:
    """La primera línea de texto después del tipo: el comercio o la persona.

    Se saltean las que son casi todas números (CUIT, CBU, tarjeta, operación)
    y el concepto ``VARIOS``. En las transferencias el nombre a veces viene
    en la segunda línea y a veces después del CUIT y el CBU.
    """
    if not tipo.startswith(_TIPOS_CON_COMERCIO):
        return None
    for linea in lineas[1:]:
        c = " ".join(linea.split())
        if c and c.upper() != "VARIOS" and sum(ch.isdigit() for ch in c) <= len(c) / 2:
            return c
    return None


def _cotizacion(lineas: list[str]) -> Optional[float]:
    for linea in lineas:
        if m := _RE_COTIZACION.search(linea):
            try:
                return float(m.group(1))
            except ValueError:
                return None
    return None


def leer_extracto(datos: bytes) -> Extracto:
    """Lee el `.xlsx` y verifica la cadena de saldos. `ExtractoInvalido` si algo no cierra."""
    try:
        with warnings.catch_warnings():
            # El Excel de Galicia no trae estilos: openpyxl avisa y usa los suyos.
            warnings.filterwarnings("ignore", message="Workbook contains no default style")
            libro = openpyxl.load_workbook(io.BytesIO(datos), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError, InvalidFileException) as e:
        raise ExtractoInvalido(f"No pude abrir el Excel ({type(e).__name__}).") from None
    try:
        hoja = libro.worksheets[0]
        filas_crudas = list(hoja.iter_rows(values_only=True))
    finally:
        libro.close()

    filas: list[FilaBanco] = []  # en el orden del archivo: lo más nuevo primero
    for n, r in enumerate(filas_crudas, 1):
        r = tuple(r) + (None,) * (6 - len(r))
        f = _fecha(r[COL_FECHA])
        if f is None:
            if filas:
                # Después de los datos solo puede haber filas vacías.
                if any(c not in (None, "") for c in r):
                    raise ExtractoInvalido(f"La fila {n} no tiene fecha y está entre los datos.")
            continue
        lineas = [l.strip() for l in str(r[COL_MOVIMIENTO] or "").splitlines() if l.strip()]
        if not lineas:
            raise ExtractoInvalido(f"La fila {n} no dice qué movimiento es.")
        tipo = normalizar_tipo(lineas[0])
        debito = centavos(r[COL_DEBITO], que="débito", fila=n)
        credito = centavos(r[COL_CREDITO], que="crédito", fila=n)
        if debito and credito:
            raise ExtractoInvalido(f"La fila {n} tiene débito y crédito a la vez.")
        filas.append(FilaBanco(
            fecha=f,
            monto=credito if credito else -abs(debito),
            saldo=centavos(r[COL_SALDO], que="saldo", fila=n),
            tipo=tipo,
            comercio=_comercio(tipo, lineas),
            cotizacion=_cotizacion(lineas) if tipo.startswith("COMPRA VENTA DE DOLARES") else None,
        ))
    if not filas:
        raise ExtractoInvalido("No encontré movimientos: ¿es el extracto de la caja de ahorro "
                               "de Galicia?")

    filas.reverse()  # de la más vieja a la más nueva
    for anterior, fila in zip(filas, filas[1:]):
        if fila.fecha < anterior.fecha:
            raise ExtractoInvalido("Las fechas del extracto no están en orden.")
        if fila.saldo_antes != anterior.saldo:
            raise ExtractoInvalido(
                f"La cadena de saldos se corta el {fila.fecha:%d/%m/%Y}: el saldo anterior "
                f"era {anterior.saldo / 100:.2f} y este movimiento arranca de "
                f"{fila.saldo_antes / 100:.2f}. ¿El archivo está completo?")
    return Extracto(tuple(filas))
