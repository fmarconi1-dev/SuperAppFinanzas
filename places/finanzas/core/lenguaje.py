"""Lenguaje natural en el Secretario (Fase E, ADR-0012): Gemini traduce, el código decide.

Cuando `comandos.procesar` no entiende un mensaje (o lo entiende con una
categoría nueva, la señal medida de que leyó mal: «5000 en el chino»), se le
pide a Gemini **la orden en la gramática de siempre**. Esa orden:

* se valida contra los mismos parsers (`clasificar`): si no es una orden que
  el bot entiende, se descarta y Franco recibe la respuesta de siempre;
* si **escribe** algo (un gasto, un `ok`, un `deshacer`, un evento), no corre:
  se le muestra a Franco («Entendí: …») y corre solo con su *sí* (un
  `pendiente` de tipo `traduccion`, que vence a los 10 minutos);
* si solo **consulta** (`resumen`, `agenda`, `ayuda`), corre directo.

Gemini también puede repreguntar (falta un dato) o contestar una duda sobre la
propuesta abierta, solo con lo que dice el contexto. Si no contesta, se dice.
El cliente llega inyectado (`traductor`): acá no hay red.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

from core.api.gemini import GeminiNoDisponible
from places.finanzas.core import agenda as ag
from places.finanzas.core import lotes, saldos
from places.finanzas.core.comandos import (
    AYUDA,
    EntradaInvalida,
    Respuesta,
    _RE_COMANDO_AGENDA,
    _borrar_pendiente,
    _cantidad,
    _leer_respuesta_lote,
    _texto_propuesta,
    guardar_estado,
    normalizar,
    parsear_gasto,
)
from places.finanzas.core.transactions import all_motivos

#: Órdenes que solo leen: corren sin pedir el *sí*.
CONSULTAS = {"resumen", "saldo", "agenda", "semana", "ayuda", "help", "comandos",
             "balances todas", "balances todos"}

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

_CORRECCIONES = (
    "Correcciones a una propuesta abierta (por número de renglón, separadas por coma): "
    "N categoría · N no (no se carga) · N es ID (es ese gasto ya cargado) · "
    "N efectivo / N tarjeta (para lo que sobra) · ok (acepta) · cancelar (descarta)."
)

#: Dónde pone Franco lo que Gemini no puede adivinar (Franco, 4/11/2026, después
#: de la prueba en Fly: la nafta iba a Transportes y la farmacia a Otros ingresos).
PISTAS = (
    "Auto: nafta, peaje, seguro del auto, service, estacionamiento.",
    "Compras: súper, chino, farmacia, ferretería.",
    "Impuestos: comisiones y gastos del banco, IVA, percepciones.",
)

#: Palabras con las que Franco acepta una propuesta en el mismo mensaje. Sin una
#: de estas, un "ok" que agrega Gemini se saca: con el *sí* a la traducción se
#: aplicaría la conciliación entera (prueba en Fly del 4/11: «el del mecánico
#: ponelo en auto» → «4 auto, ok»). "va" no está: «la ferretería va en compras».
_ACEPTA = {"dale", "ok", "okay", "listo", "confirmo", "acepto", "aceptalo", "aplicalo",
           "aplica", "cargalo", "cargalos", "correcto", "perfecto"}


def _sin_ok_no_pedido(orden: str, texto: str, cantidad: int) -> Optional[str]:
    """La orden sin el `ok` final si Franco no aceptó en su mensaje (None si no queda nada)."""
    r = _leer_respuesta_lote(orden, cantidad) if cantidad else None
    if r is None or not r.aceptar or set(re.findall(r"[a-z]+", normalizar(texto))) & _ACEPTA:
        return orden
    if not r.correcciones:
        return None
    return ", ".join(f"{n} {que}" for n, que in r.correcciones)


# -- ¿Qué renglones nombró Franco? (segunda corrida en Fly, 4/11/2026: «el profe es
# salidas, el mecánico auto y el resto como dijiste, dale» → Gemini les inventó
# categoría a los renglones que no nombró). Una corrección solo vale para un renglón
# que el mensaje nombra: por número, por una palabra que solo está en ese renglón
# (el comercio o la persona), por el monto o por la fecha.

_RE_RENGLON = re.compile(r"^\s*(\d{1,3})\.\s+(.*)$")
_RE_MONTO_RENGLON = re.compile(r"\$([\d.]+(?:,\d+)?)")
_RE_MONTO_MENSAJE = re.compile(
    r"(\d+(?:[.,]\d+)*)\s*(mil|k|lucas?|palos?|millon(?:es)?)?(?![\w/])")
_MULTIPLICADOR = {"mil": 1_000, "k": 1_000, "luca": 1_000, "lucas": 1_000, "palo": 1_000_000,
                  "palos": 1_000_000, "millon": 1_000_000, "millones": 1_000_000}


def _monto(crudo: str, unidad: Optional[str] = None) -> Optional[float]:
    """"81.070" → 81070 · "2,4" + "palos" → 2.400.000 · "23.800,50" → 23800,5."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", crudo) or "," in crudo:
        crudo = crudo.replace(".", "").replace(",", ".")
    try:
        valor = float(crudo)
    except ValueError:
        return None
    return valor * _MULTIPLICADOR.get(unidad or "", 1)


