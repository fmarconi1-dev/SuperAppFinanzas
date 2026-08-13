"""Sector e industria por ticker, resueltos automáticamente.

**Qué problema resuelve.** El corte por sector cubría 13 de las 22 posiciones
porque dependía del snapshot del scoring. Franco pidió que *"la app sea capaz
de reconocer por sí sola los sectores de las empresas"*.

**Fuente: Yahoo `v1/finance/search`.** Devuelve `sector` e `industry` para
acciones sin necesidad de autenticación (a diferencia de `quoteSummary`, que
exige un *crumb* con cookie y es frágil). Para las acciones argentinas se
prueba también el sufijo ``.BA`` — así ``TGNO4`` resuelve por ``TGNO4.BA``.

**Los ETF no tienen sector, y está bien.** Yahoo los marca ``quoteType: ETF``
con ``sector: null`` porque un ETF *es* una canasta. En vez de dejarlos en
"Sin dato", se les arma una etiqueta a partir del nombre del fondo:
``SPDR Gold Shares`` → **"ETF · Oro"**. Si el subyacente no se reconoce, se cae
al nombre del fondo — nunca se inventa un sector.

**Resguardos (los mismos que exige el repo para cualquier fuente externa):**

* **Caché en DB** (`cartera_sectores`, M12): se resuelve una vez por ticker.
  Si Yahoo se cae, la cartera se muestra igual con lo cacheado.
* **Override manual** (`es_override = 1`): gana sobre cualquier proveedor.
  Cuando el criterio de Franco no coincida con el estándar, manda él.
* **`fetch` inyectable**: los tests corren sin red.
* **Nunca lanza**: si la búsqueda falla, devuelve `None` y el ticker queda en
  "Sin dato". La composición de la cartera no puede romperse por esto.

Decisión tomada con Franco (2026-07-30): ante discrepancia entre Yahoo y su
criterio, **manda Yahoo** — así la cartera queda comparable contra cualquier
referencia que use el estándar GICS. El override queda disponible igual.
Caso testigo: TGNO4 es *Energy / Oil & Gas Midstream* para Yahoo, aunque en
Argentina se lo piense como una utility regulada.
"""

from __future__ import annotations

import json
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass

__all__ = [
    "URL_BUSQUEDA", "ETIQUETAS_ETF", "FichaTicker",
    "buscar_ficha", "etiqueta_etf", "resolver_ficha",
    "leer_sectores_cache", "guardar_ficha_en_cache", "set_override_sector",
    "refrescar_sectores", "sectores_para",
]

URL_BUSQUEDA = (
    "https://query2.finance.yahoo.com/v1/finance/search"
    "?q={q}&quotesCount=6&newsCount=0"
)

#: Subyacente del ETF → etiqueta corta en español. Se busca por palabra clave
#: en el nombre del fondo, de la más específica a la más general. Es un mapa de
#: conveniencia para leer el cuadro de un vistazo: lo que no matchea cae al
#: nombre del fondo, no a una etiqueta inventada.
ETIQUETAS_ETF = (
    ("gold", "Oro"),
    ("silver", "Plata"),
    ("uranium", "Uranio"),
    ("copper", "Cobre"),
    ("lithium", "Litio"),
    ("oil", "Petróleo"),
    ("natural gas", "Gas"),
    ("s&p 500", "S&P 500"),
    ("nasdaq", "Nasdaq"),
    ("dow jones", "Dow Jones"),
    ("russell", "Russell"),
    ("emerging markets", "Emergentes"),
    ("europe", "Europa"),
    ("china", "China"),
    ("japan", "Japón"),
    ("real estate", "Inmobiliario"),
    ("semiconductor", "Semiconductores"),
    ("biotech", "Biotecnología"),
    ("dividend", "Dividendos"),
    ("bond", "Bonos"),
    ("treasury", "Treasuries"),
    ("bitcoin", "Bitcoin"),
)

_PREFIJO_ETF = "ETF · "


