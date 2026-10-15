# Canal de WhatsApp para el secretario

Investigación del 14/10/2026. **Decisión (ADR-0008): Meta Cloud API con costo cero garantizado.** Franco: *"tiene que ser gratis sí o sí y sin peros"*.

## Cómo es gratis, sin peros

Meta cobra **una sola cosa**: los mensajes de **plantilla** (los que el negocio manda por su cuenta, fuera de la conversación). Todo lo demás es gratis: *"All non-template messages are free"*, siempre que se manden dentro de la **ventana de 24 h** que se abre cada vez que vos le escribís al bot.

El costo cero se apoya en **dos candados**. Con cualquiera de los dos solo ya no hay cobro posible:

1. **No se carga ningún medio de pago en Meta.** Sin tarjeta, Meta no tiene a quién cobrarle: una plantilla paga falla (error 131042, "problema de pago") en vez de cobrarse.
2. **El código no sabe mandar plantillas.** La API de la SuperApp solo arma mensajes de texto libre (`"type": "text"`), y un test falla si aparece `"type": "template"` en cualquier parte. Un texto libre fuera de la ventana **no se cobra: Meta lo rechaza** (error 131047).

El peor caso es que un mensaje no salga, nunca que se cobre.

### Qué se resigna: el bot no puede escribirte cuando quiere

Dentro de la ventana el bot contesta todo lo que quieras. Fuera de la ventana no puede iniciar la charla. Eso solo afecta al **briefing matutino** (Fase B), que se resuelve así:

- **La ventana dura 24 h desde tu último mensaje.** Si ayer cargaste un gasto después de las 7:00, hoy a las 7:00 la ventana está abierta y el briefing sale solo. Con el uso diario normal (cargar gastos) eso pasa casi siempre.
- **Si la ventana está cerrada, el briefing queda guardado** y te llega apenas le escribís cualquier cosa al bot ("hola", "briefing", un gasto). Y el mail del briefing te llega igual a Gmail, como hoy.
- La API guarda la hora de tu último mensaje para saber cuál de los dos caminos tomar. No hay un tercer camino pago.

## Paso a paso (todo gratis)

**Antes de empezar:** necesitás tu Facebook personal y tu celular con WhatsApp. No hace falta chip nuevo, empresa, CUIT ni tarjeta.

### Parte 1 — Cuenta y número del bot (≈20 min, se puede hacer ya)

1. Entrá a **developers.facebook.com** con tu Facebook → *Comenzar* → registrate como desarrollador (verifica tu cuenta con un SMS o un mail).
2. **Mis apps → Crear app** → caso de uso **"Conectarse con clientes a través de WhatsApp"** → te pide una *business portfolio*: creala con tu nombre (es un contenedor, no una empresa registrada). Si en cualquier momento aparece **"Agregar método de pago"**, **saltealo**. Ese es el candado 1.
3. En el panel de la app: **WhatsApp → Configuración de la API** (*API Setup*). Meta ya te creó un **número de prueba** gratis. Anotá dos datos que se ven ahí: **Phone number ID** y **WhatsApp Business Account ID**.
4. En el campo **Para** (*To*) → *Administrar lista de números* → agregá **tu número personal CON el 9** (+54 9 11 …) → te llega un código por WhatsApp → lo ingresás. ⚠️ Sin el 9, Meta acepta los mensajes y no los entrega (pasó el 15/10/2026).
5. **No toques el botón "Enviar mensaje"** del panel: manda la plantilla `hello_world`. En su lugar, agendá el número de prueba en tu celular como **"Secretario"** y mandale *hola* desde tu WhatsApp. Eso abre la primera ventana.
6. **La prueba de costo cero.** En el mismo panel, tocá **"Generar token de acceso"** (es temporal; no lo pegues en ningún chat) y, dentro de las 24 h siguientes a tu *hola*, corré:
   ```
   .venv\Scripts\python.exe scripts\probar_whatsapp_texto.py
   ```
   Te pide el token (no se ve mientras lo pegás), el Phone number ID y tu número, y manda **un texto libre**, nunca una plantilla. El resultado te dice qué pasó:
   - **ÉXITO** y te llega el mensaje → Meta deja mandar texto sin tarjeta. Seguimos con Meta y arranca la Fase A.
   - **BLOQUEADO POR PAGO** (131042) → no se carga tarjeta: se pasa a Telegram.
   - **VENTANA CERRADA**, **NÚMERO NO AUTORIZADO** o **TOKEN VENCIDO** → el propio mensaje dice cómo corregirlo. Se arregla y se vuelve a correr.

### Parte 2 — Llave permanente (≈10 min)

6. Entrá a **business.facebook.com** → Configuración → **Usuarios del sistema** → *Agregar* → nombre `superapp`, rol **Administrador**.
7. Al usuario del sistema → **Asignar activos**: la app (control total) y la cuenta de WhatsApp (control total).
8. **Generar token** → la app → vencimiento **"Nunca"** → permisos `whatsapp_business_messaging` y `whatsapp_business_management` → copialo. Es la llave con la que la SuperApp manda mensajes. No se comparte ni va en el repo.
9. En la app → **Configuración → Básica** → copiá la **Clave secreta de la app** (*App Secret*). Sirve para comprobar que cada mensaje que llega viene de Meta de verdad.

