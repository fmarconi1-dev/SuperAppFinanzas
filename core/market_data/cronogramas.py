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

⚠️ **"No lo tiene" y "no contestó" son cosas distintas (trampa 16).** Hasta el
22/9/2026 las dos terminaban en la caché negativa: un 429 por cuota agotada,
un timeout o Docta caída marcaban el bono como "sin cronograma" **para
siempre**, y la pantalla decía que era esperable. Ahora solo una respuesta
válida y vacía (o un 404) va a la caché negativa; una falla de la fuente
levanta `FuenteNoDisponible` adentro del módulo, no marca nada y se reintenta
la próxima vez.

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
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime

from core.market_data._errores import ERRORES_DE_RED as _ERRORES_DE_RED
from core.market_data._errores import FuenteNoDisponible

__all__ = [
    "obtener_token_detallado", "FuenteNoDisponible",
    "BASE", "Flujo", "Cronograma", "hay_credenciales", "obtener_token",
    "buscar_simbolo", "traer_cronograma", "reset_token",
    "guardar_cronograma", "leer_cronograma", "marcar_sin_cronograma",
    "ya_consultado", "refrescar_cronogramas",
]

BASE = "https://api.doctacapital.com.ar"

# ⚠️ **Sin barra final.** El ejemplo `curl` de la documentación la lleva
# (`/auth/token/`) pero la especificación OpenAPI —que es la autoridad— define
# el path como `/api/v1/auth/token`. Copiar el ejemplo daba **HTTP 404**, que
# es especialmente engañoso: parece un problema de credenciales y no lo es.
# Pasó el 5/8/2026 en la primera prueba real.
URL_TOKEN = f"{BASE}/api/v1/auth/token"
URL_BUSQUEDA = f"{BASE}/api/v1/bonds/instruments/search?query={{q}}&limit=10"
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


def obtener_token_detallado(fetch=None,
                            forzar: bool = False) -> tuple[str | None, str]:
    """``(token, motivo)``. Igual que `obtener_token` pero **explica el fallo**.

    Existe porque la versión silenciosa es lo correcto para la app —una fuente
    caída no puede tirar una pantalla— pero es **inservible para diagnosticar**.
    El 5/8/2026 el script de verificación falló y lo único que pudo decir fue
    "el token no se pudo obtener", que no ayuda a nadie. `scripts/verificar_docta.py`
    usa esta variante; el resto del código usa la silenciosa.
    """
    global _TOKEN
    if not forzar and _TOKEN and _TOKEN[1] > time.time() + _MARGEN_TOKEN:
        return _TOKEN[0], "cacheado"
    if not hay_credenciales():
        faltan = [v for v in ("DOCTA_CLIENT_ID", "DOCTA_CLIENT_SECRET")
                  if not os.environ.get(v)]
        return None, f"faltan las variables: {', '.join(faltan)}"

    cuerpo = json.dumps({
        "grant_type": "client_credentials",
        "client_id": os.environ["DOCTA_CLIENT_ID"],
        "client_secret": os.environ["DOCTA_CLIENT_SECRET"],
    }).encode("utf-8")
    try:
        crudo = (fetch or _fetch_http)(
            URL_TOKEN, cuerpo, {"Content-Type": "application/json"})
    except urllib.error.HTTPError as exc:
        detalle = ""
        try:
            detalle = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        return None, f"HTTP {exc.code} {exc.reason}. Respuesta: {detalle}"
    except urllib.error.URLError as exc:
        return None, f"no se pudo conectar: {exc.reason}"
    except Exception as exc:                      # pragma: no cover
        return None, f"{type(exc).__name__}: {exc}"

    try:
        datos = json.loads(crudo) if isinstance(crudo, str) else crudo
    except Exception:
        return None, f"la respuesta no es JSON: {str(crudo)[:200]}"

    token = datos.get("access_token") if isinstance(datos, dict) else None
    if not token:
        claves = list(datos) if isinstance(datos, dict) else type(datos).__name__
        return None, (f"la respuesta no trae `access_token`. "
                      f"Vino: {claves}. Cuerpo: {str(datos)[:300]}")

    # ⚠️ `or 3600` NO: en Python el 0 es falso, así que un `expires_in: 0`
    # —un token ya vencido— se convertiría en una hora de validez y el
    # módulo seguiría mandando un token muerto. Lo cazó un test.
    segundos = datos.get("expires_in")
    vence = time.time() + (float(segundos) if segundos is not None else 3600.0)
    _TOKEN = (str(token), vence)
    return _TOKEN[0], "ok"


