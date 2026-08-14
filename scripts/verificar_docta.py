"""¿Docta Capital tiene los bonos de Franco? — chequeo antes de construir.

**Por qué existe.** Antes de cablear una fuente externa a la app hay que saber
si cubre los instrumentos reales. La sospecha concreta: el pagaré
`#UMV060770008` es del **MAV** y el catálogo de Docta declara soberanos,
sub-soberanos y ONs — probablemente no esté. Mejor saberlo ahora que después
de escribir el módulo entero encima de un supuesto.

**Cuota.** Gasta **1 request por instrumento** (más 1 del token, que no
consume cuota de datos). El plan gratuito da 15 por día: alcanza de sobra.

**No escribe nada.** Solo consulta y muestra. No toca la base ni la app.

Uso, desde la raíz del repo y con el `.env` cargado:

    .venv\\Scripts\\python.exe scripts\\verificar_docta.py
    .venv\\Scripts\\python.exe scripts\\verificar_docta.py AE38 AN29 RUCDO
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

#: Lo que Franco tiene o tuvo en renta fija. El pagaré va a propósito: es el
#: caso que se quiere confirmar, no el que se espera que funcione.
POR_DEFECTO = ["AE38", "AN29", "RUCDO", "#UMV060770008"]


def _cargar_env() -> None:
    """Lee el `.env` de la raíz. Sin dependencias: el archivo es trivial."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, _, valor = limpia.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def main(argv: list[str]) -> int:
    _cargar_env()
    from core.market_data import cronogramas as cr

    tickers = argv[1:] or POR_DEFECTO

    if not cr.hay_credenciales():
        print("FALTAN CREDENCIALES.")
        print("  Poné DOCTA_CLIENT_ID y DOCTA_CLIENT_SECRET en el archivo")
        print("  `.env` de la raíz (NO en .env.example, que se commitea).")
        return 1

    print("Pidiendo token ...", end=" ", flush=True)
    if cr.obtener_token() is None:
        print("FALLO.")
        print("  El token no se pudo obtener. Revisá que el client_id y el")
        print("  client_secret sean los de https://app.docta.com.ar/dashboard/account/api")
        return 1
    print("ok")
    print()

    print(f"{'TICKER':<16}{'EN EL CATALOGO':<18}{'FLUJOS':>7}  {'PROXIMO PAGO':<14}CLASE")
    print("-" * 74)

    cubiertos, faltantes = [], []
    for t in tickers:
        simbolo = cr.buscar_simbolo(t)
        if simbolo is None:
            estado = "NO" if not t.startswith("#") else "NO (es del MAV)"
            print(f"{t:<16}{estado:<18}{'—':>7}  {'—':<14}—")
            faltantes.append(t)
            continue

        cron = cr.traer_cronograma(simbolo)
        if cron is None or not cron.flujos:
            print(f"{t:<16}{'si, sin flujos':<18}{'0':>7}  {'—':<14}—")
            faltantes.append(t)
            continue

        prox = cron.proximo_pago()
        cuando = prox.fecha.strftime("%d/%m/%Y") if prox else "ya vencido"
        print(f"{t:<16}{'SI':<18}{len(cron.flujos):>7}  {cuando:<14}"
              f"{cron.clase or '—'}")
        cubiertos.append(t)

    print()
    print(f"Cubiertos: {len(cubiertos)}/{len(tickers)}"
          + (f"  ({', '.join(cubiertos)})" if cubiertos else ""))
    if faltantes:
        print(f"Sin datos: {', '.join(faltantes)}")
        print()
        print("  Lo que NO cubra la fuente se carga a mano. El mecanismo de")
        print("  carga manual hay que construirlo igual como respaldo, por si")
        print("  el proveedor cambia o desaparece.")

    # Detalle del primer bono cubierto: sirve para ver la forma real de los
    # datos antes de escribir el parser definitivo.
    if cubiertos:
        t = cubiertos[0]
        cron = cr.traer_cronograma(t)
        print()
        print(f"=== Primeros pagos futuros de {t} (por 100 nominales) ===")
        for f in (cron.proximos() if cron else [])[:6]:
            print(f"  {f.fecha}  capital {f.capital:>10,.4f}   "
                  f"interes {f.interes:>10,.4f}   total {f.total:>10,.4f}"
                  + (f"   residual {f.residual:>8,.2f}"
                     if f.residual is not None else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