def _renglones(texto_propuesta: str) -> dict[int, str]:
    """{número: lo que dice el renglón, sin la categoría propuesta (lo de después de →)}."""
    salida = {}
    for linea in texto_propuesta.splitlines():
        if m := _RE_RENGLON.match(linea):
            salida[int(m.group(1))] = m.group(2).split("→")[0]
    return salida


def _nombrados(texto: str, texto_propuesta: str, categorias: list[str]) -> set[int]:
    """Los renglones de la propuesta que nombra el mensaje de Franco."""
    renglones = _renglones(texto_propuesta)
    mensaje = normalizar(texto)
    palabras_msj = {w for w in re.findall(r"[a-z]+", mensaje) if len(w) >= 4}
    numeros_msj = {int(n) for n in re.findall(r"(?<![\d.,/])(\d{1,3})(?![\d.,/])", mensaje)}
    # Un monto de menos de $100 es un número de renglón ("el 4"), no un monto.
    montos_msj = [v for c, u in _RE_MONTO_MENSAJE.findall(mensaje)
                  if (v := _monto(c, u)) and v >= 100]
    # En el tipo de movimiento (lo de antes de "·"), las palabras de las categorías no
    # distinguen renglones: "compras" no nombra al de "Compra Debito", ni "auto" al de
    # "Autoservicio". En el comercio o la persona sí ("FUNDACION …").
    de_categorias = {w for c in categorias for w in re.findall(r"[a-z]+", normalizar(c))}

    def del_tipo(w: str) -> bool:
        return not any(c.startswith(w) or w.startswith(c) for c in de_categorias if len(c) >= 4)

    def palabras_de(linea: str) -> set[str]:
        tipo, _, comercio = normalizar(linea).partition("·")
        return ({w for w in re.findall(r"[a-z]+", tipo) if len(w) >= 4 and del_tipo(w)}
                | {w for w in re.findall(r"[a-z]+", comercio) if len(w) >= 4})

    palabras = {n: palabras_de(t) for n, t in renglones.items()}
    # Solo las palabras que distinguen un renglón: "transferencia" está en varios.
    cuantas: dict[str, int] = {}
    for ws in palabras.values():
        for w in ws:
            cuantas[w] = cuantas.get(w, 0) + 1
    nombrados = set()
    for n, linea in renglones.items():
        propias = {w for w in palabras[n] if cuantas[w] == 1}
        por_palabra = any(p == m or (len(m) >= 5 and (p.startswith(m) or m.startswith(p)))
                          for p in propias for m in palabras_msj)
        montos = [v for c in _RE_MONTO_RENGLON.findall(linea) if (v := _monto(c))]
        por_monto = any(abs(a - b) <= a * 0.03 for a in montos for b in montos_msj)
        por_fecha = any(f in mensaje for f in re.findall(r"\b\d{2}/\d{2}\b", linea))
        if n in numeros_msj or por_palabra or por_monto or por_fecha:
            nombrados.add(n)
    return nombrados


def _solo_lo_nombrado(orden: str, texto: str, texto_propuesta: str, cantidad: int,
                      categorias: list[str]) -> Optional[str]:
    """La orden sin las correcciones a renglones que Franco no nombró (None si no queda nada)."""
    r = _leer_respuesta_lote(orden, cantidad) if cantidad else None
    if r is None or not r.correcciones:
        return orden
    nombrados = _nombrados(texto, texto_propuesta, categorias)
    quedan = [(n, que) for n, que in r.correcciones if n in nombrados]
    if len(quedan) == len(r.correcciones):
        return orden
    if not quedan and not r.aceptar:
        return None
    return ", ".join([f"{n} {que}" for n, que in quedan] + (["ok"] if r.aceptar else []))


