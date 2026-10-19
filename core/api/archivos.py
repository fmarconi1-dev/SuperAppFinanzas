"""Archivos que Franco le manda al Secretario (Fase D, paso 3, ADR-0009 §7).

El extracto de la caja (Excel), el resumen de una tarjeta (PDF) o una foto.
Acá solo se decide **qué es** el archivo, mirando su contenido y no el
nombre ni lo que dice Meta: un `.xlsx` renombrado a `.pdf`, o una foto
mandada como documento, se reconocen igual. Leerlo es de `places/` (llega
inyectado, como los comandos de texto).

**El archivo nunca toca el disco.** Se baja a memoria, se lee y se suelta: no
queda nada que borrar después, ni en el volumen de Fly ni en `/tmp`, aunque el
proceso se caiga a mitad.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from typing import Optional

#: Lo que se acepta, con el nombre con que se le habla a Franco.
TIPOS = {
    "xlsx": "un Excel",
    "pdf": "un PDF",
    "jpeg": "una foto",
    "png": "una foto",
    "webp": "una foto",
}


@dataclass(frozen=True)
class ArchivoRecibido:
    """Un archivo ya bajado y reconocido. `datos` vive solo en memoria."""

    tipo: str  # una clave de TIPOS
    datos: bytes
    nombre: Optional[str] = None
    #: El texto que Franco escribió debajo del archivo, si escribió algo.
    pie: Optional[str] = None

    @property
    def es_foto(self) -> bool:
        return self.tipo in {"jpeg", "png", "webp"}

    def describir(self) -> str:
        """«un Excel (galicia.xlsx, 45 KB)»: para contestarle a Franco qué llegó."""
        detalle = ", ".join(p for p in (self.nombre, tamanio_legible(len(self.datos))) if p)
        return f"{TIPOS[self.tipo]} ({detalle})"


def tamanio_legible(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / (1024 * 1024):.1f} MB".replace(".", ",")


def tipo_de_contenido(datos: bytes) -> Optional[str]:
    """La clave de `TIPOS` según los primeros bytes, o None si no es nada conocido.

    Un `.xlsx` es un zip: se acepta solo si adentro está el libro de Excel
    (`xl/workbook.xml`). Un zip cualquiera, o un `.xls` viejo, no.
    """
    if datos.startswith(b"%PDF-"):
        return "pdf"
    if datos.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "webp"
    if datos.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                if "xl/workbook.xml" in z.namelist():
                    return "xlsx"
        except zipfile.BadZipFile:
            return None
    return None
