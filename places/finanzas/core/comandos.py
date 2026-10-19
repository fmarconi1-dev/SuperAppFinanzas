"""Comandos de WhatsApp: texto que manda Franco → respuesta (Fase A, ADR-0008).

**Puro y sin red.** Recibe el texto, una conexión y el usuario, y devuelve qué
contestar. Quién mandó el mensaje, la firma de Meta y el envío viven en
`core/api/`; acá no se sabe nada de WhatsApp, así que el día que el canal sea
otro (Telegram), este archivo no cambia.

Formato de una carga (separadores `,` `;` `|`, o espacio entre monto y
categoría):

    [fecha], monto, categoría[, comentario]

Ejemplos: ``2500, super`` · ``13/10; 18.000 | nafta | YPF`` · ``+350000 sueldo``.

Reglas que no se negocian:

* **Nunca se carga a ciegas.** Un monto ambiguo, una fecha imposible o una
  categoría dudosa se repregunta; no se adivina.
* **`user_id` explícito en todas las llamadas.** Esto corre en un hilo del
  servidor HTTP, donde los contextvars de usuario y workspace arrancan vacíos.
* **"Hoy" es hoy en Buenos Aires**, nunca en la zona del servidor (Fly corre
  en UTC: a las 22:00 de acá allá ya es mañana).
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from core.api.archivos import ArchivoRecibido
from core.api.google import AgendaNoDisponible, AgendaRechazo
from core.db import backup_db
from core.workspaces import resolve_workspace_id
from places.finanzas.core import agenda as ag
from places.finanzas.core import lotes

from places.finanzas.core.metrics import (
    ingresos_vs_gastos_mensual,
    load_categorias_full,
    load_transactions,
)
from places.finanzas.core.transactions import (
    all_motivos,
    delete_transaction,
    get_transaction,
    insertar_sin_backup,
    list_recent,
)

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")

#: Un gasto esperando "sí" o "no" deja de valer a los 10 minutos.
VIGENCIA_PENDIENTE = timedelta(minutes=10)
#: `deshacer` solo alcanza lo cargado por WhatsApp en las últimas 24 h.
VENTANA_DESHACER = timedelta(hours=24)
#: Una fecha sin año más adelante que esto se toma como del año pasado.
DIAS_SALTO_DE_ANIO = 180
#: Parecido mínimo (difflib) para proponer una categoría existente.
CORTE_PARECIDO = 0.75

AYUDA = (
    "*Cómo cargar*\n"
    "monto, categoría[, comentario]\n"
    "  • 2500, super\n"
    "  • 13/10, 18.000, nafta, YPF ruta 2\n"
    "  • ayer; 4500 | farmacia\n"
    "  • +350000, sueldo  (el + es ingreso)\n"
    "Montos: 25.000 · 2500,50 · $25.000 · 25k\n"
    "Cuentas: 100-50 · 3x2.500 · 12.000/3 · 1500+800\n"
    "Fechas: hoy · ayer · 13/10 · 13/10/2026\n"
    "Varios gastos: uno por renglón en el mismo mensaje; te los muestro\n"
    "  y los cargo todos juntos con tu *ok*\n\n"
    "*Agenda*\n"
    "  • evento: viernes, 15:00, 16:00, Dentista\n"
    "  • evento: 20/10, Cumple de Juan  (todo el día)\n"
    "  • tarea: 25/10, Pagar seguro  ·  tarea: Llamar al contador\n"
    "  • agenda — eventos de la semana y tareas pendientes\n\n"
    "*Comandos*\n"
    "  • resumen — gastos e ingresos del mes\n"
    "  • deshacer — borra lo último que cargaste por acá (si fueron\n"
    "    varios juntos, los borra a todos)\n"
    "  • ayuda — este mensaje"
)

SI = {"si", "sí", "s", "dale", "ok", "okay", "yes", "correcto", "listo"}
NO = {"no", "n", "nop", "cancelar", "cancela"}


@dataclass
class Respuesta:
    """Lo que hay que contestar y qué pasó, para registrarlo."""

    texto: str
    #: cargado | lote (varios gastos aplicados juntos) | consulta | pendiente |
    #: deshecho | rechazado | error | agendado | archivo (llegó un archivo)
    resultado: str
    transaccion_id: Optional[int] = None


@dataclass
class Gasto:
    fecha: date
    monto: float
    es_ingreso: bool
    categoria: str
    comentario: Optional[str] = None
    #: La cuenta tal como la escribió Franco ("100-50"), si el monto era una.
    cuenta: Optional[str] = None

    @property
    def bruto(self) -> Optional[float]:
        """Lo que salió en el momento, si el monto era una cuenta (`bruto_de_cuenta`)."""
        return bruto_de_cuenta(self.cuenta) if self.cuenta else None


class EntradaInvalida(ValueError):
    """El mensaje no se puede cargar tal como está. El texto va a Franco."""


def ahora_ar() -> datetime:
    return datetime.now(ZONA)


# ---------------------------------------------------------------------------
# Montos
# ---------------------------------------------------------------------------

_RE_MILES = re.compile(r"^\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?$")
_RE_SIMPLE = re.compile(r"^\d+(?:,\d{1,2})?$")
_RE_K = re.compile(r"^(\d+(?:,\d{1,3})?)k$")
_RE_PUNTO_DECIMAL = re.compile(r"^\d+\.\d{1,2}$")


#: Signos de cuenta que se aceptan en el monto, con sus equivalentes del
#: teclado del celular (× ÷ − y la "x" de "3x2.500").
_OPERADORES = {"+": "+", "-": "-", "−": "-", "*": "*", "x": "*", "×": "*",
               "/": "/", "÷": "/"}
_RE_OPERADOR = re.compile(r"\s*([-+*/x×÷−])\s*", re.IGNORECASE)


def parsear_monto(crudo: str) -> float:
    """Monto tipeado en el celular: un número o una **cuenta** con + − × ÷.

    Cada número sigue las reglas de `_numero` (formato argentino, estricto).
    La cuenta respeta la precedencia de siempre (× y ÷ antes que + y −):
    ``100-50`` = 50 · ``3x2.500`` = 7.500 · ``1000+500*2`` = 2.000.
    Solo números y esos signos: no se evalúa texto libre. Un resultado de
    cero o negativo, o una división por cero, se rechazan.
    """
    partes = _RE_OPERADOR.split(crudo.strip())
    if len(partes) == 1:
        valor = _numero(partes[0])
    else:
        if len(partes) % 2 == 0 or any(not partes[i].strip() for i in range(0, len(partes), 2)):
            raise EntradaInvalida(f"No entendí la cuenta «{crudo.strip()}».")
        terminos = [_numero(partes[0])]
        sumas: list[str] = []
        for i in range(1, len(partes), 2):
            op, n = _OPERADORES[partes[i].lower()], _numero(partes[i + 1])
            if op == "*":
                terminos[-1] *= n
            elif op == "/":
                if n == 0:
                    raise EntradaInvalida(f"La cuenta «{crudo.strip()}» divide por cero.")
                terminos[-1] /= n
            else:
                sumas.append(op)
                terminos.append(n)
        valor = terminos[0]
        for op, n in zip(sumas, terminos[1:]):
            valor = valor + n if op == "+" else valor - n

    valor = round(valor, 2)
    if valor <= 0:
        if len(partes) > 1:
            raise EntradaInvalida(
                f"La cuenta «{crudo.strip()}» da {valor:g}: el monto tiene que ser mayor que cero.")
        raise EntradaInvalida("El monto tiene que ser mayor que cero.")
    return valor


def bruto_de_cuenta(cuenta: str) -> float:
    """Lo que Franco pagó en el momento, antes de que le devuelvan (ADR-0009 §4).

    Regla (aprobada por Franco el 19/10/2026): lo que está **antes del primer
    −**, con cada división reemplazada por su dividendo.

    * ``150000-25000*5`` → 150.000 (se carga 25.000: cinco le devolvieron)
    * ``100-50`` → 100 · ``12.000/3`` → 12.000 (pagó todo y lo dividen entre 3)
    * ``3x2.500`` → 7.500 · ``2500+1500`` → 4.000 (nadie devuelve nada)
    * ``1000+500*2-300`` → 2.000

    La conciliación lo usa para reconocer las devoluciones y para descontar
    del efectivo lo que salió de verdad. Es función pura de la cuenta
    guardada: sirve igual para un gasto de hoy que para releer un mensaje viejo.
    """
    partes = _RE_OPERADOR.split(cuenta.strip())
    terminos = [_numero(partes[0])]
    for i in range(1, len(partes), 2):
        op, n = _OPERADORES[partes[i].lower()], _numero(partes[i + 1])
        if op == "-":
            break
        if op == "*":
            terminos[-1] *= n
        elif op == "+":
            terminos.append(n)
        # "/": el dividendo es lo que se pagó; la división es el reparto.
    return round(sum(terminos), 2)


def _numero(crudo: str) -> float:
    """Un número tipeado en el celular, en formato argentino. Estricto a propósito.

    * Punto: solo miles, en grupos de 3 (``25.000``, ``1.250.000``).
    * Coma: decimal (``2500,50``).
    * ``$`` adelante y ``k`` atrás son opcionales (``25k`` = 25.000).
    * ``2500.50`` es **ambiguo** (¿2.500,50 o 250.050?): se repregunta.

    No se reusa `parsers.parse_currency_estricto`: borra todos los puntos,
    así que ``1.5`` daría 15. Sirve para el CSV, no para un mensaje.
    """
    s = crudo.strip().lower().replace(" ", "")
    s = s.removeprefix("ars").removeprefix("$")
    if not s:
        raise EntradaInvalida("Falta el monto.")

    if m := _RE_K.match(s):
        valor = float(m.group(1).replace(",", ".")) * 1000
    elif _RE_MILES.match(s):
        valor = float(s.replace(".", "").replace(",", "."))
    elif _RE_SIMPLE.match(s):
        valor = float(s.replace(",", "."))
    elif _RE_PUNTO_DECIMAL.match(s):
        entero, dec = s.split(".")
        raise EntradaInvalida(
            f"No sé si «{crudo.strip()}» es {entero},{dec} o {entero}{dec}. "
            f"Mandalo con coma para los centavos ({entero},{dec}) o sin separador."
        )
    else:
        raise EntradaInvalida(f"No entendí el monto «{crudo.strip()}».")
    return valor


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

_RE_FECHA_INICIO = re.compile(
    r"^\s*(hoy|ayer|\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{4}-\d{1,2}-\d{1,2})\s*(?:[,;|]\s*|\s+)",
    re.IGNORECASE,
)


def parsear_fecha(crudo: str, hoy: date) -> date:
    """``hoy``, ``ayer``, ``DD/MM``, ``DD/MM/AA``, ``DD/MM/AAAA`` o ``AAAA-MM-DD``.

    Sin año: el año actual, salvo que la fecha quede **lejos** en el futuro
    (más de `DIAS_SALTO_DE_ANIO`): un ``28/12`` cargado el 2 de enero es del
    año pasado. Una fecha apenas futura (``20/10`` cargado el 15/10) es un
    error de tipeo y se rechaza: pasarla al año anterior la escondería del
    `resumen` del mes sin que Franco se entere.
    """
    s = crudo.strip().lower()
    if s == "hoy":
        return hoy
    if s == "ayer":
        return hoy - timedelta(days=1)
    try:
        if "-" in s:
            a, m, d = (int(x) for x in s.split("-"))
            f = date(a, m, d)
        else:
            partes = [int(x) for x in s.split("/")]
            d, m = partes[0], partes[1]
            if len(partes) == 3:
                a = partes[2] + 2000 if partes[2] < 100 else partes[2]
                f = date(a, m, d)
            else:
                f = date(hoy.year, m, d)
                if (f - hoy).days > DIAS_SALTO_DE_ANIO:
                    f = date(hoy.year - 1, m, d)
    except ValueError:
        raise EntradaInvalida(f"La fecha «{crudo.strip()}» no existe.") from None
    if f > hoy:
        raise EntradaInvalida(f"La fecha {f:%d/%m/%Y} está en el futuro.")
    return f


# ---------------------------------------------------------------------------
# El mensaje completo
# ---------------------------------------------------------------------------

# Monto al principio: signo opcional, $ opcional, dígitos/puntos/comas y k.
# Tiene que **terminar en dígito** (o k): si no, en "2500, super" la coma
# separadora quedaba pegada al monto ("2500,"). Con eso, en "2500,50, super"
# el monto es "2500,50" y la coma siguiente es el separador.
# Puede ser una **cuenta**: números unidos por + − × ÷ (con o sin espacios).
# Sin esto, "100 - 50, compras" tomaba $100 y la categoría "- 50".
_NUM = r"(?:ars)?\s*\$?\s*\d(?:[\d.,]*\d)?k?"
_RE_MONTO_INICIO = re.compile(
    rf"^\s*(?P<signo>\+)?\s*(?P<monto>{_NUM}(?:\s*[-+*/x×÷−]\s*{_NUM})*)"
    r"\s*(?:[,;|]\s*|\s+)(?P<resto>.+)$",
    re.IGNORECASE | re.DOTALL,
)
#: Una categoría tiene que tener al menos una letra y no empezar con un signo.
_RE_TIENE_LETRA = re.compile(r"[^\W\d_]")
_RE_SEPARADOR = re.compile(r"\s*[,;|]\s*")


def parsear_gasto(texto: str, hoy: date) -> Gasto:
    """Texto de una carga → `Gasto`. `EntradaInvalida` con el motivo si no se puede."""
    resto = texto.strip()
    fecha = hoy
    # Un "12/3" al principio es fecha **solo si después viene un monto**
    # ("12/3, 500, super"). Si no ("12/3, super"), es la cuenta 12 ÷ 3.
    m = _RE_FECHA_INICIO.match(resto)
    if m and _RE_MONTO_INICIO.match(resto[m.end():]):
        fecha = parsear_fecha(m.group(1), hoy)
        resto = resto[m.end():]

    m = _RE_MONTO_INICIO.match(resto)
    if not m:
        raise EntradaInvalida("No encontré monto y categoría.")
    crudo = m.group("monto")
    monto = parsear_monto(crudo)
    partes = [p for p in _RE_SEPARADOR.split(m.group("resto").strip()) if p]
    if not partes:
        raise EntradaInvalida("Falta la categoría.")
    categoria = " ".join(partes[0].split())
    if not _RE_TIENE_LETRA.search(categoria) or categoria[0] in "+-*/×÷−=":
        raise EntradaInvalida(f"«{categoria}» no parece una categoría.")
    comentario = ", ".join(partes[1:]) or None
    cuenta = "".join(crudo.split()) if _RE_OPERADOR.search(crudo) else None
    return Gasto(fecha=fecha, monto=monto, es_ingreso=bool(m.group("signo")),
                 categoria=categoria, comentario=comentario, cuenta=cuenta)


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------

def normalizar(s: str) -> str:
    """Minúsculas, sin acentos y con espacios simples: "Café  Martínez" → "cafe martinez"."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )
    return " ".join(sin_acentos.lower().split())