def _signo_cruzado(conn: sqlite3.Connection, orden: str, *, hoy: date, wid: int,
                   motivos: list[str]) -> bool:
    """¿Algún gasto traducido tiene el signo al revés de su categoría?

    Tercera corrida en Fly (4/11/2026): «compré dólares por 1.200.000» →
    «+1200000, Compra Divisa». Un ingreso en una categoría que no es de ingresos
    (o un gasto en una que sí) se descarta: escrito a mano puede ser una
    devolución, pero traducido es un error de Gemini. "Inversiones" va en los dos
    sentidos (un ingreso es un rescate).
    """
    from places.finanzas.core.categorizer import MOTIVOS_DUAL_DESAHORRO
    from places.finanzas.core.comandos import resolver_categoria

    renglones = [r for r in orden.splitlines() if r.strip()]
    if not renglones or any("," not in r for r in renglones):
        return False
    for renglon in renglones:
        try:
            g = parsear_gasto(renglon, hoy)
        except EntradaInvalida:
            return False
        tipo, nombre = resolver_categoria(g.categoria, motivos)
        if tipo == "nueva" or nombre in MOTIVOS_DUAL_DESAHORRO:
            continue
        fila = conn.execute("SELECT grupo FROM categorias WHERE motivo = ? AND workspace_id = ?",
                            (nombre, wid)).fetchone()
        if fila and fila["grupo"] and g.es_ingreso != (fila["grupo"] == "Ingreso"):
            return True
    return False


#: Lo cargado que ve Gemini para corregirlo por chat (Franco, 6/11/2026: 60 días).
DIAS_CARGADOS = 60
TOPE_CARGADOS = 150


def _filas_cargadas(conn: sqlite3.Connection, wid: int, hoy: date) -> list:
    return conn.execute(
        "SELECT t.id, t.fecha, t.motivo, t.pasivos, t.ingresos, t.comentario, gc.cuenta "
        "FROM transacciones t LEFT JOIN gasto_cuentas gc ON gc.transaccion_id = t.id "
        "WHERE t.workspace_id = ? AND t.fecha >= ? ORDER BY t.fecha DESC, t.id DESC LIMIT ?",
        (wid, (hoy - timedelta(days=DIAS_CARGADOS)).isoformat(), TOPE_CARGADOS)).fetchall()


def _cargados(conn: sqlite3.Connection, wid: int, hoy: date) -> str:
    """Lo cargado en los últimos `DIAS_CARGADOS` días, con su número, para `#N fecha …`."""
    from places.finanzas.core.comandos import pesos

    lineas = []
    for f in _filas_cargadas(conn, wid, hoy):
        monto = f["ingresos"] or f["pasivos"]
        linea = (f"#{f['id']} {date.fromisoformat(f['fecha']):%d/%m} {f['motivo']} "
                 f"{'+' if f['ingresos'] else ''}{pesos(monto)}")
        if f["cuenta"]:
            linea += f" (= {f['cuenta']})"
        if f["comentario"]:
            linea += f" · {f['comentario']}"
        lineas.append(linea)
    return "\n".join(lineas)


def contexto(conn: sqlite3.Connection, *, user_id: int, wid: int, hoy: date,
             ahora: datetime, charla: Optional[list] = None) -> str:
    """Lo que Gemini necesita para traducir: hoy, la gramática, las categorías, lo
    cargado (60 días), la propuesta abierta tal como la ve Franco y, en modo Gemini,
    la charla reciente (ADR-0012)."""
    partes = [
        f"Hoy: {_DIAS[hoy.weekday()]} {hoy:%d/%m/%Y} (Buenos Aires).",
        "GRAMÁTICA DEL BOT\n" + AYUDA + "\n" + _CORRECCIONES,
        "CATEGORÍAS EXISTENTES\n" + ", ".join(sorted(set(all_motivos(conn, user_id=user_id)))),
        "DÓNDE VA CADA COSA (así categoriza Franco)\n" + "\n".join(PISTAS),
    ]
    if cargados := _cargados(conn, wid, hoy):
        partes.append(f"LO CARGADO EN LOS ÚLTIMOS {DIAS_CARGADOS} DÍAS (para corregir algo, "
                      "nombralo con su #número)\n" + cargados)
    lote = lotes.vigente(conn, workspace_id=wid, ahora=ahora)
    if lote:
        partes.append("PROPUESTA ABIERTA (lo que Franco tiene en pantalla)\n"
                      + _texto_de_propuesta(lote.propuesta, hoy))
    if charla:
        partes.append("CHARLA RECIENTE (lo último que hablaron, del más viejo al más nuevo)\n"
                      + "\n".join(f"Franco: {c['franco']}\nSecretario: {c['secretario']}"
                                  for c in charla))
    return "\n\n".join(partes)


