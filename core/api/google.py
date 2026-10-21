"""Cliente del Apps Script de agenda (Fase B, ADR-0008): Calendar y Tasks.

La SuperApp no habla con Google directamente (eso exigiría OAuth y guardar
tokens): le pide al Apps Script de Franco, publicado como aplicación web, que
cree eventos y tareas o que liste la semana. El contrato está en
`integraciones/google-apps-script/README.md`.

Tres cosas de Apps Script que este cliente resuelve:

* **El 302.** La URL `/exec` contesta un POST con una redirección a
  `script.googleusercontent.com`, que hay que seguir con **GET**. `urllib` lo
  hace solo (para 301/302/303 convierte el POST en GET sin cuerpo).
* **Siempre HTTP 200.** El resultado real es el campo `ok`: un `ok: false` es
  un error aunque el HTTP diga 200. Acá se convierte en `AgendaRechazo`.
* **El secreto va en el cuerpo** (Apps Script no expone los headers).

`id_solicitud` (el wamid del WhatsApp) viaja en lo que escribe: si Meta
reintenta el mensaje, el Apps Script devuelve el resultado anterior en vez de
crear el evento dos veces.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

TIMEOUT = 30  # Apps Script tarda 1–3 s, más el arranque en frío de Google


class AgendaNoDisponible(Exception):
    """No se pudo hablar con el Apps Script (red, timeout, respuesta rota)."""


class AgendaRechazo(Exception):
    """El Apps Script contestó `ok: false`. `codigo` es su campo `error`."""

    def __init__(self, codigo: str, detalle: str = ""):
        super().__init__(f"{codigo}: {detalle}" if detalle else codigo)
        self.codigo = codigo
        self.detalle = detalle


@dataclass(frozen=True)
class ClienteAgenda:
    url: str
    secreto: str

    @classmethod
    def desde_entorno(cls) -> Optional["ClienteAgenda"]:
        """El cliente, o None si falta alguna variable (la agenda queda apagada)."""
        url = os.environ.get("GOOGLE_WORKSPACE_WEBHOOK_URL", "").strip()
        secreto = os.environ.get("GOOGLE_WORKSPACE_SECRET", "").strip()
        if not url or not secreto:
            return None
        return cls(url=url, secreto=secreto)

    # -- acciones ------------------------------------------------------------

    def crear_evento(self, *, fecha: str, titulo: str, hora_inicio: Optional[str] = None,
                     hora_fin: Optional[str] = None, descripcion: Optional[str] = None,
                     id_solicitud: Optional[str] = None) -> dict:
        return self._pedir("crear_evento", id_solicitud, fecha=fecha, titulo=titulo,
                           hora_inicio=hora_inicio, hora_fin=hora_fin, descripcion=descripcion)

    def crear_tarea(self, *, titulo: str, fecha: Optional[str] = None,
                    descripcion: Optional[str] = None,
                    id_solicitud: Optional[str] = None) -> dict:
        return self._pedir("crear_tarea", id_solicitud, titulo=titulo, fecha=fecha,
                           descripcion=descripcion)

    def resumen_semana(self, *, desde: Optional[str] = None, hasta: Optional[str] = None) -> dict:
        return self._pedir("resumen_semana", None, desde=desde, hasta=hasta)

    def completar_tarea(self, *, lista_id: str, tarea_id: str,
                        id_solicitud: Optional[str] = None) -> dict:
        """Marca la tarea como hecha en Google Tasks (el tilde del Inicio)."""
        return self._pedir("completar_tarea", id_solicitud, lista_id=lista_id, tarea_id=tarea_id)

    def agendar_balances(self, *, eventos: list[dict]) -> dict:
        """Un evento 📊 de día entero por balance (ADR-0011).

        Cada evento: `clave` (`TICKER:AAAA-MM-DD`), `fecha`, `titulo`,
        `descripcion` y `momento` (`pre`, `post` o vacío). La clave queda como
        etiqueta del evento: si ya existe uno con esa clave ese día, no se crea
        otro (así un reintento no duplica, sin depender de `id_solicitud`).
        """
        return self._pedir("agendar_balances", None, eventos=eventos)

    def borrar_balances(self, *, claves: list[str]) -> dict:
        """Borra los eventos 📊 con esas claves. Los que ya no estaban se informan."""
        return self._pedir("borrar_balances", None, claves=claves)

    # -- transporte ----------------------------------------------------------

    def _pedir(self, accion: str, id_solicitud: Optional[str], **campos) -> dict:
        cuerpo = {"secreto": self.secreto, "accion": accion,
                  **{k: v for k, v in campos.items() if v is not None}}
        if id_solicitud:
            cuerpo["id_solicitud"] = id_solicitud
        pedido = urllib.request.Request(
            self.url, data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
                crudo = r.read()
        except urllib.error.HTTPError as e:
            raise AgendaNoDisponible(f"el Apps Script respondió HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise AgendaNoDisponible(f"no se pudo conectar con el Apps Script: {e}") from None
        try:
            datos = json.loads(crudo)
        except json.JSONDecodeError:
            # Suele ser la página de login de Google: la aplicación web no
            # está publicada con acceso "Cualquier persona".
            raise AgendaNoDisponible("el Apps Script no devolvió JSON "
                                     "(¿la aplicación web tiene acceso 'Cualquier persona'?)") from None
        if not isinstance(datos, dict) or datos.get("ok") is not True:
            d = datos if isinstance(datos, dict) else {}
            raise AgendaRechazo(str(d.get("error") or "sin_ok"), str(d.get("detalle") or ""))
        return datos
