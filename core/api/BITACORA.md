# core/api/

<!-- huella: 69875edad29b -->

Resumen: API HTTP stdlib de la SuperApp (Fase A, ADR-0008): servidor con el webhook de WhatsApp firmado por Meta, dedupe y cola de trabajo, más el canal de Meta (único módulo que le habla).

## Buscar acá si

- el bot no contesta, contesta dos veces o un mensaje "se perdió" → `servidor.py` (firma, remitente, dedupe por wamid, cola, `resultado` en `whatsapp_mensajes`)
- Meta rechaza un envío o aparece un código 131xxx en `fly logs` → `whatsapp_meta.py` (`CanalNoDisponible` con el código; ante un 131030 prueba sin el 9 y con el 9, y si ninguno sirve dice que el número del panel va con el 9)
- configurar el webhook en el panel de Meta (verify token, `hub.challenge`) → `servidor.py` + `docs/WHATSAPP-CANAL.md`
- qué variables de entorno hacen falta → `ConfigWhatsApp.desde_entorno` (y `.env.example`)
- la interpretación del texto (montos, categorías, `resumen`, `deshacer`) → **no es acá**: `places/finanzas/core/comandos.py`

## Trampas

- **`core/` no importa `places/`.** La lógica de los comandos llega inyectada (`procesar`) desde `api.py`. Así el canal es intercambiable (plan B: Telegram) y no se arma un ciclo.
- **Costo cero (candado 2):** solo se manda `"type": "text"`. Un test falla si la palabra de las plantillas aparece en estos archivos.
- **Números argentinos:** **Dos formatos, cada uno en su lugar (comprobado en producción el 15/10/2026):** en la **lista del panel** el celular argentino va **con el 9** (`549…`; sin el 9, Meta acepta los envíos y no los entrega); los mensajes entrantes traen el `from` **con el 9**; y para **mandar**, Meta lo quiere **sin el 9** (`54…`): a `549…` responde 131030 aunque la lista esté bien. Por eso `enviar_texto` manda primero en forma canónica (sin el 9) y, solo ante un 131030, reintenta con el 9; el remitente se compara también en forma canónica. Ojo con la tentación de "responder al `from` tal cual": eso fue el 131030 del primer mensaje real.
- **Orden del POST:** se lee el cuerpo **antes** de rechazar (si no, en Windows el cliente ve `ConnectionResetError` en vez del 503), se verifica la firma sobre los **bytes crudos**, se registra el wamid, se responde 200 y recién ahí se procesa en el hilo trabajador.
- **Un solo hilo trabajador** a propósito: un "sí" nunca se adelanta al gasto que confirma, y no compiten dos escrituras. Los contextvars arrancan vacíos en ese hilo: el workspace se fija ahí, y `user_id` viaja explícito.
- Si procesar falla, `resultado='error'` + aviso a Franco. El dedupe no puede convertir un fallo en silencio.
- Los estados `failed` que manda Meta se loguean con el código: ahí aparecería tarde un 131042 (pago) o un 131047 (ventana cerrada).

## Estado

- **15/10/2026:** creado y **desplegado**. Webhook verificado por Meta; la app tuvo que suscribirse a la cuenta de WhatsApp Business (`POST /{waba}/subscribed_apps`): solo estaba suscripta la app de prueba de Meta y por eso no llegaba nada. Primer mensaje real recibido a las 20:50 (`from` = `549…`); la respuesta rebotó con 131030 por mandar con el 9 → corregido (se manda sin el 9).

## Proximo paso

Desplegar el arreglo del formato de envío y hacer la prueba real (`ayuda` → `100, compras` → `deshacer`). Con eso cierra la Fase A.