### Parte 3 — Conectar la SuperApp (cuando la Fase A esté desplegada)

10. Elegí un **token de verificación** (cualquier texto largo al azar) y cargá todo en Fly:
    ```
    fly secrets set WHATSAPP_TOKEN=... WHATSAPP_PHONE_NUMBER_ID=... WHATSAPP_APP_SECRET=... WHATSAPP_VERIFY_TOKEN=... WHATSAPP_NUMERO_AUTORIZADO=549... -a superapp-finanzas
    ```
11. Panel de la app → **WhatsApp → Configuración → Webhook**: URL `https://superapp-finanzas.fly.dev/api/whatsapp`, token de verificación el del paso 10 → *Verificar y guardar*. Después, en *Campos del webhook*, suscribí **`messages`**.
12. Mandale `ayuda` al Secretario. Si contesta, listo.
13. **Si no llega nada:** Meta advierte que en modo *desarrollo* algunos webhooks no se envían. Pasá la app a modo **Live** (gratis). Te va a pedir una URL de política de privacidad: usá `https://superapp-finanzas.fly.dev/api/privacidad`, que la Fase A deja publicada.

## Lo que todavía no está confirmado (y qué pasa si falla)

| Duda | Por qué | Si sale mal |
|---|---|---|
| ¿Meta deja mandar texto libre **sin medio de pago cargado**? | ✅ **Sí, confirmado el 15/10/2026**: con el número de prueba y sin tarjeta, el texto libre **llegó** al teléfono de Franco. (Un primer intento se aceptó y no llegó: era el formato del número, ver abajo.) | — |
| ¿Hace falta verificar la "empresa"? | Meta documenta topes para portfolios nuevas (2 números, 250 mensajes por día fuera de ventana), y varios proveedores dicen que se opera sin verificar. | Mismo plan B. |
| ¿El número de prueba es para siempre? | Meta no documenta que venza. | Plan B gratis: Telegram. Un chip propio también serviría, pero cuesta lo que salga el chip. |
| Formato de números argentinos | ✅ **Resuelto el 15/10/2026.** Los celulares argentinos son `549…` en WhatsApp. El 15/10 el número de Franco estaba en la lista del panel **sin el 9**: Meta *aceptó* el envío a `54…` y no lo entregó nunca. Cargado **con el 9**, llegó. | En el panel, tu número va **con el 9** (+54 9 11 …). La API responde al `from` exacto de cada mensaje (el id que da Meta) y no prueba otros formatos: ante un 131030 avisa qué corregir. |

## Política de IA de Meta

Desde el 15/1/2026, Meta prohíbe en la Business API a los asistentes de IA **de propósito general** (ChatGPT, Perplexity y similares). Un bot que carga gastos y agenda eventos para su dueño no entra en esa prohibición. Si más adelante se agrega un LLM para entender mensajes en lenguaje natural, sigue siendo una función accesoria.

## Comparación (por qué Meta y no las otras)

| | Meta Cloud API | Green-API | Telegram |
|---|---|---|---|
| Oficial | sí | no (riesgo de baneo del número) | sí |
| Costo con los dos candados | **0** | depende de su plan | 0 |
| Número aparte | el de prueba, gratis | conviene uno | no hace falta |
| Bot escribe primero (briefing) | solo con la ventana abierta | sí | sí |
| Seguridad del webhook | firma HMAC de Meta | token propio | token secreto |

**Telegram es el plan B** si Meta falla en algún punto de la tabla de dudas: es gratis, oficial y no tiene ventana de 24 h. El resto de la API (parser, base, Google) es igual: solo cambia el módulo del canal.

## Fuentes

- [Get Started — Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started) · [versión nueva](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started.md)
- [Pricing](https://developers.facebook.com/docs/whatsapp/pricing) · [Phone numbers](https://developers.facebook.com/docs/whatsapp/cloud-api/phone-numbers) · [Messaging limits](https://developers.facebook.com/docs/whatsapp/messaging-limits) · [Display names](https://developers.facebook.com/docs/whatsapp/display-names) · [Webhooks](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview)
- Error 131042 solo en plantillas (foro de Meta): [hilo](https://developers.facebook.com/community/threads/26841465555446325/) · [DataCrazy](https://help.datacrazy.io/en/articles/10670778-error-131042-payment-in-the-whatsapp-cloud-api)
- Modo Live y política de privacidad: [Bevatel](https://docs.bevatel.com/inboxes/whatsapp/whatsapp-cloud-api) · [Hookdeck](https://hookdeck.com/webhooks/skills/whatsapp-webhooks)
- Operar sin verificación (terceros): [Zoko](https://www.zoko.io/post/use-whatsapp-api-without-business-verification) · [Infobip](https://www.infobip.com/docs/whatsapp/get-started/sender-registration)
- Números de Argentina: [Smarsh](https://docs.smarsh.com/docs/whatsapp-number-mismatch) · [Whapi](https://support.whapi.cloud/help-desk/specifics-of-sending-messages-to-numbers-of-different-countries)
- Política de IA: [TechCrunch, 18/10/2025](https://techcrunch.com/2025/10/18/whatssapp-changes-its-terms-to-bar-general-purpose-chatbots-from-its-platform/)
