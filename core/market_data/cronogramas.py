"""Cronogramas de pago de la renta fija (Docta Capital).

**Qué destraba.** La TIR esperada, la duration y el calendario de cobros
necesitan saber, para cada bono, **cuándo paga y cuánto**: cada cupón y cada
amortización con su fecha. Ese dato no está ni en el Excel de Franco ni en las
fuentes que ya usa la app — se verificó contra el OpenAPI de `data912`, que
solo sirve precios. Investigación completa en `docs/CRONOGRAMAS-RENTA-FIJA.md`.

**Fuente:** `api.doctacapital.com.ar`. Cubre soberanos, sub-soberanos y ONs
argentinos, con los flujos ya ajustados por CER/UVA.

---

## La decisión que hace viable el plan gratuito

El plan gratuito da **15 requests por día**. Suena a nada y **alcanza de
sobra**, por un motivo que define todo el diseño de este módulo:

> **Un cronograma es dato estático.** El AE38 va a pagar lo mismo, en las
> mismas fechas, el mes que viene que hoy.

Se baja **una vez por bono** y se guarda en la DB (M15). Franco tiene 2 o 3
instrumentos de renta fija vivos: son 3 requests, una vez. Lo único que
cambiaría seguido es la TIR intradiaria, y **eso no se le pide a nadie**: con
el cronograma cacheado y el precio que ya trae `data912`, la TIR la calcula la
app con la bisección que ya existe en `posiciones.py`.

Por eso `refrescar_cronograma()` **no vuelve a pedir lo que ya tiene** salvo
que se lo fuerce, y la **caché negativa** deja constancia de lo que no está
para no reintentarlo en cada carga.

---

## Resguardos (los que el repo exige para toda fuente externa)

* **`fetch` inyectable** — los tests corren sin red y sin credenciales.
* **Nunca lanza.** Si la API falla, devuelve `None` y la cartera se muestra
  igual con lo que haya en caché. Un proveedor caído no puede tirar abajo una
  pantalla.
* **Credenciales por entorno** (`DOCTA_CLIENT_ID` / `DOCTA_CLIENT_SECRET`),
  nunca en el código. Sin credenciales el módulo se comporta como si la fuente
  no existiera, sin romper nada.
* **Token cacheado en memoria** con su vencimiento: pedir un token por request
  gastaría la cuota al doble.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime

__all__ = [
    "BASE", "Flujo", "Cronograma", "hay_credenciales", "obtener_token",
    "buscar_simbolo", "traer_cronograma", "reset_token",
]

BASE = "https://api.doctacapital.com.ar"
URL_TOKEN = f"{BASE}/api/v1/auth/token/"
URL_BUSQUEDA = f"{BASE}/api/v1/bonds/instruments/search?query={{q}}"
URL_CASHFLOW = (f"{BASE}/api/v1/bonds/analytics/{{simbolo}}/cashflow"
                "?nominal_units={nominales}")

_TIMEOUT = 20
#: Margen antes de que expire el token, para no usar uno que muere en vuelo.
_MARGEN_TOKEN = 60


@dataclass(frozen=True)
class Flujo:
    """Un pago del bono: fecha, cuánto de capital y cuánto de interés."""

    fecha: date
    capital: float = 0.0
    interes: float = 0.0
    total: float = 0.0
    #: Capital que queda vivo después de este pago. Sirve para saber cuánto
    #: del bono ya se amortizó sin tener que acumular a mano.
    residual: float | None = None

    @property
    def es_amortizacion(self) -> bool:
        return abs(self.capital) > 1e-9

    def futuro(self, hoy: date | None = None) -> bool:
        return self.fecha >= (hoy or date.today())


@dataclass
class Cronograma:
    """Los pagos de un bono, para una cantidad de nominales dada."""

    ticker: str
    nominales: float
    flujos: list[Flujo]
    #: `HARD_DOLLAR`, `CER`, etc. Lo informa el proveedor y condiciona cómo se
    #: lee el flujo: un bono CER paga en pesos ajustados.
    clase: str | None = None

    @property
    def total_futuro(self) -> float:
        return sum(f.total for f in self.flujos if f.futuro())

    def proximos(self, hoy: date | None = None) -> list[Flujo]:
        hoy = hoy or date.today()
        return sorted((f for f in self.flujos if f.fecha >= hoy),
                      key=lambda f: f.fecha)

    def proximo_pago(self, hoy: date | None = None) -> Flujo | None:
        prox = self.proximos(hoy)
        return prox[0] if prox else None


# ---------------------------------------------------------------------------
# Credenciales y token
# ---------------------------------------------------------------------------

#: `(token, vence_en_epoch)`. En memoria a propósito: dura lo que el proceso.
_TOKEN: tuple[str, float] | None = None


def reset_token() -> None:
    """Olvida el token cacheado. Para los tests y para rotar credenciales."""
    global _TOKEN
    _TOKEN = None


def hay_credenciales() -> bool:
    """Si no están, el módulo no hace nada — y eso **no es un error**.

    La app tiene que funcionar igual sin esta fuente: los cronogramas son una
    mejora, no un requisito.
    """
    return bool(os.environ.get("DOCTA_CLIENT_ID")
                and os.environ.get("DOCTA_CLIENT_SECRET"))


def _fetch_http(url: str, datos: bytes | None = None,
                cabeceras: dict | None = None) -> str:
    req = urllib.request.Request(url, data=datos, headers=cabeceras or {})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def obtener_token(fetch=None, forzar: bool = False) -> str | None:
    """Token Bearer por *client credentials*, cacheado hasta que vence.

    Devuelve ``None`` si no hay credenciales o si la autenticación falla —
    **nunca lanza**. Pedir un token en cada request gastaría la cuota al doble,
    de ahí la caché.
    """
    global _TOKEN
    if not forzar and _TOKEN and _TOKEN[1] > time.time() + _MARGEN_TOKEN:
        return _TOKEN[0]
    if not hay_credenciales():
        return None

    cuerpo = json.dumps({
        "grant_type": "client_credentials",
        "client_id": os.environ["DOCTA_CLIENT_ID"],
        "client_secret": os.environ["DOCTA_CLIENT_SECRET"],
    }).encode("utf-8")
    try:
        crudo = (fetch or _fetch_http)(
            URL_TOKEN, cuerpo, {"Content-Type": "application/json"})
        datos = json.loads(crudo) if isinstance(crudo, str) else crudo
        token = datos.get("access_token")
        if not token:
            return None
        # ⚠️ `or 3600` NO: en Python el 0 es falso, así que un `expires_in: 0`
        # —un token ya vencido— se convertiría en una hora de validez y el
        # módulo seguiría mandando un token muerto. Lo cazó un test.
        segundos = datos.get("expires_in")
        vence = time.time() + (float(segundos) if segundos is not None
                               else 3600.0)
        _TOKEN = (str(token), vence)
        return _TOKEN[0]
    except Exception:
        return None


def _get(url: str, fetch=None) -> dict | None:
    """GET autenticado. Devuelve el JSON o ``None``. Nunca lanza."""
    token = obtener_token(fetch)
    if not token:
        return None
    try:
        crudo = (fetch or _fetch_http)(
            url, None, {"Authorization": f"Bearer {token}"})
        return json.loads(crudo) if isinstance(crudo, str) else crudo
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def buscar_simbolo(ticker: str, fetch=None) -> str | None:
    """El símbolo exacto que conoce el proveedor, o ``None`` si no lo tiene.

    **Se resuelve antes de pedir el cronograma** porque la documentación lo
    pide explícitamente y porque gastar una consulta en un ticker que no
    existe es tirar cuota.

    ⚠️ Exige **coincidencia exacta**, igual que en `sectores.py`: una búsqueda
    devuelve parecidos, y quedarse con el primero le pondría a un bono el
    cronograma de otro. Es el error más caro que podría cometer este módulo.
    """
    t = str(ticker or "").strip().upper()
    if not t or t.startswith("#"):
        # Los pagarés y cheques del MAV no están en el catálogo (soberanos,
        # sub-soberanos y ONs). Ni se consulta: sería gastar cuota a ciegas.
        return None

    datos = _get(URL_BUSQUEDA.format(q=urllib.parse.quote(t)), fetch)
    if not isinstance(datos, dict):
        return None
    for item in (datos.get("data") or datos.get("results") or []):
        if not isinstance(item, dict):
            continue
        simbolo = str(item.get("ticker") or item.get("symbol") or "").upper()
        if simbolo == t:
            return simbolo
    return None


def _a_fecha(valor) -> date | None:
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def traer_cronograma(ticker: str, nominales: float = 100.0,
                     fetch=None) -> Cronograma | None:
    """El cronograma de un bono, o ``None`` si el proveedor no lo tiene.

    `nominales` escala los importes. Se pide **100** por defecto y se escala
    después: así el mismo cronograma cacheado sirve aunque cambie la tenencia,
    sin gastar otra consulta.
    """
    t = str(ticker or "").strip().upper()
    if not t or t.startswith("#"):
        return None

    datos = _get(
        URL_CASHFLOW.format(simbolo=urllib.parse.quote(t),
                            nominales=int(nominales)),
        fetch,
    )
    if not isinstance(datos, dict):
        return None

    flujos: list[Flujo] = []
    for f in datos.get("data") or []:
        if not isinstance(f, dict):
            continue
        fecha = _a_fecha(f.get("payment_date"))
        if fecha is None:
            continue          # una fila sin fecha no sirve para nada
        capital = float(f.get("adj_capital") or f.get("capital") or 0.0)
        interes = float(f.get("adj_interest_amount")
                        or f.get("interest_amount") or 0.0)
        total = f.get("cash_flow")
        flujos.append(Flujo(
            fecha=fecha,
            capital=capital,
            interes=interes,
            total=float(total) if total is not None else capital + interes,
            residual=(float(f["residual_value"])
                      if f.get("residual_value") is not None else None),
        ))
    if not flujos:
        return None

    meta = datos.get("metadata") or {}
    return Cronograma(
        ticker=t,
        nominales=float(meta.get("nominal_units") or nominales),
        flujos=sorted(flujos, key=lambda x: x.fecha),
        clase=meta.get("subasset_class"),
    )
