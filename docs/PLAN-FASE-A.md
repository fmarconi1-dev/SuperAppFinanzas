# Plan — Fase A: gastos por WhatsApp (ADR-0008)

**Objetivo:** Franco le escribe al "Secretario" por WhatsApp y el gasto queda cargado en la base de producción, con confirmación. Costo cero (ver `docs/WHATSAPP-CANAL.md`).

**Fuera de alcance de esta fase:** briefing, `evento:` / `tarea:`, Apps Script (Fase B) · dashboard y rebranding (Fase C) · `/api/transacciones` y `/api/conciliar` (Fase D) · cuentas y perímetro (Fase 5).

## Qué puede hacer Franco al terminar

| Mensaje | Respuesta |
|---|---|
| `2500, super` | ✅ Cargado #812: $2.500 en Supermercado (14/10) |
| `13/10, 18.000, nafta, YPF ruta 2` | con fecha, monto, categoría y comentario |
| `ayer; 4500 | farmacia` | separadores `,` `;` `|`; acepta `hoy` y `ayer` |
| `+350000, sueldo` | el `+` lo carga como ingreso |
| `2500, supr` | ¿Quisiste decir **Supermercado**? Respondé *sí* o *no* |
| `2500, regalo tía` (categoría inexistente) | "Regalo tía" no existe. ¿La creo? *sí* / *no* |
| `resumen` / `saldo` | gastos e ingresos del mes + últimos 5 movimientos |
| `deshacer` | borra el último gasto cargado **por WhatsApp** en las últimas 24 h y dice cuál |
| `ayuda` | formatos y comandos |
| cualquier otra cosa que no se entienda | explica el formato; **nunca carga a ciegas** |

## Diseño

### Archivos nuevos

| Archivo | Qué |
|---|---|
| `api.py` (raíz) | runner: `init_db()` y levanta el servidor |
| `core/api/servidor.py` | `ThreadingHTTPServer` en `127.0.0.1:8000`; rutas, códigos HTTP, logging |
| `core/api/whatsapp_meta.py` | canal: verificación GET, firma HMAC, extraer mensajes del payload, enviar texto, partir en 4096. **Único módulo que habla con Meta.** Si se pasa a Telegram, se cambia solo este |
| `places/finanzas/core/comandos.py` | parser y lógica de comandos, **pura y sin red**: recibe texto + conexión y devuelve la respuesta |
| `deploy/nginx.conf` | 8501 → `/api/` a 8000, `/` a Streamlit en 8502 |
| `tests/test_api_*.py`, `tests/test_comandos_whatsapp.py` | ver Tests |

### Endpoints

| Ruta | Auth | Qué |
|---|---|---|
| `GET /api/health` | — | `200 {"ok": true}` |
| `GET /api/whatsapp` | `hub.verify_token` | suscripción de Meta: devuelve `hub.challenge` en texto plano |
| `POST /api/whatsapp` | firma `X-Hub-Signature-256` | mensajes entrantes |
| `GET /api/privacidad` | — | política de privacidad mínima en HTML (Meta la pide para el modo Live) |

### Flujo de un mensaje entrante

1. Leer el cuerpo **crudo** y verificar `X-Hub-Signature-256 = sha256=HMAC(WHATSAPP_APP_SECRET, cuerpo)` con `hmac.compare_digest`. Si no coincide → 401, sin procesar.
2. Extraer `entry[].changes[].value.messages[]`. De los `statuses`, los entregados y leídos se ignoran; **los `failed` se loguean con su código de error**, porque ahí aparecería un 131042 (pago) o un 131047 (ventana cerrada) que Meta informa tarde.
3. Por cada mensaje:
   - el remitente (`from`), normalizado a dígitos, tiene que ser `WHATSAPP_NUMERO_AUTORIZADO`. Si no, se ignora y se loguea sin el contenido;
   - **dedupe:** `INSERT OR IGNORE` del `id` (wamid). Si ya estaba, se ignora: Meta reintenta hasta 7 días;
   - se guarda la hora en `whatsapp_estado.ultimo_entrante` (la Fase B la usa para saber si la ventana está abierta).
4. Responder **200 enseguida** y procesar en un hilo aparte. Así un arranque en frío o un envío lento no provoca reintentos.
5. Si el mensaje no es de texto → "Por ahora solo entiendo texto". Si es texto → `comandos.procesar()` → `whatsapp_meta.enviar_texto(from, respuesta)`. **Se contesta al `from` exacto** que trajo el mensaje: es el id de WhatsApp que da Meta. Los celulares argentinos son `549…` en WhatsApp. El 15/10 el número de Franco estaba en la lista del panel **sin el 9**: Meta *aceptó* el envío a `54…` y no lo entregó nunca. Cargado **con el 9**, llegó. Por eso no se deducen formatos ni se reintenta con otra variante: un 131030 se loguea con qué arreglar en el panel. El remitente se compara con el autorizado en forma canónica (con o sin el 9 da igual). Si el procesamiento falla después de registrar el wamid, la fila queda con `resultado='error'` y se le avisa a Franco por WhatsApp: el dedupe no puede convertir un fallo en silencio.