def obtener_token(fetch=None, forzar: bool = False) -> str | None:
    """Token Bearer por *client credentials*, cacheado hasta que vence.

    Devuelve ``None`` si no hay credenciales o si la autenticación falla —
    **nunca lanza**. Pedir un token en cada request gastaría la cuota al doble,
    de ahí la caché. Para diagnosticar un fallo, ver `obtener_token_detallado`.
    """
    return obtener_token_detallado(fetch, forzar)[0]


def _get_estricto(url: str, fetch=None) -> dict | None:
    """GET autenticado. El JSON, ``None`` si la fuente dice que **no existe**
    (HTTP 404), o `FuenteNoDisponible` si **no contestó**."""
    token, motivo = obtener_token_detallado(fetch)
    if not token:
        raise FuenteNoDisponible(f"sin token: {motivo}")
    try:
        crudo = (fetch or _fetch_http)(
            url, None, {"Authorization": f"Bearer {token}"})
        return json.loads(crudo) if isinstance(crudo, str) else crudo
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise FuenteNoDisponible(f"HTTP {exc.code} {exc.reason}") from exc
    except _ERRORES_DE_RED as exc:
        raise FuenteNoDisponible(f"{type(exc).__name__}: {exc}") from exc


def _get(url: str, fetch=None) -> dict | None:
    """GET autenticado. Devuelve el JSON o ``None``. Nunca lanza por la red."""
    try:
        return _get_estricto(url, fetch)
    except FuenteNoDisponible:
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

    Nunca lanza: si la fuente no contesta también devuelve ``None``. Para
    distinguir los dos casos, `refrescar_cronogramas` usa `_traer`.
    """
    try:
        return _traer(ticker, nominales, fetch)
    except FuenteNoDisponible:
        return None


def _traer(ticker: str, nominales: float = 100.0,
           fetch=None) -> Cronograma | None:
    """Como `traer_cronograma`, pero una falla de la fuente **lanza**
    `FuenteNoDisponible` en vez de parecerse a "no lo tiene"."""
    t = str(ticker or "").strip().upper()
    if not t or t.startswith("#"):
        return None

    datos = _get_estricto(
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


# ---------------------------------------------------------------------------
# Persistencia (M15)
# ---------------------------------------------------------------------------
#
# **La caché no es una optimización: es el uso correcto de la fuente.** El plan
# gratuito da 15 requests por día y alcanza porque un cronograma es dato
# estático. Se baja una vez por bono y queda en la DB. Y la **caché negativa**
# es igual de importante: sin ella, el pagaré —que la fuente no tiene— se
# consultaría en cada carga de la pantalla, para siempre.

def guardar_cronograma(conn, cron: "Cronograma", fuente: str = "docta") -> int:
    """Guarda el cronograma en la DB. Devuelve cuántos flujos escribió."""
    conn.execute("DELETE FROM cartera_cronogramas WHERE ticker = ?",
                 (cron.ticker,))
    filas = [(cron.ticker, f.fecha.isoformat(), f.capital, f.interes,
              f.total, f.residual) for f in cron.flujos]
    conn.executemany(
        "INSERT OR REPLACE INTO cartera_cronogramas "
        "(ticker, fecha_pago, capital, interes, total, residual) "
        "VALUES (?, ?, ?, ?, ?, ?)", filas)
    conn.execute(
        "INSERT INTO cartera_cronogramas_meta "
        "(ticker, clase, nominales_base, fuente, n_flujos, actualizado_en) "
        "VALUES (?, ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(ticker) DO UPDATE SET clase = excluded.clase, "
        "  nominales_base = excluded.nominales_base, fuente = excluded.fuente, "
        "  n_flujos = excluded.n_flujos, actualizado_en = datetime('now')",
        (cron.ticker, cron.clase, cron.nominales, fuente, len(filas)))
    return len(filas)


def marcar_sin_cronograma(conn, ticker: str, motivo: str = "sin_dato") -> None:
    """**Caché negativa.** Deja constancia de que se buscó y no había.

    Sin esto, el pagaré del MAV dispararía una consulta en cada carga de la
    pantalla y se comería la cuota diaria sin traer nada nunca.
    """
    conn.execute(
        "INSERT INTO cartera_cronogramas_meta "
        "(ticker, fuente, n_flujos, actualizado_en) "
        "VALUES (?, ?, 0, datetime('now')) "
        "ON CONFLICT(ticker) DO UPDATE SET fuente = excluded.fuente, "
        "  n_flujos = 0, actualizado_en = datetime('now')",
        (str(ticker).strip().upper(), motivo))


def leer_cronograma(conn, ticker: str,
                    nominales: float | None = None) -> Cronograma | None:
    """El cronograma cacheado, escalado a `nominales` si se pide.

    Los importes están guardados **por 100 nominales** (como los sirve la API),
    así que escalar es una multiplicación — y por eso el mismo cronograma
    guardado sigue sirviendo aunque cambie la tenencia, sin gastar cuota.
    """
    t = str(ticker or "").strip().upper()
    try:
        meta = conn.execute(
            "SELECT clase, nominales_base, n_flujos FROM "
            "cartera_cronogramas_meta WHERE ticker = ?", (t,)).fetchone()
        if meta is None or not meta["n_flujos"]:
            return None
        filas = conn.execute(
            "SELECT fecha_pago, capital, interes, total, residual "
            "FROM cartera_cronogramas WHERE ticker = ? ORDER BY fecha_pago",
            (t,)).fetchall()
    except sqlite3.OperationalError:
        # Base sin M15 (tests con esquema recortado). Solo el error de SQLite:
        # un error de programación tiene que verse, no parecer "sin dato".
        return None

    base = float(meta["nominales_base"] or 100.0) or 100.0
    escala = (float(nominales) / base) if nominales else 1.0

    flujos = []
    for r in filas:
        fecha = _a_fecha(r["fecha_pago"])
        if fecha is None:
            continue
        flujos.append(Flujo(
            fecha=fecha,
            capital=(r["capital"] or 0.0) * escala,
            interes=(r["interes"] or 0.0) * escala,
            total=(r["total"] or 0.0) * escala,
            residual=((r["residual"] * escala)
                      if r["residual"] is not None else None),
        ))
    if not flujos:
        return None
    return Cronograma(ticker=t, nominales=(nominales or base),
                      flujos=flujos, clase=meta["clase"])


def ya_consultado(conn, ticker: str) -> bool:
    """Si ya se preguntó por este ticker — **tenga o no cronograma**."""
    try:
        fila = conn.execute(
            "SELECT 1 FROM cartera_cronogramas_meta WHERE ticker = ?",
            (str(ticker).strip().upper(),)).fetchone()
        return fila is not None
    except sqlite3.OperationalError:          # base sin M15
        return False


def refrescar_cronogramas(conn, tickers, fetch=None, forzar: bool = False
                          ) -> tuple[int, list[str], list[str]]:
    """Baja los cronogramas que falten y los cachea.

    **No vuelve a pedir lo que ya preguntó** salvo `forzar=True`: con 15
    consultas por día, reintentar en cada carga vaciaría la cuota en minutos.

    Devuelve ``(resueltos, sin_datos, no_consultados)``:

    * `sin_datos` — la fuente contestó que no lo tiene: va a la caché negativa.
    * `no_consultados` — la fuente **no contestó** (sin token, caída, cuota
      agotada). **No se marcan**: se reintentan la próxima vez. Al primer
      fallo se corta, porque con la cuota agotada los que siguen fallarían
      igual.

    Nunca lanza por la red: sin credenciales o con la fuente caída, la cartera
    se muestra igual con lo cacheado.
    """
    resueltos, faltan, no_consultados = 0, [], []
    pendientes = sorted({str(x).strip().upper() for x in tickers if x})
    for i, t in enumerate(pendientes):
        if not forzar and ya_consultado(conn, t):
            if leer_cronograma(conn, t) is None:
                faltan.append(t)
            continue
        if t.startswith("#"):
            # Pagarés y cheques del MAV: fuera del catálogo, confirmado el
            # 5/8/2026. Se marca sin consultar para no gastar cuota.
            marcar_sin_cronograma(conn, t, "fuera_del_catalogo")
            faltan.append(t)
            continue

        try:
            cron = _traer(t, fetch=fetch)
        except FuenteNoDisponible:
            no_consultados.extend(x for x in pendientes[i:]
                                  if not x.startswith("#"))
            break
        if cron is None or not cron.flujos:
            marcar_sin_cronograma(conn, t)
            faltan.append(t)
            continue
        guardar_cronograma(conn, cron)
        resueltos += 1
    return resueltos, faltan, no_consultados
