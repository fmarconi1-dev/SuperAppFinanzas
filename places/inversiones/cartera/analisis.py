"""Composición de la cartera: por tipo de renta y por sector (Fase 3b, punto 4).

Responde "¿cómo está repartida mi plata?" en tres cortes, cada uno aplicado a
lo que **sí** le corresponde:

* **Tipo de renta** — renta variable, renta fija, cripto, efectivo. Sale de
  ``categoria_activo`` (la hoja `Config` del Excel), así que cubre el **100%**
  de la cartera. Es el corte principal.
* **Sector**, solo sobre la **renta variable** — lo resuelve Yahoo por ticker y
  se cachea en la DB. No se inventa el sector de nada: a un ETF de oro o a un
  bono soberano no se le puede asignar uno sin mentir.
* **Emisor**, solo sobre la **renta fija** — soberano, subsoberano o
  corporativo, más el país. Preguntarle el "sector" a un bono no tiene sentido;
  lo que define su riesgo es **quién te debe la plata**.

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
    "TIPOS_DE_EMISOR", "tipo_de_renta", "tipo_de_emisor", "pais_del_emisor",
    "por_tipo_de_renta", "por_sector", "por_emisor", "por_pais",
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
    """Sector económico de la **renta variable**, resuelto por Yahoo.

    Solo entran acciones y CEDEARs: a un bono soberano, a un pagaré, al
    efectivo o al bitcoin **no se les puede asignar un sector** — no es que
    falte el dato, es que no existe. Meterlos empujaría todo a un "Sin dato"
    del 75% que no dice nada. Con este recorte, el porcentaje se lee como
    *"de mi renta variable, cuánto tengo en cada sector"*.

    Dentro de la renta variable, lo que Yahoo no cubre **sí** queda en
    "Sin dato": los ETFs (son una canasta; asignarles un sector sería
    inventarlo) y cualquier papel que Yahoo no reconozca.
    """
    variables = [
        p for p in valuadas
        if tipo_de_renta(getattr(p, "categoria_activo", ""), p.ticker)
        == "Renta variable"
    ]
    return _agrupar(variables, lambda p: sectores.get(p.ticker) or SIN_DATO)


# ---------------------------------------------------------------------------
# Renta fija: quién te debe la plata
# ---------------------------------------------------------------------------
#
# `sectores_desde_snapshot()` vivía acá y leía el snapshot del scoring como
# primera fuente del sector. Se retiró el 5/8/2026 junto con el módulo de
# Scoring (decisión de Franco). Los sectores se resuelven **100% con Yahoo**.

#: Etiquetas del emisor. El orden es el del riesgo percibido, no alfabético.
TIPOS_DE_EMISOR = ("Soberano", "Subsoberano", "Corporativo")

#: Letras y bonos del Tesoro Nacional. Se reconocen por la categoría del Excel
#: (`Bonos`, `Letras`) — el emisor no está como dato en ningún lado, así que se
#: deriva de lo que sí hay.
_CAT_SOBERANO = ("bonos", "letras")
#: Obligaciones negociables = deuda de una empresa. Los pagarés y cheques
#: avalados también: el que paga es una empresa, no el Estado.
_CAT_CORPORATIVO = ("ons", "pagares", "cheques")

#: Provincias y municipios. Sus tickers tienen prefijos reconocibles (PBA =
#: Buenos Aires, CO = Córdoba, BA37/BB37/BC37 = canjes provinciales).
_PREFIJOS_SUBSOBERANO = ("PBA", "PBY", "BDC", "CO2", "BA3", "BB3", "BC3")


def tipo_de_emisor(categoria_activo, ticker: str = "") -> str:
    """Soberano / Subsoberano / Corporativo para un instrumento de renta fija.

    **Por qué existe.** A un bono no se le puede preguntar el sector — no tiene
    uno. Lo que define su riesgo es **quién te debe la plata**: no es lo mismo
    un título del Tesoro que una ON de una petrolera.

    Se deriva de la categoría del Excel y del ticker, porque el emisor **no
    está como dato** en ninguna fuente que tengamos. Lo que no se puede
    determinar queda en `Sin dato`: es un corte para leer riesgo, y una
    etiqueta inventada ahí sería peor que la ausencia.
    """
    t = str(ticker or "").strip().upper()
    if t.startswith("#"):
        return "Corporativo"          # pagaré/cheque avalado: paga una empresa
    cat = _norm(categoria_activo)
    if cat in _CAT_CORPORATIVO:
        return "Corporativo"
    if cat in _CAT_SOBERANO:
        if any(t.startswith(p) for p in _PREFIJOS_SUBSOBERANO):
            return "Subsoberano"
        return "Soberano"
    return SIN_DATO


def pais_del_emisor(categoria_activo, ticker: str = "") -> str:
    """País del emisor de un instrumento de renta fija.

    Hoy devuelve **Argentina** para todo lo que sea renta fija: todos los
    instrumentos de Franco son locales. Existe como función aparte —y no como
    una constante— para que el día que compre deuda de afuera el cambio sea
    acá adentro y no repartido por la vista.
    """
    if tipo_de_renta(categoria_activo, ticker) != "Renta fija":
        return SIN_DATO
    return "Argentina"


def por_emisor(valuadas) -> list[Grupo]:
    """Renta fija por tipo de emisor. Solo entra la renta fija."""
    fija = [
        p for p in valuadas
        if tipo_de_renta(getattr(p, "categoria_activo", ""), p.ticker)
        == "Renta fija"
    ]
    return _agrupar(
        fija,
        lambda p: tipo_de_emisor(getattr(p, "categoria_activo", ""), p.ticker),
    )


def por_pais(valuadas) -> list[Grupo]:
    """Renta fija por país del emisor. Solo entra la renta fija."""
    fija = [
        p for p in valuadas
        if tipo_de_renta(getattr(p, "categoria_activo", ""), p.ticker)
        == "Renta fija"
    ]
    return _agrupar(
        fija,
        lambda p: pais_del_emisor(getattr(p, "categoria_activo", ""), p.ticker),
    )