def resolver_categoria(tipeada: str, existentes: list[str]) -> tuple[str, Optional[str]]:
    """('exacta', nombre) · ('parecida', sugerencia) · ('nueva', None).

    Parecida = un único motivo que empieza con lo tipeado (``super`` →
    Supermercado) o el más parecido según difflib por encima del corte.
    """
    t = normalizar(tipeada)
    por_norma = {normalizar(e): e for e in existentes}
    if t in por_norma:
        return "exacta", por_norma[t]
    if len(t) >= 3:
        prefijos = [e for n, e in por_norma.items() if n.startswith(t)]
        if len(prefijos) == 1:
            return "parecida", prefijos[0]
    cercanas = difflib.get_close_matches(t, list(por_norma), n=1, cutoff=CORTE_PARECIDO)
    if cercanas:
        return "parecida", por_norma[cercanas[0]]
    return "nueva", None


# ---------------------------------------------------------------------------
# Estado del canal (pendiente)
# ---------------------------------------------------------------------------

def _leer_estado(conn: sqlite3.Connection, clave: str) -> Optional[str]:
    row = conn.execute("SELECT valor FROM whatsapp_estado WHERE clave = ?", (clave,)).fetchone()
    return row["valor"] if row else None


def guardar_estado(conn: sqlite3.Connection, clave: str, valor: str, ahora: datetime) -> None:
    conn.execute(
        "INSERT INTO whatsapp_estado (clave, valor, actualizado_en) VALUES (?, ?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, "
        "actualizado_en = excluded.actualizado_en",
        (clave, valor, ahora.isoformat()),
    )


