"""Prueba de costo cero: ¿Meta deja mandar texto libre sin medio de pago?

Se corre UNA vez, en la PC de Franco, después de la Parte 1 de
`docs/WHATSAPP-CANAL.md`. Responde la única duda abierta de ADR-0008 antes
de escribir la Fase A.

Uso (con el Python del venv):

    .venv\\Scripts\\python.exe scripts\\probar_whatsapp_texto.py

El token temporal del panel de Meta ("Generar token de acceso") se **lee del
portapapeles**: lo copiás con el botón del panel y apretás Enter. Pegarlo a
mano en un campo oculto no anda en la consola de Windows (Ctrl+V llega como
basura y Meta contesta 190), y así además no queda en pantalla ni en el
historial. Después pide el Phone number ID y tu número. Los tres también se
toman de WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID y WHATSAPP_NUMERO_AUTORIZADO
si están definidas.

**Antes de correrlo:** mandale "hola" al número de prueba desde tu WhatsApp.
Eso abre la ventana de 24 h; sin ella Meta rechaza el texto (131047) y la
prueba no dice nada.

Solo manda `"type": "text"`. No sabe mandar plantillas: nada de lo que hace
este script puede generar un cobro.
"""

from __future__ import annotations

import getpass
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v23.0")

# Qué significa cada código de error de Meta para esta prueba en particular.
DIAGNOSTICOS = {
    131042: ("BLOQUEADO POR PAGO",
             "Meta NO deja mandar texto libre sin medio de pago. No cargues tarjeta: "
             "pasamos al plan B (Telegram)."),
    131047: ("VENTANA CERRADA",
             "Pasaron más de 24 h desde tu último mensaje al bot (o nunca le escribiste). "
             "Mandale 'hola' desde tu WhatsApp y corré el script de nuevo."),
    131030: ("NÚMERO NO AUTORIZADO",
             "Tu número no está en la lista de destinatarios. Un celular argentino va en "
             "la lista del panel CON el 9 (+54 9 11 …), pero acá se manda SIN el 9 "
             "(54 11 …): así lo acepta y lo entrega Meta (comprobado el 15/10)."),
    190: ("TOKEN VENCIDO O INVÁLIDO",
          "El token temporal dura poco. Generá uno nuevo en el panel y reintentá."),
    100: ("PARÁMETRO INVÁLIDO",
          "Revisá el Phone number ID (es el del número de prueba, no el de la cuenta)."),
}


