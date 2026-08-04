"""Composición de la cartera: por tipo de renta y por sector (Fase 3b, punto 4).

Responde "¿cómo está repartida mi plata?" en dos cortes:

* **Tipo de renta** — renta variable, renta fija, cripto, efectivo. Sale de
  ``categoria_activo`` (la hoja `Config` del Excel), así que cubre el **100%**
  de la cartera. Es el corte principal.
* **Sector** — sale del snapshot del scoring, que hoy trae 100 empresas con su
  sector. Cubre **13 de las 22** posiciones de Franco; el resto (bonos, ETFs,
  cripto, el pagaré y las acciones argentinas fuera del universo) queda como
  **"Sin dato"**, explícito. No se inventa el sector de nada: a un ETF de oro o
  a un bono soberano no se le puede asignar uno sin mentir.

**Dos decisiones que evitan repetir errores viejos:**

1. **El porcentaje se calcula sobre el patrimonio, con el efectivo adentro.**
   Si se calculara solo sobre las posiciones, un 30% en caja desaparecería del
   gráfico y todo lo demás se vería más grande de lo que es.
2. **Se agrega el resultado NO realizado, no el total.** Sumar el resultado
   total por grupo repetiría la trampa de la Fase 3a: al pasar importes en
   dólares a pesos con el TC de cada fecha, la devaluación infla los subtotales
   (se verificó: $9,92M por componentes contra $2,27M por patrimonio).
   ``valor − costo`` vive entero en el plano de pesos de hoy y sí se puede
   sumar.

Módulo puro: recibe posiciones ya valuadas y devuelve grupos.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Grupo", "TIPOS_DE_RENTA", "SIN_DATO", "EFECTIVO",
    "tipo_de_renta", "por_tipo_de_renta", "por_sector",
    "sectores_desde_snapshot",
]

#: Etiqueta única para lo que no tiene el dato. Se muestra tal cual: es
#: información ("no sé"), no un cajón de sastre donde esconder cosas.
SIN_DATO = "Sin dato"
EFECTIVO = "Efectivo"

#: `categoria_activo` (hoja Config) → tipo de renta. La clave se normaliza
#: sin tildes y en minúsculas, así que "Pagarés" y "Pagares" caen igual.
TIPOS_DE_RENTA = {
    "acciones": "Renta variable",
    "cedears": "Renta variable",
    "bonos": "Renta fija",
    "letras": "Renta fija",
    "ons": "Renta fija",
    "pagares": "Renta fija",
    "cripto": "Cripto",
    "efectivo": EFECTIVO,
}


@dataclass
class Grupo:
    """Un tajo de la cartera con su peso y su resultado no realizado."""

    nombre: str
    n: int = 0                       # posiciones
    valor_ars: float = 0.0
    costo_ars: float = 0.0
    #: Posiciones del grupo que no se pudieron valuar: su costo tampoco entra,
    #: para no comparar un valor parcial contra un costo completo.
    sin_precio: int = 0
    pct: float = 0.0                 # sobre el patrimonio, efectivo incluido

    @property
    def resultado_ars(self) -> float:
        """No realizado: lo que vale hoy menos lo que costó."""
        return self.valor_ars - self.costo_ars

    @property
    def rendimiento_pct(self) -> float | None:
        if not self.costo_ars:
            return None
        return self.resultado_ars / self.costo_ars * 100.0

    def valor_usd(self, mep: float | None) -> float | None:
        if not mep:
            return None
        return self.valor_ars / mep


def _norm(texto) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip().lower()


def tipo_de_renta(categoria_activo, ticker: str = "") -> str:
    """Traduce la categoría del Excel a tipo de renta. Sin match → Sin dato.

    **Los pagarés y cheques se reconocen por el ticker.** Su ticker empieza con
    ``#`` y **nunca** están en la hoja `Config` (el Excel nunca los tuvo), así
    que llegan acá con categoría "Otros". Son renta fija por definición: se
    compran a descuento sobre el nominal y su precio converge al nominal. Sin
    esta regla, el pagaré de Franco —**el 34% de su cartera**— quedaba en
    "Sin dato".
    """
    if str(ticker or "").startswith("#"):
        return "Renta fija"
    return TIPOS_DE_RENTA.get(_norm(categoria_activo), SIN_DATO)


def _agrupar(valuadas, clave, efectivo_ars: float = 0.0) -> list[Grupo]:
    """Núcleo: agrupa por `clave(posicion_valuada)` y calcula los pesos.

    El efectivo entra como un grupo más para que los porcentajes se midan
    contra el patrimonio y sumen 100%.
    """
    grupos: dict[str, Grupo] = {}

    def _g(nombre: str) -> Grupo:
        g = grupos.get(nombre)
        if g is None:
            g = grupos[nombre] = Grupo(nombre)
        return g

    for p in valuadas:
        if getattr(p, "cerrada", False):
            continue          # sin tenencia: no ocupa lugar en la cartera
        g = _g(clave(p))
        g.n += 1
        if p.valor_ars is None:
            g.sin_precio += 1
            continue
        g.valor_ars += p.valor_ars
        g.costo_ars += p.costo_ars

    if efectivo_ars:
        g = _g(EFECTIVO)
        g.n += 1
        g.valor_ars += efectivo_ars
        g.costo_ars += efectivo_ars      # la caja no tiene resultado propio

    total = sum(g.valor_ars for g in grupos.values())
    for g in grupos.values():
        g.pct = (g.valor_ars / total * 100.0) if total else 0.0

    # De mayor a menor peso; "Sin dato" siempre al final, aunque pese mucho:
    # es una etiqueta de ignorancia, no una categoría que compita con las otras.
    return sorted(grupos.values(),
                  key=lambda g: (g.nombre == SIN_DATO, -g.valor_ars))


def por_tipo_de_renta(valuadas, efectivo_ars: float = 0.0) -> list[Grupo]:
    """Renta variable / fija / cripto / efectivo. Cobertura total."""
    return _agrupar(
        valuadas,
        lambda p: tipo_de_renta(getattr(p, "categoria_activo", ""), p.ticker),
        efectivo_ars,
    )


def por_sector(valuadas, sectores: dict) -> list[Grupo]:
    """Sector económico de la **renta variable**, según el snapshot del scoring.

    Solo entran acciones y CEDEARs: a un bono soberano, a un pagaré, al
    efectivo o al bitcoin **no se les puede asignar un sector** — no es que
    falte el dato, es que no existe. Meterlos empujaría todo a un "Sin dato"
    del 75% que no dice nada. Con este recorte, el porcentaje se lee como
    *"de mi renta variable, cuánto tengo en cada sector"*.

    Dentro de la renta variable, lo que el snapshot no cubre **sí** queda en
    "Sin dato": los ETFs (son una canasta; asignarles un sector sería
    inventarlo) y las acciones fuera del universo del scoring.
    """
    variables = [
        p for p in valuadas
        if tipo_de_renta(getattr(p, "categoria_activo", ""), p.ticker)
        == "Renta variable"
    ]
    return _agrupar(variables, lambda p: sectores.get(p.ticker) or SIN_DATO)


def sectores_desde_snapshot(snapshot) -> dict[str, str]:
    """``{ticker: sector}`` del snapshot del scoring. Tolera un snapshot vacío
    o caído: sin datos devuelve ``{}`` y todo queda en "Sin dato"."""
    if not isinstance(snapshot, dict):
        return {}
    out: dict[str, str] = {}
    for e in snapshot.get("empresas") or []:
        ticker, sector = e.get("ticker"), e.get("sector")
        if ticker and sector:
            out[str(ticker).strip().upper()] = str(sector).strip()
    return out
