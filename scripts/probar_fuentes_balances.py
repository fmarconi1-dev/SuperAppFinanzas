"""¿Las fuentes de los balances contestan desde acá? (ADR-0011). No escribe nada.

Pensado para correrlo **dentro de la máquina de Fly**, porque las fuentes
pueden rechazar pedidos de servidores aunque desde la PC anden:

    fly ssh console -a superapp-finanzas -C "python /app/scripts/probar_fuentes_balances.py"

Prueba, una por una: el calendario de Nasdaq (el próximo día hábil), la ficha
de Nasdaq de MSFT, la lista del S&P 500 de Wikipedia, y en Yahoo los cierres
de KO y el posmercado de KO del día hábil anterior. Cada una dice OK o FALLA
con el motivo. (Verificado desde la PC el 21/10/2026: NFLX cerró el 20/10 en
68,69 y terminó el posmercado en 64,72.)
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.api import balances_fuentes as bf  # noqa: E402

FALLAS = (bf.CalendarioNoDisponible, bf.ListaNoDisponible, bf.PrecioNoDisponible)


def _habil(desde: date, paso: int) -> date:
    dia = desde + timedelta(days=paso)
    while dia.weekday() >= 5:
        dia += timedelta(days=paso)
    return dia


def pruebas(hoy: date) -> list[tuple[str, object]]:
    dia, anterior = _habil(hoy, 1), _habil(hoy, -1)
    return [
        (f"Nasdaq, calendario del {dia:%d/%m}",
         lambda: f"{len(bf.calendario_del_dia(dia))} empresas"),
        ("Nasdaq, ficha de MSFT", lambda: bf.fecha_anunciada("MSFT")),
        ("Wikipedia, S&P 500", lambda: f"{len(bf.lista_sp500())} tickers"),
        ("Yahoo, cierres de KO",
         lambda: {f"{d:%d/%m}": round(v, 2) for d, v in sorted(bf.cierres("KO").items())[-2:]}),
        (f"Yahoo, posmercado de KO del {anterior:%d/%m}",
         lambda: round(bf.ultimo_del_posmercado("KO", anterior), 3)),
    ]


def main(hoy: date | None = None) -> int:
    fallas = 0
    for nombre, prueba in pruebas(hoy or date.today()):
        try:
            print(f"OK     {nombre}: {prueba()}")
        except FALLAS as e:
            fallas += 1
            print(f"FALLA  {nombre}: {e}")
    print("Todas contestaron." if not fallas else f"{fallas} fuente(s) no contestaron.")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