def _borrar_pendiente(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM whatsapp_estado WHERE clave = 'pendiente'")


def _leer_pendiente(conn: sqlite3.Connection, ahora: datetime) -> Optional[dict]:
    crudo = _leer_estado(conn, "pendiente")
    if not crudo:
        return None
    p = json.loads(crudo)
    if ahora - datetime.fromisoformat(p["creado_en"]) > VIGENCIA_PENDIENTE:
        _borrar_pendiente(conn)
        return None
    return p


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------

def pesos(valor: float) -> str:
    """$2.500 · $2.500,50 — sin ",00" cuando no hay centavos."""
    s = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    s = s.removesuffix(",00")
    return f"-${s}" if valor < 0 else f"${s}"


def _fecha_corta(f: date, hoy: date) -> str:
    """13/10, o 28/12/2025 si no es de este año: el año nunca queda implícito."""
    return f"{f:%d/%m}" if f.year == hoy.year else f"{f:%d/%m/%Y}"


def _confirmacion(txn_id: int, g: Gasto, categoria: str, hoy: date) -> str:
    linea = (f"✅ Cargado #{txn_id}: {pesos(g.monto)} en {categoria} "
             f"({_fecha_corta(g.fecha, hoy)})")
    if g.cuenta:
        linea += f" · {g.cuenta}"
    if g.es_ingreso:
        linea += " — ingreso"
    if g.comentario:
        linea += f"\n📝 {g.comentario}"
    return linea


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def procesar(
    conn: sqlite3.Connection,
    texto: str,
    *,
    user_id: int,
    ahora: Optional[datetime] = None,
    agenda: Optional[Any] = None,
    id_mensaje: Optional[str] = None,
) -> Respuesta:
    """Interpreta un mensaje de Franco y, si corresponde, escribe en la base.

    `agenda` es el cliente del Apps Script (`core.api.google.ClienteAgenda`),
    o None si no está configurado. `id_mensaje` (el wamid) viaja a Google como
    `id_solicitud`, para que un reintento de Meta no cree dos eventos.
    """
    ahora = ahora or ahora_ar()
    hoy = ahora.astimezone(ZONA).date()
    limpio = (texto or "").strip()
    clave = normalizar(limpio).strip(" .!¡?¿")

    pendiente = _leer_pendiente(conn, ahora)
    if pendiente and (clave in SI or clave in NO):
        # La pregunta de un gasto suelto es la más nueva: su sí/no va primero.
        return _responder_pendiente(conn, pendiente, clave in SI, user_id, hoy)
    if pendiente:
        # Cualquier otra cosa descarta la pregunta y se procesa como nueva.
        _borrar_pendiente(conn)

    # Una propuesta de varios gastos (lote) **no** se descarta con cualquier
    # mensaje: solo la tocan `ok`, `no`/`cancelar` o "N algo" con N de la lista.
    wid = resolve_workspace_id(conn, user_id)
    lote = lotes.vigente(conn, workspace_id=wid, ahora=ahora)
    if lote and (respuesta_lote := _leer_respuesta_lote(limpio, _cantidad(lote.propuesta))):
        if lote.propuesta.get("tipo") == "extracto":
            from places.finanzas.core import conciliacion  # diferido: conciliacion usa este módulo
            r = conciliacion.responder(
                conn, lote, aceptar=respuesta_lote.aceptar, cancelar=respuesta_lote.cancelar,
                correcciones=respuesta_lote.correcciones, user_id=user_id, wid=wid, ahora=ahora)
            return Respuesta(r.texto, r.resultado)
        return _responder_lote(conn, lote, respuesta_lote, user_id, ahora, hoy)

    if not limpio:
        return Respuesta("No recibí texto. Mandá *ayuda* para ver cómo cargar.", "rechazado")
    if clave in {"ayuda", "help", "comandos"}:
        return Respuesta(AYUDA, "consulta")
    if clave in {"resumen", "saldo"}:
        return Respuesta(resumen_mes(conn, user_id=user_id, hoy=hoy), "consulta")
    if clave in {"deshacer", "borrar ultimo", "borra ultimo"}:
        return deshacer(conn, user_id=user_id, ahora=ahora)
    if clave in SI or clave in NO:
        return Respuesta("No tengo nada pendiente de confirmar.", "rechazado")
    if m := _RE_COMANDO_AGENDA.match(limpio):
        return _comando_agenda(m.group(1).lower(), m.group(2), agenda, id_mensaje, hoy)
    if clave in {"agenda", "semana"}:
        return _comando_agenda("agenda", "", agenda, id_mensaje, hoy)
    renglones = [r.strip() for r in limpio.splitlines() if r.strip()]
    if len(renglones) >= 2 and _RE_EMPIEZA_COMO_GASTO.match(renglones[0]):
        return _proponer_varios(conn, renglones, user_id, wid, ahora, hoy)

    try:
        g = parsear_gasto(limpio, hoy)
    except EntradaInvalida as e:
        return Respuesta(f"⚠️ {e}\n\nMandá *ayuda* para ver los formatos.", "rechazado")

    tipo, nombre = resolver_categoria(g.categoria, all_motivos(conn, user_id=user_id))
    if tipo == "exacta":
        txn_id = _insertar(conn, g, nombre, user_id)
        return Respuesta(_confirmacion(txn_id, g, nombre, hoy), "cargado", txn_id)

    propuesta = nombre if tipo == "parecida" else _capitalizar(g.categoria)
    guardar_estado(conn, "pendiente", json.dumps({
        "fecha": g.fecha.isoformat(),
        "monto": g.monto,
        "es_ingreso": g.es_ingreso,
        "categoria": propuesta,
        "comentario": g.comentario,
        "cuenta": g.cuenta,
        "creado_en": ahora.isoformat(),
    }), ahora)
    if tipo == "parecida":
        pregunta = f"¿Quisiste decir *{propuesta}*?"
    else:
        pregunta = f"La categoría *{propuesta}* no existe. ¿La creo?"
    return Respuesta(
        f"{pregunta} ({pesos(g.monto)}{' = ' + g.cuenta if g.cuenta else ''}, "
        f"{_fecha_corta(g.fecha, hoy)})\nRespondé *sí* o *no*.", "pendiente"
    )


def procesar_archivo(
    conn: sqlite3.Connection,
    archivo: ArchivoRecibido,
    *,
    user_id: int,
    ahora: Optional[datetime] = None,
) -> Respuesta:
    """Un archivo que mandó Franco, ya bajado y reconocido (Fase D, paso 3).

    Un Excel es el extracto de la caja de Galicia: se lee y se arma la
    propuesta de conciliación (un lote, que no escribe nada hasta el `ok`).
    Los resúmenes de tarjeta son el paso 5 y las fotos el 6
    (`docs/PLAN-FASE-D.md`). El archivo vive en memoria y no se guarda.
    """
    ahora = ahora or ahora_ar()
    if archivo.tipo == "xlsx":
        from places.finanzas.core import conciliacion  # diferido: conciliacion usa este módulo
        from places.finanzas.core.extracto_galicia import ExtractoInvalido, leer_extracto

        try:
            extracto = leer_extracto(archivo.datos)
        except ExtractoInvalido as e:
            return Respuesta(f"⚠️ No pude leer el extracto: {e}", "rechazado")
        wid = resolve_workspace_id(conn, user_id)
        try:
            propuesta = conciliacion.proponer_extracto(conn, extracto, user_id=user_id, wid=wid,
                                                       ahora=ahora)
        except conciliacion.ConciliacionInvalida as e:
            return Respuesta(f"⚠️ {e}", "rechazado")
        _borrar_pendiente(conn)
        habia_otra = lotes.proponer(conn, workspace_id=wid, user_id=user_id, origen="extracto",
                                    propuesta=propuesta, ahora=ahora)
        texto = conciliacion.texto_propuesta(propuesta, nuevo_ancla=bool(propuesta["ancla"]))
        if habia_otra:
            texto = "(Descarté la propuesta anterior, que no habías confirmado.)\n\n" + texto
        return Respuesta(texto, "pendiente")

    que = {"pdf": "Leer los resúmenes de tarjeta"}.get(archivo.tipo, "Leer fotos")
    return Respuesta(
        f"📎 Recibí {archivo.describir()}. {que} es lo próximo que aprendo: "
        "todavía no lo leo. No guardé el archivo.",
        "archivo",
    )


_RE_COMANDO_AGENDA = re.compile(r"^\s*(evento|tarea|task)\s*:\s*(.*)$", re.IGNORECASE | re.DOTALL)


def _comando_agenda(
    comando: str, cuerpo: str, agenda: Optional[Any], id_mensaje: Optional[str], hoy: date
) -> Respuesta:
    """`evento:`, `tarea:` y `agenda`. Confirma **solo** si Google dijo `ok: true`."""
    if agenda is None:
        return Respuesta("La agenda todavía no está conectada (falta configurar el Apps Script).",
                         "rechazado")
    try:
        if comando == "evento":
            ev = ag.parsear_evento(cuerpo, hoy)
            agenda.crear_evento(**ev, id_solicitud=id_mensaje)
            return Respuesta(ag.confirmar_evento(ev, hoy), "agendado")
        if comando in {"tarea", "task"}:
            ta = ag.parsear_tarea(cuerpo, hoy)
            agenda.crear_tarea(**ta, id_solicitud=id_mensaje)
            return Respuesta(ag.confirmar_tarea(ta, hoy), "agendado")
        return Respuesta(ag.formatear_semana(agenda.resumen_semana(), hoy), "consulta")
    except ag.AgendaInvalida as e:
        return Respuesta(f"⚠️ {e}", "rechazado")
    except AgendaRechazo as e:
        return Respuesta(f"⚠️ Google no lo aceptó ({e}). No se agendó nada.", "error")
    except AgendaNoDisponible as e:
        return Respuesta(f"⚠️ No pude hablar con Google ({e}). No se agendó nada; "
                         "probá de nuevo en un rato.", "error")


def _capitalizar(s: str) -> str:
    s = " ".join(s.split())
    return s[:1].upper() + s[1:]


def _insertar(conn: sqlite3.Connection, g: Gasto, categoria: str, user_id: int) -> int:
    """Un gasto suelto: la fila y, si el monto era una cuenta, su bruto, juntos o nada."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        txn_id = insertar_sin_backup(
            conn,
            fecha=g.fecha,
            motivo=categoria,
            pasivos=0.0 if g.es_ingreso else g.monto,
            ingresos=g.monto if g.es_ingreso else 0.0,
            comentario=g.comentario,
            user_id=user_id,
        )
        if g.cuenta:
            _guardar_cuenta(conn, txn_id, g.cuenta)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    backup_db()
    return txn_id


def _guardar_cuenta(conn: sqlite3.Connection, txn_id: int, cuenta: str) -> None:
    conn.execute(
        "INSERT INTO gasto_cuentas (transaccion_id, workspace_id, cuenta, bruto) "
        "SELECT id, workspace_id, ?, ? FROM transacciones WHERE id = ?",
        (cuenta, bruto_de_cuenta(cuenta), txn_id),
    )


def _movimiento(item: dict) -> lotes.Movimiento:
    monto = float(item["monto"])
    return lotes.Movimiento(
        fecha=date.fromisoformat(item["fecha"]),
        motivo=item["categoria"],
        pasivos=0.0 if item["es_ingreso"] else monto,
        ingresos=monto if item["es_ingreso"] else 0.0,
        comentario=item.get("comentario"),
        cuenta=item.get("cuenta"),
        bruto=bruto_de_cuenta(item["cuenta"]) if item.get("cuenta") else None,
    )


# ---------------------------------------------------------------------------
# Varios gastos en un mensaje (Fase D, paso 2): una propuesta = un lote
# ---------------------------------------------------------------------------

#: El primer renglón de un mensaje de varios gastos empieza como una carga:
#: con fecha, monto o "+" de ingreso. Si no ("evento: …" en dos renglones,
#: un texto cualquiera), se procesa como siempre.
_RE_EMPIEZA_COMO_GASTO = re.compile(r"^(?:\+|\$|hoy\b|ayer\b|\d)", re.IGNORECASE)
#: "2 transportes", "3 no": número de renglón de la propuesta y qué hacer.
_RE_CORRECCION = re.compile(r"^(\d{1,3})\s+(\S.*)$")


def _cantidad(propuesta: dict) -> int:
    """Cuántos renglones se pueden nombrar con su número en esta propuesta."""
    if "numerados" in propuesta:
        return propuesta["numerados"]
    return len(propuesta["items"])


@dataclass
class RespuestaLote:
    aceptar: bool = False
    cancelar: bool = False
    #: (número de renglón, texto): "no" lo saca; otra cosa es la categoría.
    correcciones: tuple[tuple[int, str], ...] = ()


def _leer_respuesta_lote(texto: str, cantidad: int) -> Optional[RespuestaLote]:
    """¿El mensaje contesta la propuesta? None si es otra cosa (un gasto, `agenda`).

    Contesta si es `ok`/sí, `no`/`cancelar`, o una lista separada por comas de
    "N algo" con N **entero y dentro de la propuesta**, con `ok` opcional al
    final: ``2 transportes, 3 no, ok``. Así ``2.500 super`` o ``$2 super``
    siguen siendo gastos. Un `no` a secas descarta la propuesta entera, igual
    que el `no` a un gasto suelto.
    """
    clave = normalizar(texto).strip(" .!¡?¿")
    if clave in SI:
        return RespuestaLote(aceptar=True)
    if clave in NO:
        return RespuestaLote(cancelar=True)
    partes = [p.strip() for p in _RE_SEPARADOR.split(texto.strip()) if p.strip()]
    if not partes:
        return None
    aceptar = normalizar(partes[-1]).strip(" .!¡?¿") in SI
    if aceptar:
        partes = partes[:-1]
    correcciones = []
    for p in partes:
        m = _RE_CORRECCION.match(p)
        if not m or not 1 <= int(m.group(1)) <= cantidad:
            return None
        correcciones.append((int(m.group(1)), " ".join(m.group(2).split())))
    if not correcciones:
        return None
    return RespuestaLote(aceptar=aceptar, correcciones=tuple(correcciones))


def _item_de_gasto(g: Gasto, existentes: list[str]) -> dict:
    tipo, nombre = resolver_categoria(g.categoria, existentes)
    return {
        "fecha": g.fecha.isoformat(),
        "monto": g.monto,
        "es_ingreso": g.es_ingreso,
        "categoria": nombre if tipo != "nueva" else _capitalizar(g.categoria),
        "tipo": tipo,  # exacta | parecida | nueva
        "tipeada": g.categoria,
        "comentario": g.comentario,
        "cuenta": g.cuenta,
    }


def _proponer_varios(
    conn: sqlite3.Connection, renglones: list[str], user_id: int, wid: int,
    ahora: datetime, hoy: date,
) -> Respuesta:
    """Varios renglones → propuesta numerada. **No escribe nada** hasta el `ok`."""
    gastos, errores = [], []
    for i, renglon in enumerate(renglones, 1):
        try:
            gastos.append(parsear_gasto(renglon, hoy))
        except EntradaInvalida as e:
            errores.append(f"  {i}. «{renglon}»: {e}")
    if errores:
        return Respuesta(
            "⚠️ No entendí estos renglones:\n" + "\n".join(errores)
            + "\n\nNo cargué nada. Corregilos y mandá el mensaje de nuevo.", "rechazado")

    existentes = all_motivos(conn, user_id=user_id)
    propuesta = {"items": [_item_de_gasto(g, existentes) for g in gastos]}
    habia_otra = lotes.proponer(conn, workspace_id=wid, user_id=user_id, origen="whatsapp",
                                propuesta=propuesta, ahora=ahora)
    texto = _texto_propuesta(propuesta["items"], hoy)
    if habia_otra:
        texto = "(Descarté la propuesta anterior, que no habías confirmado.)\n\n" + texto
    return Respuesta(texto, "pendiente")


def _texto_propuesta(items: list[dict], hoy: date) -> str:
    lineas = [f"Te cargo {len(items)}:"]
    for i, it in enumerate(items, 1):
        signo = "+" if it["es_ingreso"] else ""
        linea = (f"{i}. {it['categoria']} {signo}{pesos(it['monto'])} "
                 f"({_fecha_corta(date.fromisoformat(it['fecha']), hoy)})")
        if it.get("cuenta"):
            linea += f" = {it['cuenta']}"
        if it["es_ingreso"]:
            linea += " — ingreso"
        if it["tipo"] == "parecida":
            linea += f"  ← ¿quisiste decir? (escribiste «{it['tipeada']}»)"
        elif it["tipo"] == "nueva":
            linea += "  ← categoría nueva"
        if it.get("comentario"):
            linea += f" · {it['comentario']}"
        lineas.append(linea)
    lineas.append(_totales(items))
    lineas.append("\n¿Va? Contestá *ok*. Para corregir antes: *2 transportes* · "
                  "*2 no* (lo saco) · *cancelar*")
    return "\n".join(lineas)


def _totales(items: list[dict]) -> str:
    gastos = sum(it["monto"] for it in items if not it["es_ingreso"])
    ingresos = sum(it["monto"] for it in items if it["es_ingreso"])
    partes = []
    if gastos:
        partes.append(f"gastos {pesos(gastos)}")
    if ingresos:
        partes.append(f"ingresos {pesos(ingresos)}")
    return "Total: " + " · ".join(partes)


def _responder_lote(
    conn: sqlite3.Connection, lote: lotes.Lote, r: RespuestaLote, user_id: int,
    ahora: datetime, hoy: date,
) -> Respuesta:
    if r.cancelar:
        lotes.descartar(conn, lote.id)
        return Respuesta("Listo, descarté la propuesta: no cargué nada.", "rechazado")

    items = [dict(it) for it in lote.propuesta["items"]]
    sacar: set[int] = set()
    dudosa = False  # una corrección que no es exacta se muestra antes de cargar
    if r.correcciones:
        existentes = all_motivos(conn, user_id=user_id)
        for n, que in r.correcciones:
            if normalizar(que) in {"no", "sacar", "saca", "sacalo"}:
                sacar.add(n)
                continue
            tipo, nombre = resolver_categoria(que, existentes)
            items[n - 1].update(categoria=nombre if tipo != "nueva" else _capitalizar(que),
                                tipo=tipo, tipeada=que)
            dudosa = dudosa or tipo != "exacta"
    items = [it for i, it in enumerate(items, 1) if i not in sacar]
    if not items:
        lotes.descartar(conn, lote.id)
        return Respuesta("Sacaste todos: no cargué nada.", "rechazado")

    if r.correcciones:
        lotes.actualizar(conn, lote.id, {**lote.propuesta, "items": items})
    if not r.aceptar or dudosa:
        aviso = "Revisá las marcadas y contestá *ok*.\n\n" if (r.aceptar and dudosa) else ""
        return Respuesta(aviso + _texto_propuesta(items, hoy), "pendiente")

    lotes.aplicar(conn, lote.id, [_movimiento(it) for it in items], user_id=user_id, ahora=ahora)
    totales = _totales(items).removeprefix("Total: ")
    if len(items) == 1:
        return Respuesta(f"✅ Cargado 1 ({totales}).\n*deshacer* lo borra.", "lote")
    return Respuesta(f"✅ Cargados {len(items)} ({totales}).\n*deshacer* borra los "
                     f"{len(items)}.", "lote")


def _responder_pendiente(
    conn: sqlite3.Connection, p: dict, acepta: bool, user_id: int, hoy: date
) -> Respuesta:
    _borrar_pendiente(conn)
    if not acepta:
        return Respuesta("Listo, no cargué nada. Mandalo de nuevo con la categoría que va.",
                         "rechazado")
    g = Gasto(fecha=date.fromisoformat(p["fecha"]), monto=float(p["monto"]),
              es_ingreso=bool(p["es_ingreso"]), categoria=p["categoria"],
              comentario=p.get("comentario"), cuenta=p.get("cuenta"))
    txn_id = _insertar(conn, g, g.categoria, user_id)
    return Respuesta(_confirmacion(txn_id, g, g.categoria, hoy), "cargado", txn_id)


def deshacer(conn: sqlite3.Connection, *, user_id: int, ahora: datetime) -> Respuesta:
    """Deshace **lo último** cargado por WhatsApp en las últimas 24 h.

    Lo último puede ser un gasto suelto o un lote (varios gastos confirmados
    juntos): un lote se deshace entero. Se comparan fechas, no textos.
    """
    desde = ahora - VENTANA_DESHACER
    row = conn.execute(
        "SELECT wamid, transaccion_id, recibido_en FROM whatsapp_mensajes "
        "WHERE transaccion_id IS NOT NULL AND resultado = 'cargado' AND recibido_en >= ? "
        "ORDER BY recibido_en DESC LIMIT 1",
        (desde.isoformat(),),
    ).fetchone()
    ultimo_lote = lotes.ultimo_aplicado(
        conn, workspace_id=resolve_workspace_id(conn, user_id), desde=desde)
    if ultimo_lote and (row is None
                        or ultimo_lote[1] >= datetime.fromisoformat(row["recibido_en"])):
        return _deshacer_lote(conn, ultimo_lote[0], ahora)
    if row is None:
        return Respuesta("No hay nada cargado por WhatsApp en las últimas 24 h para deshacer.",
                         "rechazado")
    txn = get_transaction(conn, row["transaccion_id"], user_id=user_id)
    if txn is None:
        conn.execute("UPDATE whatsapp_mensajes SET resultado = 'deshecho' WHERE wamid = ?",
                     (row["wamid"],))
        return Respuesta("Esa carga ya no existe (¿la borraste desde la app?).", "rechazado")
    delete_transaction(conn, txn["id"], user_id=user_id)
    conn.execute("UPDATE whatsapp_mensajes SET resultado = 'deshecho' WHERE wamid = ?",
                 (row["wamid"],))
    monto = txn["ingresos"] or txn["pasivos"]
    return Respuesta(
        f"↩️ Borré #{txn['id']}: {pesos(monto)} en {txn['motivo']} "
        f"({date.fromisoformat(txn['fecha']):%d/%m})",
        "deshecho",
    )


def _deshacer_lote(conn: sqlite3.Connection, lote_id: int, ahora: datetime) -> Respuesta:
    try:
        d = lotes.deshacer(conn, lote_id, ahora=ahora)
    except lotes.LoteNoDeshacible as e:
        return Respuesta(f"⚠️ No puedo deshacer los gastos que cargaste juntos: {e}. "
                         "No toqué nada; corregilo desde la app.", "rechazado")
    if not d.borradas and not d.restauradas:
        return Respuesta("↩️ Deshice lo último que confirmaste. No había cargado gastos: "
                         "solo lo que anoté del banco.", "deshecho")
    if len(d.borradas) > 1:
        lineas = [f"↩️ Borré los {len(d.borradas)} que cargaste juntos:"]
    elif d.borradas:
        lineas = ["↩️ Borré el que cargaste:"]
    else:
        lineas = ["↩️ Deshice lo último que confirmaste."]
    for b in d.borradas:
        monto = b["ingresos"] or b["pasivos"]
        lineas.append(f"  #{b['id']}: {pesos(monto)} en {b['motivo']} "
                      f"({date.fromisoformat(b['fecha']):%d/%m})")
    if d.restauradas:
        lineas.append(f"Y volví a como estaban {d.restauradas} gasto(s) que había corregido "
                      "con el monto del banco.")
    return Respuesta("\n".join(lineas), "deshecho")


@dataclass
class TotalesMes:
    gastos: float
    ingresos: float
    movimientos: int
    sin_categorizar: float


def totales_mes(
    conn: sqlite3.Connection, *, user_id: int, hoy: date, hasta_dia: Optional[int] = None
) -> Optional[TotalesMes]:
    """Totales del mes con la **misma fórmula que el dashboard**. None si no hay movimientos.

    `hasta_dia` corta el mes en ese día (inclusive): sirve para comparar el
    mes en curso contra **el mismo período** del anterior, no contra el mes
    entero (el 17/10, octubre lleva 17 días y septiembre 30).

    "Gastos" = Gasto Fijo + Gasto Variable (no cuenta la Compra Divisa, que es
    ahorro). Esa fórmula deja afuera "Sin categorizar", que es justo donde
    caen las categorías nuevas creadas desde WhatsApp: por eso va aparte, para
    que ningún peso desaparezca. Lo usan `resumen` y el briefing (Fase B).
    """
    df = load_transactions(conn, user_id=user_id)
    if df.empty:
        return None
    cats = load_categorias_full(conn, user_id=user_id)
    del_mes = df[(df["fecha"].dt.year == hoy.year) & (df["fecha"].dt.month == hoy.month)]
    if hasta_dia is not None:
        del_mes = del_mes[del_mes["fecha"].dt.day <= hasta_dia]
    if del_mes.empty:
        # Hay movimientos, pero no en este mes (el 1° antes de cargar nada, o
        # el período previo vacío). Sin esto, el filtro de "sin categorizar"
        # sobre una tabla vacía tiraba KeyError: 'pasivos' (17/10/2026).
        return TotalesMes(gastos=0.0, ingresos=0.0, movimientos=0, sin_categorizar=0.0)
    tabla = ingresos_vs_gastos_mensual(del_mes, cats)
    return TotalesMes(
        gastos=float(tabla["gastos"].sum()) if not tabla.empty else 0.0,
        ingresos=float(tabla["ingresos"].sum()) if not tabla.empty else 0.0,
        movimientos=len(del_mes),
        sin_categorizar=float(del_mes[
            del_mes["motivo"].map(lambda m: cats.get(m, ("Sin categorizar",))[0] == "Sin categorizar")
        ]["pasivos"].sum()),
    )


def resumen_mes(conn: sqlite3.Connection, *, user_id: int, hoy: date) -> str:
    """Respuesta al comando `resumen`: totales del mes + últimos 5 movimientos."""
    titulo = f"*📊 {hoy:%m/%Y}*"
    t = totales_mes(conn, user_id=user_id, hoy=hoy)
    if t is None:
        return f"{titulo}\nTodavía no hay movimientos."

    lineas = [
        titulo,
        f"Gastos: {pesos(t.gastos)}",
        f"Ingresos: {pesos(t.ingresos)}",
        f"Movimientos: {t.movimientos}",
    ]
    if t.sin_categorizar:
        lineas.append(f"Sin categorizar: {pesos(t.sin_categorizar)} (asignales grupo en Configuración)")

    ultimas = list_recent(conn, 5, user_id=user_id)
    if ultimas:
        lineas.append("\n*Últimos movimientos*")
        for t in ultimas:
            signo = "+" if t["ingresos"] else ""
            monto = t["ingresos"] or t["pasivos"]
            lineas.append(
                f"  {date.fromisoformat(t['fecha']):%d/%m} {signo}{pesos(monto)} {t['motivo']}"
            )
    return "\n".join(lineas)
