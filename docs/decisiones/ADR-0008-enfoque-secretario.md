# ADR-0008 — La SuperApp pasa a ser un secretario personal (WhatsApp + Google + dashboard)

**Fecha:** 2026-10-14 · **Estado:** ✅ Aceptada · **Fase:** nueva serie A–D; la Fase 5 (ADR-0006) queda en pausa

## Contexto

El 14/10/2026 Franco planteó un cambio de enfoque con rebranding: *"El objetivo es que actúe como mi secretario, registrando eventos, tareas pendientes y use esta base de gastos personales para registrar por WhatsApp mis gastos"*, con un dashboard nuevo que muestre las finanzas junto con los eventos de la semana y las tareas pendientes.

Traía un prompt de implementación (una API HTTP con stdlib, nginx en el contenedor, Green-API/CallMeBot y Apps Script como puente a Google). La revisión encontró: tokens con valores por defecto y en la URL, un webhook que aceptaba mensajes de cualquiera, un `doPost` de Apps Script sin autenticación, riesgo de gastos duplicados por reintentos, confirmaciones "✅" aunque la operación fallara, categorías nuevas por cada error de tipeo, un entrypoint que pisaba el seed, la API sin supervisor y, para el dashboard, ninguna lectura de Google. Y metía cinco cosas en una fase, contra la regla "una fase a la vez".

Sobre el canal, Franco puso una condición dura: *"No voy a pagar nada por esto, tiene que ser gratis sí o sí y sin peros"*.

## Decisión

### 1. Canal: Meta WhatsApp Cloud API, con costo cero por construcción

- Número de **prueba** de Meta para el bot; el número personal de Franco como único destinatario autorizado.
- **Candado 1:** no se carga medio de pago en Meta. **Candado 2:** el código solo manda texto libre (`type: text`), nunca plantillas, con un test que lo vigila. Fuera de la ventana de 24 h Meta **rechaza** el texto libre (131047), no lo cobra.
- El briefing matutino sale si la ventana está abierta; si no, queda pendiente y se entrega con el próximo mensaje de Franco.
- Detalle, paso a paso y dudas abiertas: `docs/WHATSAPP-CANAL.md`. **Plan B: Telegram**, si Meta bloquea el texto libre sin medio de pago o exige verificación.

### 2. Arquitectura

- **API HTTP con stdlib** (`http.server.ThreadingHTTPServer`, `urllib`) en `127.0.0.1:8000`, dentro del mismo contenedor. Sin dependencias nuevas.
- **nginx** escucha en 8501 (el puerto que Fly ya expone): `/api/` → API, `/` → Streamlit en 8502. **`fly.toml` no se toca.** El entrypoint conserva el seed y relanza la API si se cae.
- **Google Apps Script** como puente a Calendar y Tasks (`integraciones/google-apps-script/`), con secreto en el cuerpo, idempotencia y acciones de lectura para el dashboard.
- Los gastos que llegan por WhatsApp se escriben con `insert_transaction`, con `user_id` y workspace **explícitos** (variables de entorno), sin depender de contextvars.

### 3. Fases (una a la vez, cada una desplegable)

| Fase | Qué | Salida |
|---|---|---|
| **A** | API + WhatsApp para gastos e ingresos: cargar, `resumen`, `deshacer`, `ayuda`; seguridad, idempotencia, categorías con "¿quisiste decir?" | Franco carga gastos desde el celular |
| **B** | Briefing matutino (con resumen de gastos) + `evento:` / `tarea:` vía Apps Script | Agenda y briefing por WhatsApp |
| **C** | Dashboard "secretario" (finanzas + eventos de la semana + tareas) + rebranding | La app nueva |
| **D** | Conciliación por lotes (`GET /api/transacciones`, `POST /api/conciliar`, todo o nada, con `dry_run` y backup) | Auditoría de extractos |

## Alternativas consideradas

- **Green-API** (el borrador). Descartada como principal: no es oficial (riesgo de baneo) y, si se vincula al número propio, los mensajes de Franco son `fromMe` y no entran. Su ventaja (el bot escribe cuando quiere) no compensa.
- **CallMeBot** como respaldo. Descartada: solo envía, no recibe, y duplicaba código y tests.
- **Plantillas pagas para el briefing.** Descartada por la condición de Franco.
- **Telegram.** Queda como plan B, porque es gratis y no tiene ventana. No es la primera opción porque Franco quiere WhatsApp.
- **Llamar a las APIs de Google desde Python.** Descartada por ahora: exige OAuth y guardar tokens. Apps Script corre como Franco sin nada de eso.

## Consecuencias

- **La Fase 5 (ADR-0006) queda en pausa**, no descartada. La Fase A adelanta la parte de WhatsApp de su **Paso 4**, pero sin cuentas ni perímetro: los gastos se escriben como transacciones comunes. Cuando la Fase 5 vuelva, lo cargado por WhatsApp se asigna a la cuenta efectivo.
- **Tensión con ADR-0006** ("las fuentes producen propuestas, nunca escrituras"): un mensaje de Franco al bot es él mismo cargando un gasto, igual que el formulario, así que se escribe directo. Lo que sigue siendo propuesta es el **matching** contra otras fuentes (Fase 5, Paso 5).
- Variables de entorno nuevas, ninguna con valor por defecto que sea un secreto: si falta, la API se niega a operar (mismo patrón que `SIGNUP_CODE`).
- El token `franquito77` del borrador se considera expuesto: no se usa.
- El rebranding cambia el nombre visible, pero **la app de Fly sigue siendo `superapp-finanzas`**: Fly no permite renombrar. Si se quiere otro nombre en la URL, va por dominio propio.
- `test_scripts_backup` fija la máquina en 1 GB; nginx y la API agregan poco, no hace falta tocarla.
