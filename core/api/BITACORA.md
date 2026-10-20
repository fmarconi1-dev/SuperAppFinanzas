# core/api/

<!-- huella: f85561b1e920 -->

Resumen: API HTTP stdlib de la SuperApp (Fase A, ADR-0008): servidor con el webhook de WhatsApp firmado por Meta, dedupe y cola de trabajo, más el canal de Meta (único módulo que le habla).

## Buscar acá si

- el bot no contesta, contesta dos veces o un mensaje "se perdió" → `servidor.py` (firma, remitente, dedupe por wamid, cola, `resultado` en `whatsapp_mensajes`)
- Meta rechaza un envío o aparece un código 131xxx en `fly logs` → `whatsapp_meta.py` (`CanalNoDisponible` con el código; ante un 131030 prueba sin el 9 y con el 9, y si ninguno sirve dice que el número del panel va con el 9)
- un briefing de Gemini que no llegó, llegó dos veces o llegó tarde → `servidor.py` (`_post_briefing`, `encolar_saliente`, `entregar_pendientes`; la tabla `whatsapp_salientes`)
- `evento:` / `tarea:` / `agenda` no llegan a Google, o Google contesta raro → `google.py` (`ClienteAgenda`: el 302 de Apps Script, `ok: false` → `AgendaRechazo`, página de login → `AgendaNoDisponible`)
- configurar el webhook en el panel de Meta (verify token, `hub.challenge`) → `servidor.py` + `docs/WHATSAPP-CANAL.md`
- un archivo (extracto, resumen, foto) que no llegó, no se bajó o se contestó "no sé leer ese archivo" → `whatsapp_meta.descargar_archivo` (dos pasos: id → URL → contenido; `ArchivoNoDisponible`), `archivos.tipo_de_contenido` (por los primeros bytes) y `servidor._bajar`
- el dólar de un consumo en USD de la tarjeta salió raro, o "no pude traer el dólar oficial" → `cotizaciones.py` (ArgentinaDatos, gratis, sin clave; un 404 es un feriado y va el día hábil anterior; si no contesta, `CotizacionNoDisponible` y se le pide el dólar a Franco)
- qué variables de entorno hacen falta → `ConfigWhatsApp.desde_entorno` (y `.env.example`)
- la interpretación del texto (montos, categorías, `resumen`, `deshacer`) → **no es acá**: `places/finanzas/core/comandos.py`

## Trampas

- **`core/` no importa `places/`.** La lógica de los comandos llega inyectada (`procesar`) desde `api.py`. Así el canal es intercambiable (plan B: Telegram) y no se arma un ciclo.
- **Costo cero (candado 2):** solo se manda `"type": "text"`. Un test falla si la palabra de las plantillas aparece en estos archivos.
- **Números argentinos:** **Dos formatos, cada uno en su lugar (comprobado en producción el 15/10/2026):** en la **lista del panel** el celular argentino va **con el 9** (`549…`; sin el 9, Meta acepta los envíos y no los entrega); los mensajes entrantes traen el `from` **con el 9**; y para **mandar**, Meta lo quiere **sin el 9** (`54…`): a `549…` responde 131030 aunque la lista esté bien. Por eso `enviar_texto` manda primero en forma canónica (sin el 9) y, solo ante un 131030, reintenta con el 9; el remitente se compara también en forma canónica. Ojo con la tentación de "responder al `from` tal cual": eso fue el 131030 del primer mensaje real.
- **Orden del POST:** se lee el cuerpo **antes** de rechazar (si no, en Windows el cliente ve `ConnectionResetError` en vez del 503), se verifica la firma sobre los **bytes crudos**, se registra el wamid, se responde 200 y recién ahí se procesa en el hilo trabajador.
- **Un solo hilo trabajador** a propósito: un "sí" nunca se adelanta al gasto que confirma, y no compiten dos escrituras. Los contextvars arrancan vacíos en ese hilo: el workspace se fija ahí, y `user_id` viaja explícito.
- Si procesar falla, `resultado='error'` + aviso a Franco. El dedupe no puede convertir un fallo en silencio.
- **La cola de salida no tiene camino pago:** fuera de la ventana el mensaje espera. No "arreglar" un briefing que no llegó mandándolo igual: fuera de la ventana Meta lo rechaza (131047) y queda con su error en la cola.
- **Apps Script siempre contesta HTTP 200**: el resultado real es `ok`. Y un POST a `/exec` vuelve con 302 a `script.googleusercontent.com`, que `urllib` sigue con GET sin cuerpo (así tiene que ser). Si en vez de JSON llega HTML, es la página de login: la aplicación web no está publicada con acceso "Cualquier persona".
- **Un archivo se baja antes que nada** (Fase D, paso 3): la URL que da Meta vence en minutos, así que el hilo trabajador lo baja incluso antes de entregar los briefings en cola. Se baja **a memoria** y nunca toca el disco (ni el volumen ni `/tmp`): no hay nada que borrar después, aunque el proceso se caiga a mitad. Tope: 10 MB (`MAX_ARCHIVO`), mirado en lo que dice Meta y en lo que llega.
- **El tipo se decide por el contenido, no por el nombre ni por el `mime_type` de Meta**: un `.xlsx` es un zip con `xl/workbook.xml`; un zip cualquiera o un `.xls` viejo no se aceptan. De un archivo, en `whatsapp_mensajes.texto` queda solo qué era (`[document] nombre · pie`), nunca el contenido.
- **Una descarga rota no es "un archivo que no sé leer"** ("no contestó" ≠ "no existe"). Si Meta devuelve una página (`text/html` o `application/json`) en vez del archivo, o si su `mime_type` dice Excel, PDF o foto y los bytes no lo son, es `error` con "mandalo de nuevo", y queda en el log el tipo y el largo (nunca el contenido). "No sé leer ese archivo" es solo para lo que de verdad no es de los tipos aceptados.
- `GRAPH_BASE` es una constante del módulo para que los tests apunten a un Meta de mentira local; no la cambies por entorno.
- Los estados `failed` que manda Meta se loguean con el código: ahí aparecería tarde un 131042 (pago) o un 131047 (ventana cerrada).

