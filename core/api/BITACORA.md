# core/api/

<!-- huella: 39ed4d8e4207 -->

Resumen: API HTTP stdlib de la SuperApp (Fase A, ADR-0008): servidor con el webhook de WhatsApp firmado por Meta, dedupe y cola de trabajo, más el canal de Meta (único módulo que le habla).

## Buscar acá si

- el bot no contesta, contesta dos veces o un mensaje "se perdió" → `servidor.py` (firma, remitente, dedupe por wamid, cola, `resultado` en `whatsapp_mensajes`)
- Meta rechaza un envío o aparece un código 131xxx en `fly logs` → `whatsapp_meta.py` (`CanalNoDisponible` con el código; un 131030 dice que el número del panel tiene que ir con el 9)
- configurar el webhook en el panel de Meta (verify token, `hub.challenge`) → `servidor.py` + `docs/WHATSAPP-CANAL.md`
- qué variables de entorno hacen falta → `ConfigWhatsApp.desde_entorno` (y `.env.example`)
- la interpretación del texto (montos, categorías, `resumen`, `deshacer`) → **no es acá**: `places/finanzas/core/comandos.py`

## Trampas

- **`core/` no importa `places/`.** La lógica de los comandos llega inyectada (`procesar`) desde `api.py`. Así el canal es intercambiable (plan B: Telegram) y no se arma un ciclo.
- **Costo cero (candado 2):** solo se manda `"type": "text"`. Un test falla si la palabra de las plantillas aparece en estos archivos.
- **Números argentinos:** Los celulares argentinos son `549…` en WhatsApp. El 15/10 el número de Franco estaba en la lista del panel **sin el 9**: Meta *aceptó* el envío a `54…` y no lo entregó nunca. Cargado **con el 9**, llegó. Por eso se responde al **`from` exacto** del mensaje entrante (el id que da Meta) y **no se reintenta con otra variante**: mandar a `54…` sería un fallo silencioso. El remitente se compara con el autorizado en forma canónica (`canonico`, solo para comparar).
- **Orden del POST:** se lee el cuerpo **antes** de rechazar (si no, en Windows el cliente ve `ConnectionResetError` en vez del 503), se verifica la firma sobre los **bytes crudos**, se registra el wamid, se responde 200 y recién ahí se procesa en el hilo trabajador.
- **Un solo hilo trabajador** a propósito: un "sí" nunca se adelanta al gasto que confirma, y no compiten dos escrituras. Los contextvars arrancan vacíos en ese hilo: el workspace se fija ahí, y `user_id` viaja explícito.
- Si procesar falla, `resultado='error'` + aviso a Franco. El dedupe no puede convertir un fallo en silencio.
- Los estados `failed` que manda Meta se loguean con el código: ahí aparecería tarde un 131042 (pago) o un 131047 (ventana cerrada).

## Estado

- **15/10/2026:** creado. Tests: `tests/test_api_whatsapp.py` (servidor real en un puerto libre). Smoke test de `api.py` como proceso: health, verificación de Meta y POST firmado OK; el envío con token falso lo rechazó Meta (190) y quedó en el log. Costo cero confirmado con el script (texto entregado sin tarjeta). **Sin desplegar.**

## Proximo paso

Deploy + Parte 3 de `docs/WHATSAPP-CANAL.md`. Con el primer mensaje real, anotar acá el formato del `from` que muestra el log.