### Envío (costo cero)

- `POST https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages` con `{"messaging_product": "whatsapp", "to": ..., "type": "text", "text": {"body": ...}}`.
- **No existe ninguna función que mande plantillas.** `test_api_sin_plantillas.py` falla si aparece `"template"` en `core/api/` o en `places/finanzas/core/comandos.py`.
- Si Meta rechaza (131047 fuera de ventana, cualquier error), se loguea con el código y se levanta `CanalNoDisponible`: el error se nombra, no se traga.
- Textos de más de 4096 caracteres se parten por párrafo y, si hace falta, por línea.

### Base de datos — M17, aditiva

(M16 queda reservada para las cuentas de la Fase 5.)

```sql
CREATE TABLE IF NOT EXISTS whatsapp_mensajes (
  wamid          TEXT PRIMARY KEY,
  recibido_en    TEXT NOT NULL,              -- ISO, America/Argentina/Buenos_Aires
  remitente      TEXT NOT NULL,
  texto          TEXT,
  transaccion_id INTEGER REFERENCES transacciones(id) ON DELETE SET NULL,
  resultado      TEXT                        -- cargado | consulta | pendiente | error | ignorado
);
CREATE TABLE IF NOT EXISTS whatsapp_estado (
  clave TEXT PRIMARY KEY,                    -- ultimo_entrante, pendiente
  valor TEXT NOT NULL,
  actualizado_en TEXT NOT NULL
);
```

- `pendiente` guarda en JSON el gasto que espera un *sí* o un *no* (categoría dudosa o nueva). Vence a los 10 minutos. Un mensaje que no sea *sí* ni *no* descarta lo pendiente y se procesa como mensaje nuevo.
- `deshacer` busca la última fila con `transaccion_id` no nulo de las últimas 24 h y llama a `delete_transaction`.

### Parser (`comandos.py`)

- **Separadores** `,` `;` `|`. Primer bloque opcional de fecha: `DD/MM`, `DD/MM/AA`, `DD/MM/AAAA`, `AAAA-MM-DD`, `hoy`, `ayer`. Sin año → año actual, pero **si la fecha queda en el futuro, se toma el año anterior** (un `28/12` cargado el 2/1). Una fecha futura explícita se rechaza.
- **Monto:** parser propio y estricto, `parsear_monto`. **No se reusa `parse_currency_estricto`** (corregido el 15/10): ese borra todos los puntos, así que `2500.50` daría 250.050 y `1.5` daría 15. Está bien para el CSV, no para un mensaje tipeado en el celular. Reglas:
  - el punto solo se acepta como separador de miles, en grupos de 3 (`25.000`, `1.250.000`);
  - la coma es el decimal (`2500,50`, `25.000,5`);
  - `$` adelante, opcional; `k` atrás para miles (`25k`, `2,5k`);
  - un punto seguido de 1 o 2 dígitos (`2500.50`) es **ambiguo**: se repregunta, nunca se escribe.

  `None` → "no entendí el monto". Monto 0 o negativo → error. Un `+` adelante → ingreso.
- **`resumen`** usa la misma fórmula que el dashboard (`load_transactions` + `load_categorias_full` + `ingresos_vs_gastos_mensual`), no una suma cruda de pasivos, que contaría la Compra Divisa como gasto. Como esa fórmula deja afuera "Sin categorizar" (justo donde caen las categorías nuevas de WhatsApp), ese monto se muestra en un renglón aparte.
- **Categoría:** se compara con `all_motivos(conn, uid)` sin mayúsculas ni acentos:
  - igual → se usa el nombre canónico tal como está en la base;
  - parecida (`difflib.get_close_matches`, corte 0,75) → se pregunta *¿quisiste decir…?*;
  - sin parecido → se pregunta si se crea.
- **Comentario:** el resto de los bloques, unidos con `, `.
- **Hoy** se calcula siempre en `America/Argentina/Buenos_Aires` (`zoneinfo`), nunca en la zona del servidor (Fly corre en UTC).

### Usuario y workspace

