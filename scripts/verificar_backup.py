"""Verifica que una copia de la base sirva de verdad.

**Por qué es un archivo y no un `python -c` dentro del .ps1.** Lo estaba, y
falló en la primera corrida real: PowerShell se come las comillas al pasar un
script multilínea como argumento, así que Python recibía
``ok = c.execute(PRAGMA`` y moría con un `SyntaxError`. Con el script en un
archivo no hay comillas que romper — y además se puede testear.

Uso:
    python scripts/verificar_backup.py <ruta.db>

Imprime ``integridad|transacciones|cartera_movimientos|usuarios`` y termina con
código **0** si la copia sirve, **1** si no. Los scripts de PowerShell miran el
código de salida; el detalle impreso es para el humano.

Qué se considera "sirve":

* pasa ``PRAGMA integrity_check``;
* tiene al menos un usuario (si no, no es una base de esta app);
* tiene al menos una transacción — **eso es lo irreemplazable**: la cartera se
  reconstruye del Excel, los gastos personales no existen en ningún otro lado.

La cartera vacía **no** invalida la copia: puede ser una base anterior al
primer import.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def _contar(con: sqlite3.Connection, tabla: str) -> int:
    """Filas de `tabla`, o −1 si la tabla no existe en esta copia."""
    try:
        return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
    except sqlite3.Error:
        return -1


def verificar(ruta) -> tuple[bool, str, dict]:
    """``(sirve, integridad, {tabla: filas})``. No lanza: devuelve el motivo."""
    ruta = Path(ruta)
    if not ruta.exists():
        return False, "no existe", {}
    if ruta.stat().st_size < 1024:
        return False, "vacio", {}
    try:
        con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return False, f"no abre ({exc})", {}
    try:
        integridad = con.execute("PRAGMA integrity_check").fetchone()[0]
        conteos = {
            "transacciones": _contar(con, "transacciones"),
            "cartera_movimientos": _contar(con, "cartera_movimientos"),
            "usuarios": _contar(con, "usuarios"),
        }
    except sqlite3.Error as exc:
        return False, f"ilegible ({exc})", {}
    finally:
        con.close()

    sirve = (
        integridad == "ok"
        and conteos["usuarios"] >= 1
        and conteos["transacciones"] >= 1
    )
    return sirve, integridad, conteos


def main(argv) -> int:
    if len(argv) != 2:
        print("uso: python scripts/verificar_backup.py <ruta.db>",
              file=sys.stderr)
        return 2
    sirve, integridad, c = verificar(argv[1])
    print("|".join([
        integridad,
        str(c.get("transacciones", -1)),
        str(c.get("cartera_movimientos", -1)),
        str(c.get("usuarios", -1)),
    ]))
    if not sirve:
        print(f"La copia NO sirve: integridad={integridad}, "
              f"usuarios={c.get('usuarios', -1)}, "
              f"transacciones={c.get('transacciones', -1)}", file=sys.stderr)
    return 0 if sirve else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