## Estado

- **20/10/2026 (Fase D, paso 5, sin desplegar):** `cotizaciones.py`: el oficial vendedor de una fecha (`oficial_vendedor`), inyectado desde `api.py` como `cotizador`. Tests: `tests/test_cotizaciones.py` (contra un ArgentinaDatos de mentira).
- **19/10/2026 (Fase D, paso 3, sin desplegar):** documentos y fotos. `extraer_eventos` arma `ArchivoEntrante` (id, mime, nombre, pie); `descargar_archivo` lo baja de la Graph API; `archivos.py` (nuevo) lo reconoce por el contenido; el servidor lo pasa a `procesar_archivo` (inyectado desde `api.py`). Lo que no es Excel, PDF ni foto se contesta sin leer. Tests: `tests/test_archivos_whatsapp.py` (con un Meta de mentira) y los de archivos en `tests/test_api_whatsapp.py`.
- **17/10/2026 (Fase C):** `ClienteAgenda.completar_tarea` (el tilde del Inicio).
- **17/10/2026 (Fase B, paso 3, desplegado y probado punta a punta por Franco):** `google.py` nuevo: cliente del Apps Script de agenda (`crear_evento`, `crear_tarea`, `resumen_semana`). El servidor ahora le pasa a `procesar` el wamid de cada mensaje, que viaja a Google como `id_solicitud` (un reintento de Meta no crea dos eventos). Se configura con `GOOGLE_WORKSPACE_WEBHOOK_URL` y `GOOGLE_WORKSPACE_SECRET`; sin ellas, la agenda queda apagada y lo demás anda igual.

- **16/10/2026 (Fase B, desplegado y probado):** `POST /api/briefing` (Bearer `SUPERAPP_API_TOKEN`, `tipo` briefing/cierre, `id` del mail como dedupe) y **cola de salida** (`whatsapp_salientes`, M18): sale si la ventana de 24 h está abierta (margen de 10 min), si no queda en cola y se entrega, con aviso, apenas Franco escribe y antes de contestarle. Un lock evita que el hilo trabajador y un briefing nuevo manden lo mismo dos veces. El armado (`componer`) llega inyectado desde `api.py` y no agrega nada. Tests: `tests/test_api_briefing.py`. **El cierre de mercado del 16/10 llegó por el Secretario.**

- **15/10/2026:** creado y **desplegado**. Webhook verificado por Meta; la app tuvo que suscribirse a la cuenta de WhatsApp Business (`POST /{waba}/subscribed_apps`): solo estaba suscripta la app de prueba de Meta y por eso no llegaba nada. Primer mensaje real recibido a las 20:50 (`from` = `549…`); la respuesta rebotó con 131030 por mandar con el 9 → corregido (se manda sin el 9).

## Proximo paso

Fase D, paso 6: el cliente de Gemini para leer fotos (`docs/PLAN-FASE-D.md`). Los pasos 4 y 5 (leer el extracto y los resúmenes) son de `places/finanzas/core/`.