- `SUPERAPP_DEFAULT_USER` (nombre en `usuarios`, **exacto, con mayúsculas y minúsculas**), obligatoria: si falta o no existe, `/api/whatsapp` responde 503 y lo dice en el log (`/api/health` sigue andando). Nada de "fallback a 1".
- `SUPERAPP_DEFAULT_WORKSPACE` opcional (id). Sin ella, el personal del usuario. Se fija con `set_current_workspace_id` **dentro del hilo que procesa**, porque los contextvars no viajan entre hilos. `insert_transaction` recibe `user_id` explícito.
- La conexión es una por request (`core.db.connect()`), nunca compartida entre hilos. Las escrituras ya disparan `backup_db` desde `transactions.py`.

### Variables de entorno (todas obligatorias salvo aclaración)

| Variable | |
|---|---|
| `WHATSAPP_TOKEN` | token permanente del usuario del sistema |
| `WHATSAPP_PHONE_NUMBER_ID` | id del número de prueba |
| `WHATSAPP_APP_SECRET` | para verificar la firma |
| `WHATSAPP_VERIFY_TOKEN` | el que se escribe en el panel del webhook |
| `WHATSAPP_NUMERO_AUTORIZADO` | `549` + área + número |
| `WHATSAPP_GRAPH_VERSION` | opcional; default fijado en el código (verificar la vigente al implementar) |
| `SUPERAPP_DEFAULT_USER` | `franco` |
| `SUPERAPP_DEFAULT_WORKSPACE` | opcional |

Si falta una obligatoria, `/api/whatsapp` responde **503** con el nombre de la variable en el log (mismo patrón que `SIGNUP_CODE`), y `/api/health` sigue andando. Van a `.env.example` **sin valores** (`test_env_example_sin_secretos` lo vigila).

### Contenedor

- **Dockerfile:** `nginx` en el `apt-get`. `COPY api.py ./` y `COPY deploy/nginx.conf /etc/nginx/conf.d/superapp.conf` (y borrar el `default` de `sites-enabled`). `STREAMLIT_SERVER_PORT=8502`, `STREAMLIT_SERVER_ADDRESS=127.0.0.1`. El `HEALTHCHECK` sigue en `:8501/_stcore/health`, ahora a través de nginx. `EXPOSE 8501`.
- **nginx:** `/api/` → `127.0.0.1:8000`; `/` → `127.0.0.1:8502` con `Upgrade`/`Connection "upgrade"`, `proxy_http_version 1.1`, `proxy_read_timeout 86400` y `X-Forwarded-*`. `client_max_body_size` acotado en `/api/`. Access log de `/api/` **sin query string**.
- **Entrypoint:** **conserva el seed tal cual**, después `(while true; do python /app/api.py; echo "[entrypoint] API caída, reinicio en 2 s"; sleep 2; done) &`, `nginx`, y `exec streamlit run app.py`.
- **`fly.toml` no se toca:** el puerto 8501, el health check y el volumen quedan igual. Fly despierta la máquina con el webhook (`auto_start_machines`).

## Tests (gate: suite completa en verde, 0 skipped en local)

- **Parser:** fechas (incluido el salto de año y la fecha futura), montos es-AR, `+` ingreso, separadores, comentario, mensajes vacíos o basura.
- **Categorías:** exacta, sin acentos, parecida → pendiente, nueva → pendiente, *sí* / *no*, vencimiento a los 10 min.
- **Comandos:** `resumen` con números contra una base sintética (gastos, ingresos, cantidad, últimos 5) · `deshacer` (solo WhatsApp, solo 24 h, nada que deshacer) · `ayuda`.
- **Webhook:** firma válida / inválida / ausente · verify token correcto / incorrecto · remitente no autorizado ignorado · wamid repetido no duplica · `statuses` ignorados · no-texto contestado · faltan env → 503.
- **Servidor real** en un puerto libre, con `enviar_texto` reemplazado por un fake: `POST` firmado → fila en `transacciones` → respuesta capturada.
- **Costo cero:** no aparece `"template"` en el código del canal.
- **Contenedor:** el entrypoint conserva `needs_seed`, relanza la API y termina en `exec streamlit`; `nginx.conf` tiene las dos rutas, el upgrade del websocket y el timeout largo; el Dockerfile copia `api.py` y `deploy/nginx.conf`.
- **Sin regresiones:** las 359 de hoy siguen verdes.

## Cierre de la fase

1. Bitácoras de las carpetas tocadas (`core/`, `places/finanzas/core/`, `tests/`, raíz) selladas. `EN-HUMANO.md`, `ESTADO.md`, `ROADMAP.md`, `docs/DEPLOY.md` (nginx, secretos nuevos), `docs/RUNBOOK.md` (qué mirar si el bot no contesta).
2. Commit listo. **El push y el deploy los hace Franco.**
3. Franco hace las Partes 1–3 de `docs/WHATSAPP-CANAL.md` (la Parte 1 se puede hacer antes, en paralelo).
4. Prueba real: `2500, prueba` → ✅ → `deshacer` → borrado. La fase se cierra con eso funcionando en producción.