@dataclass(frozen=True)
class FichaTicker:
    """Lo que se sabe de un ticker: qué es, de qué sector y de qué industria."""

    ticker: str
    sector: str | None = None
    industria: str | None = None
    tipo: str | None = None          # "EQUITY" | "ETF" | …
    nombre: str | None = None
    fuente: str | None = None        # "yahoo" | "scoring" | "override" | None

    @property
    def es_etf(self) -> bool:
        return (self.tipo or "").upper() == "ETF"


def _fetch_http(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (SuperAppFinanzas)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def _norm(texto) -> str:
    s = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def etiqueta_etf(nombre: str | None) -> str:
    """``"SPDR Gold Shares"`` → ``"ETF · Oro"``.

    Si el subyacente no está en el mapa, devuelve ``"ETF · <nombre del
    fondo>"``: sigue siendo información honesta, solo menos compacta.
    """
    n = _norm(nombre)
    for clave, etiqueta in ETIQUETAS_ETF:
        if clave in n:
            return _PREFIJO_ETF + etiqueta
    limpio = str(nombre or "").strip()
    return _PREFIJO_ETF + limpio if limpio else _PREFIJO_ETF.strip(" ·")


def buscar_ficha(simbolo: str, fetch=None) -> FichaTicker | None:
    """Busca `simbolo` en Yahoo y devuelve su ficha, o ``None``.

    Solo acepta la coincidencia **exacta** de símbolo: la búsqueda devuelve
    parecidos (buscando ``URA`` aparece también ``UROY``) y quedarse con el
    primero le pondría a un ETF de uranio el sector de una minera.
    """
    try:
        crudo = (fetch or _fetch_http)(
            URL_BUSQUEDA.format(q=urllib.parse.quote(simbolo)))
        datos = json.loads(crudo) if isinstance(crudo, str) else crudo
        for q in datos.get("quotes") or []:
            if str(q.get("symbol", "")).upper() != simbolo.upper():
                continue
            return FichaTicker(
                ticker=simbolo.upper(),
                sector=q.get("sector") or None,
                industria=q.get("industry") or None,
                tipo=q.get("quoteType") or None,
                nombre=q.get("longname") or q.get("shortname") or None,
                fuente="yahoo",
            )
    except Exception:
        return None
    return None


def resolver_ficha(ticker: str, fetch=None) -> FichaTicker | None:
    """Resuelve un ticker probando el símbolo tal cual y con sufijo ``.BA``.

    Los CEDEARs comparten el ticker con el papel del exterior (``NVDA``,
    ``GLD``), así que resuelven directo. Las acciones argentinas necesitan el
    sufijo del mercado local: ``TGNO4`` → ``TGNO4.BA``.

    A los ETF, que no traen sector, se les arma la etiqueta desde el nombre.
    """
    base = (ticker or "").strip().upper()
    if not base or base.startswith("#"):
        return None            # pagarés y cheques: no son una empresa
    for simbolo in (base, f"{base}.BA"):
        ficha = buscar_ficha(simbolo, fetch)
        if ficha is None:
            continue
        if ficha.es_etf and not ficha.sector:
            ficha = FichaTicker(
                ticker=base, sector=etiqueta_etf(ficha.nombre),
                industria=ficha.industria, tipo=ficha.tipo,
                nombre=ficha.nombre, fuente="yahoo",
            )
        if ficha.sector:
            return FichaTicker(
                ticker=base, sector=ficha.sector, industria=ficha.industria,
                tipo=ficha.tipo, nombre=ficha.nombre, fuente="yahoo",
            )
    return None


# ---------------------------------------------------------------------------
# Caché en DB (M12) y override
# ---------------------------------------------------------------------------

def leer_sectores_cache(conn) -> dict[str, FichaTicker]:
    """Todo lo cacheado, ``{ticker: FichaTicker}``. Incluye los overrides."""
    return {
        r["ticker"]: FichaTicker(
            ticker=r["ticker"], sector=r["sector"], industria=r["industria"],
            tipo=r["tipo"], nombre=r["nombre"],
            fuente="override" if r["es_override"] else r["fuente"],
        )
        for r in conn.execute(
            "SELECT ticker, sector, industria, tipo, nombre, fuente, "
            "       es_override FROM cartera_sectores")
    }


def guardar_ficha_en_cache(conn, ficha: FichaTicker) -> None:
    """Guarda o actualiza una ficha. **Nunca pisa un override manual.**"""
    conn.execute(
        "INSERT INTO cartera_sectores "
        "  (ticker, sector, industria, tipo, nombre, fuente, es_override) "
        "VALUES (?, ?, ?, ?, ?, ?, 0) "
        "ON CONFLICT(ticker) DO UPDATE SET "
        "  sector = excluded.sector, industria = excluded.industria, "
        "  tipo = excluded.tipo, nombre = excluded.nombre, "
        "  fuente = excluded.fuente, "
        "  actualizado_en = datetime('now') "
        "WHERE cartera_sectores.es_override = 0",
        (ficha.ticker.upper(), ficha.sector, ficha.industria, ficha.tipo,
         ficha.nombre, ficha.fuente),
    )


def set_override_sector(conn, ticker: str, sector: str,
                        industria: str | None = None) -> None:
    """Fija el sector a mano. Gana sobre cualquier proveedor, siempre."""
    conn.execute(
        "INSERT INTO cartera_sectores "
        "  (ticker, sector, industria, fuente, es_override) "
        "VALUES (?, ?, ?, 'override', 1) "
        "ON CONFLICT(ticker) DO UPDATE SET "
        "  sector = excluded.sector, industria = excluded.industria, "
        "  fuente = 'override', es_override = 1, "
        "  actualizado_en = datetime('now')",
        ((ticker or "").strip().upper(), sector, industria),
    )


def refrescar_sectores(conn, tickers, fetch=None,
                       forzar: bool = False) -> tuple[int, list[str]]:
    """Resuelve y cachea los tickers que todavía no tengan sector.

    Precedencia: **caché/override → Yahoo**.

    El escalón del **snapshot del scoring** se retiró el 5/8/2026 junto con el
    módulo. Antes iba antes que Yahoo porque ya estaba en memoria y no costaba
    una llamada de red, pero cubría ~20 tickers de un universo que Yahoo
    resuelve entero: se comprobó que la cobertura sigue en 100% sin él.

    **Los que no resuelven también se cachean**, con `fuente = 'sin_dato'`.
    Si no, un ticker que Yahoo no conoce dispararía una búsqueda en **cada**
    carga de la pantalla, para siempre. Con `forzar=True` se reintenta todo
    (para el botón de refresco manual).

    Devuelve ``(resueltos, sin_resolver)``. No hace commit: lo decide el
    llamador. Nunca lanza — un ticker que no resuelve queda en "Sin dato".
    """
    cache = leer_sectores_cache(conn)
    resueltos, faltan = 0, []
    for t in {str(x).strip().upper() for x in tickers if x}:
        anterior = cache.get(t)
        if not forzar and anterior is not None:
            # Ya se consultó: tenga sector o no. Los overrides nunca se tocan.
            if anterior.sector:
                continue
            faltan.append(t)
            continue
        if anterior is not None and anterior.fuente == "override":
            continue
        ficha = resolver_ficha(t, fetch)
        if ficha is not None and ficha.sector:
            guardar_ficha_en_cache(conn, ficha)
            resueltos += 1
        else:
            # Caché negativa: deja constancia de que se buscó y no había.
            guardar_ficha_en_cache(conn, FichaTicker(ticker=t, fuente="sin_dato"))
            faltan.append(t)
    return resueltos, faltan


def sectores_para(conn, clave: str = "sector") -> dict[str, str]:
    """``{ticker: sector}`` (o ``industria``) listo para `analisis.por_sector`."""
    campo = "industria" if clave == "industria" else "sector"
    return {
        r["ticker"]: r[campo]
        for r in conn.execute(
            f"SELECT ticker, {campo} FROM cartera_sectores "
            f"WHERE {campo} IS NOT NULL AND {campo} <> ''")
    }