def _texto_de_propuesta(prop: dict, hoy: date) -> str:
    from places.finanzas.core import conciliacion, fotos, tarjetas  # diferido: usan comandos

    tipo = prop.get("tipo")
    if tipo == "extracto":
        return conciliacion.texto_propuesta(prop, nuevo_ancla=bool(prop.get("ancla")))
    if tipo == "resumen":
        return tarjetas.texto(prop)
    if tipo == "foto":
        return fotos.texto(prop)
    if tipo == "saldos":
        return saldos.texto(prop)
    return _texto_propuesta(prop["items"], hoy)


def clasificar(orden: str, *, hoy: date, cantidad: int) -> Optional[str]:
    """'consulta' (solo lee), 'escribe' (pide el *sí*), 'propone' (pide el *sí* y arma
    una propuesta nueva: varios gastos o saldos) o None si el bot no la entiende.

    `cantidad`: los renglones de la propuesta abierta (0 si no hay). Se valida
    con los mismos parsers que usa `procesar`, sin tocar la base.
    """
    clave = normalizar(orden).strip(" .!¡?¿")
    if not clave:
        return None
    if clave in CONSULTAS:
        return "consulta"
    if clave in {"deshacer", "borrar ultimo", "borra ultimo"}:
        return "escribe"
    if clave == "balances" or clave.startswith("balances "):
        return "escribe"
    if m := _RE_COMANDO_AGENDA.match(orden):
        comando = m.group(1).lower()
        try:
            if comando == "evento":
                ag.parsear_evento(m.group(2), hoy)
            else:
                ag.parsear_tarea(m.group(2), hoy)
        except ag.AgendaInvalida:
            return None
        return "escribe"
    if cantidad and _leer_respuesta_lote(orden, cantidad):
        return "escribe"
    from places.finanzas.core import ediciones  # diferido: ediciones usa comandos

    try:
        if ediciones.parsear(orden, hoy) is not None:     # #505 fecha 02/11 · partir #511 …
            return "escribe"
        if saldos.parsear(orden, hoy):
            return "propone"
    except EntradaInvalida:
        return None
    # Un gasto traducido va con coma ("5000, compras"). Sin coma, "9 salidas" es
    # una corrección a un renglón que no existe, no un gasto de $9.
    renglones = [r.strip() for r in orden.splitlines() if r.strip()]
    try:
        for renglon in renglones:
            if "," not in renglon:
                return None
            parsear_gasto(renglon, hoy)
    except EntradaInvalida:
        return None
    return "propone" if len(renglones) >= 2 else "escribe"


def lo_entiende_el_parser(conn: sqlite3.Connection, texto: str, *, user_id: int, wid: int,
                          hoy: date, ahora: datetime) -> bool:
    """¿El mensaje ya está en la gramática, con categorías que existen? Sin tocar la base.

    En modo Gemini, eso va directo al parser (ADR-0012 §3: si el parser entiende
    bien, no se llama a nadie): Gemini no contesta siempre igual, y un «5000,
    compras» correcto no tiene por qué depender de él.
    """
    from places.finanzas.core.comandos import resolver_categoria

    lote = lotes.vigente(conn, workspace_id=wid, ahora=ahora)
    if clasificar(texto, hoy=hoy, cantidad=_cantidad(lote.propuesta) if lote else 0) is None:
        return False
    motivos = all_motivos(conn, user_id=user_id)
    for renglon in (r for r in texto.splitlines() if r.strip()):
        try:
            g = parsear_gasto(renglon, hoy)
        except EntradaInvalida:
            continue                      # no es un gasto: un comando, una corrección, …
        if resolver_categoria(g.categoria, motivos)[0] != "exacta":
            return False
    return True


def _misma_carga(orden: str, texto: str, hoy: date) -> bool:
    """¿La orden es lo mismo que ya había leído el parser? Entonces Gemini no ayudó."""
    if normalizar(orden) == normalizar(texto):
        return True
    try:
        a, b = parsear_gasto(orden, hoy), parsear_gasto(texto, hoy)
    except EntradaInvalida:
        return False
    return (a.fecha, a.monto, a.es_ingreso, normalizar(a.categoria)) == \
        (b.fecha, b.monto, b.es_ingreso, normalizar(b.categoria))