def digitos(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def pedir(var: str, texto: str, secreto: bool = False) -> str:
    valor = os.environ.get(var, "").strip()
    if valor:
        return valor
    valor = (getpass.getpass(texto) if secreto else input(texto)).strip()
    if not valor:
        sys.exit(f"Falta {var}.")
    return valor


def parece_token(s: str) -> bool:
    """Los tokens de acceso de Meta empiezan con EAA y son largos, sin espacios."""
    return s.startswith("EAA") and len(s) >= 50 and not any(c.isspace() for c in s)


def leer_portapapeles() -> str:
    """Texto del portapapeles de Windows, o "" si no se pudo leer."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"No pude leer el portapapeles: {e}")
        return ""
    return (r.stdout or "").strip()


def pedir_token() -> str:
    valor = os.environ.get("WHATSAPP_TOKEN", "").strip()
    if valor:
        return valor
    while True:
        input('Copiá el token con el botón "Copiar" del panel de Meta y apretá Enter acá... ')
        valor = leer_portapapeles()
        if parece_token(valor):
            # Solo el principio y el largo: alcanza para confirmar que es el
            # token nuevo sin dejarlo entero en pantalla.
            print(f"Token leído: {valor[:6]}… ({len(valor)} caracteres)")
            return valor
        print("Lo que hay en el portapapeles no parece un token de Meta (empiezan con EAA). "
              "Copialo de nuevo desde el panel.")


def armar_pedido(phone_number_id: str, token: str, destino: str, texto: str) -> urllib.request.Request:
    cuerpo = {
        "messaging_product": "whatsapp",
        "to": destino,
        "type": "text",
        "text": {"body": texto},
    }
    return urllib.request.Request(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{phone_number_id}/messages",
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )


def diagnosticar(estado: int, respuesta: dict) -> tuple[bool, str]:
    """(salió_bien, explicación) a partir de lo que devolvió Meta."""
    if estado == 200 and respuesta.get("messages"):
        return True, (
            "ACEPTADO: Meta tomó el pedido sin medio de pago. OJO: aceptar no es entregar. "
            "Si la entrega falla (ventana cerrada, número equivocado, pago), Meta lo avisa "
            "después por el webhook, no acá. Fijate si el mensaje te llegó al WhatsApp."
        )
    error = respuesta.get("error", {})
    codigo = error.get("code")
    titulo, consejo = DIAGNOSTICOS.get(codigo, ("ERROR NO PREVISTO", "Pasale este resultado a Claude."))
    detalle = error.get("message", "")
    datos = error.get("error_data", {}).get("details", "")
    return False, f"{titulo} (código {codigo}): {consejo}\n  Meta dijo: {detalle} {datos}".rstrip()


def main() -> int:
    # La consola de PowerShell 5.1 no es UTF-8: sin esto, un acento o el ✅
    # revientan el print con UnicodeEncodeError.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(__doc__.split("\n\n")[0])
    print()
    token = pedir_token()
    phone_number_id = digitos(pedir("WHATSAPP_PHONE_NUMBER_ID", "Phone number ID: "))
    destino = digitos(pedir("WHATSAPP_NUMERO_AUTORIZADO", "Tu número (549 + área + número): "))

    # En la lista del panel el celular va CON el 9; para mandar, Meta lo
    # quiere SIN el 9 (a 549… responde 131030). Comprobado el 15/10/2026.
    numero = "54" + destino[3:] if destino.startswith("549") and len(destino) == 13 else destino
    if numero != destino:
        print(f"\nMando a {numero} (sin el 9): así lo acepta Meta. En la lista del panel "
              "tu número tiene que estar CON el 9.")
    texto = "✅ Prueba de la SuperApp: si leés esto, Meta deja mandar texto sin tarjeta."
    try:
        estado, respuesta = enviar(phone_number_id, token, numero, texto)
    except urllib.error.URLError as e:
        print(f"No se pudo conectar con Meta: {e.reason}")
        return 2

    ok, explicacion = diagnosticar(estado, respuesta)
    print(f"\nHTTP {estado}\n{explicacion}")
    if ok:
        # Dato para la Fase A: en qué formato hay que mandarle a Franco.
        print(f"\nNúmero al que se mandó: {numero}")
        # `wa_id` es la cuenta de WhatsApp a la que Meta resolvió el número.
        # Si no coincide con la tuya (549…), el mensaje fue a parar a otra
        # parte y nunca te va a llegar.
        for c in respuesta.get("contacts") or []:
            print(f"Meta lo resolvió a la cuenta de WhatsApp: {c.get('wa_id')} "
                  f"(pedido: {c.get('input')})  ← también pasale esto")
        for m in respuesta.get("messages") or []:
            if m.get("message_status"):
                print(f"Estado inicial del mensaje: {m['message_status']}")
    return 0 if ok else 1


def enviar(phone_number_id: str, token: str, destino: str, texto: str) -> tuple[int, dict]:
    pedido = armar_pedido(phone_number_id, token, destino, texto)
    try:
        with urllib.request.urlopen(pedido, timeout=20) as r:
            estado, cuerpo = r.status, r.read()
    except urllib.error.HTTPError as e:
        estado, cuerpo = e.code, e.read()
    try:
        respuesta = json.loads(cuerpo or b"{}")
    except json.JSONDecodeError:
        respuesta = {"error": {"message": cuerpo[:300].decode("utf-8", "replace")}}
    return estado, respuesta


if __name__ == "__main__":
    sys.exit(main())