def entender(
    conn: sqlite3.Connection,
    texto: str,
    traductor: Any,
    *,
    respaldo: "Respuesta | Callable[[], Respuesta]",
    ejecutar: Callable[[str], Respuesta],
    user_id: int,
    wid: int,
    hoy: date,
    ahora: datetime,
    charla: Optional[list] = None,
) -> Respuesta:
    """Lo que se contesta con lo que entendió Gemini.

    `respaldo` es lo que contesta el parser: ya calculado (Gemini entra porque el
    parser no entendió) o una función que lo calcula (modo Gemini: el parser
    corre solo si Gemini no ayuda, así no carga nada antes de tiempo).
    `ejecutar(orden)` corre una orden con `procesar`, sin traductor (las
    consultas, que no piden *sí*). `charla`: lo último hablado, en modo Gemini.
    """
    calculado = respaldo if isinstance(respaldo, Respuesta) else None

    def de_siempre() -> Respuesta:
        nonlocal calculado
        if calculado is None:
            calculado = respaldo()
        return calculado

    def sin_pregunta_vieja() -> None:
        # Lo que el parser dejó pendiente («¿La creo?») ya no es la pregunta.
        if calculado is not None and calculado.resultado == "pendiente":
            _borrar_pendiente(conn)

    try:
        t = traductor.traducir(texto, contexto(conn, user_id=user_id, wid=wid, hoy=hoy,
                                               ahora=ahora, charla=charla))
    except GeminiNoDisponible as e:
        r = de_siempre()
        return Respuesta(r.texto + f"\n\n(Quise entenderlo con Gemini y no pude: {e}.)",
                         r.resultado, r.transaccion_id)

    if t.tipo in ("pregunta", "respuesta") and t.texto:
        sin_pregunta_vieja()
        return Respuesta("🤖 " + t.texto, "consulta")
    if t.tipo != "orden" or not t.orden or _misma_carga(t.orden, texto, hoy):
        return de_siempre()

    lote = lotes.vigente(conn, workspace_id=wid, ahora=ahora)
    cantidad = _cantidad(lote.propuesta) if lote else 0
    orden = _sin_ok_no_pedido(t.orden, texto, cantidad)
    if orden is not None and lote:
        orden = _solo_lo_nombrado(orden, texto, _texto_de_propuesta(lote.propuesta, hoy),
                                  cantidad, all_motivos(conn, user_id=user_id))
    if orden is None:
        return de_siempre()
    clase = clasificar(orden, hoy=hoy, cantidad=cantidad)
    if clase is None:
        return de_siempre()
    # El signo se mira solo en gastos: una corrección ("5 Haberes UCEMA, 6 …") también
    # se lee como un gasto de $5, y se descartaba (cuarta corrida en Fly, 4/11/2026).
    es_correccion = bool(cantidad) and _leer_respuesta_lote(orden, cantidad) is not None
    if not es_correccion and _signo_cruzado(conn, orden, hoy=hoy, wid=wid,
                                            motivos=all_motivos(conn, user_id=user_id)):
        return de_siempre()
    if clase == "propone" and lote:
        # Varios gastos o saldos arman una propuesta nueva y tirarían la abierta (la
        # conciliación que Franco está revisando). Eso no se hace por una traducción.
        sin_pregunta_vieja()
        return Respuesta(f"🤖 Entendí:\n{orden}\n\nPero eso reemplazaría la propuesta que "
                         "tenés abierta. Terminala (*ok*) o descartala (*cancelar*) y "
                         "mandalo de nuevo.", "rechazado")
    if clase == "consulta":
        sin_pregunta_vieja()
        r = ejecutar(orden)
        return Respuesta(f"🤖 Entendí: *{orden}*\n\n{r.texto}", r.resultado, r.transaccion_id)

    entendi = f"🤖 Entendí:\n{orden}"
    from places.finanzas.core import ediciones  # diferido: ediciones usa comandos

    if (edicion := ediciones.parsear(orden, hoy)) is not None:
        # Solo un número que Gemini vio en LO CARGADO: uno inventado tocaría otro gasto.
        if edicion.txn_id not in {f["id"] for f in _filas_cargadas(conn, wid, hoy)}:
            return de_siempre()
        try:
            # «#505» solo no dice qué es: el *sí* tiene que ver el gasto entero.
            entendi = f"🤖 Entendí: {ediciones.explicar(conn, edicion, wid=wid, hoy=hoy)}."
        except EntradaInvalida as e:
            sin_pregunta_vieja()
            return Respuesta(f"🤖 {e} No cambié nada.", "rechazado")

    guardar_estado(conn, "pendiente", json.dumps({
        "tipo": "traduccion", "orden": orden, "mensaje": texto,
        "creado_en": ahora.isoformat(),
    }), ahora)
    return Respuesta(f"{entendi}\n\n¿Va? Respondé *sí* o *no*.", "pendiente")
