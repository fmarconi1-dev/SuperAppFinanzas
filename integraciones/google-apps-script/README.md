# Puente Google ↔ SuperApp (Apps Script)

Código que corre en **Google Apps Script**, no en Fly. Vive en el repo para versionarlo; se pega a mano en el editor de Apps Script (o se sube con `clasp`).

| Archivo | Qué es |
|---|---|
| `Codigo.gs` | El script: briefing (Gmail → SuperApp) y webhook (SuperApp → Calendar/Tasks). |
| `appsscript.json` | Manifiesto: zona horaria Buenos Aires, servicio avanzado **Tasks**, web app. |

## Instalación (una sola vez)

1. En [script.google.com](https://script.google.com) creá un proyecto nuevo y pegá `Codigo.gs`.
2. **Configuración del proyecto** → tildá "Mostrar el archivo de manifiesto appsscript.json en el editor" y reemplazá su contenido por `appsscript.json` de acá. Eso fija la zona horaria y activa Tasks.
3. **Configuración del proyecto → Propiedades del script**:

   | Propiedad | Valor |
   |---|---|
   | `SUPERAPP_URL` | `https://superapp-finanzas.fly.dev` |
   | `SUPERAPP_TOKEN` | el mismo valor que `SUPERAPP_API_TOKEN` en Fly |
   | `SECRETO_WEBHOOK` | el mismo valor que `GOOGLE_WORKSPACE_SECRET` en Fly |
   | `CALENDARIOS` | *(opcional)* ids separados por coma; si no está, se listan los calendarios tildados en Calendar |

   Generá cada secreto con `openssl rand -hex 32`, cada uno distinto. **Nunca** en el código.
4. Corré a mano `probarLecturas` → Google pide permisos (Gmail, Calendar, Tasks, conexiones externas). Revisá el registro.
5. **Implementar → Nueva implementación → Aplicación web**: ejecutar como *yo*, acceso *cualquier persona*. Copiá la URL `/exec` → va a Fly como `GOOGLE_WORKSPACE_WEBHOOK_URL`.
   - "Cualquier persona" es necesario para que Fly pueda llamarla sin login de Google. La protección es `SECRETO_WEBHOOK`.
   - Cada cambio de código requiere **Implementar → Gestionar implementaciones → editar → versión nueva**; si no, la URL sigue sirviendo la versión vieja.
6. Corré a mano `instalarDisparadores` (briefing cada 10 minutos).

## Contrato del webhook (`doPost`)

`POST <GOOGLE_WORKSPACE_WEBHOOK_URL>` con JSON. Google responde con un **302** a `script.googleusercontent.com`; el cliente lo sigue con **GET** (`urllib` lo hace solo) y ahí está la respuesta.

Siempre vuelve HTTP 200: **el resultado real es el campo `ok`**. Quien llama tiene que leerlo antes de confirmar nada por WhatsApp.

Campos comunes:

| Campo | |
|---|---|
| `secreto` | obligatorio, = `SECRETO_WEBHOOK` (Apps Script no expone headers, por eso va en el cuerpo) |
| `accion` | una de las de abajo |
| `id_solicitud` | opcional en las que escriben. Si llega repetido dentro de 6 h, devuelve el resultado anterior con `"repetida": true` en vez de crear dos veces. La SuperApp usa el `idMessage` del WhatsApp. |

Errores: `{"ok": false, "error": "<código>", "detalle": "..."}` con código `json_invalido`, `sin_configurar`, `no_autorizado`, `accion_invalida`, `parametros_invalidos`, `ocupado` (otra escritura en curso con el mismo lock: reintentar) o `error_interno`.

Fechas `YYYY-MM-DD`, horas `HH:MM`, instantes ISO con offset (`2026-10-15T09:30:00-03:00`).

### Escritura

| `accion` | Parámetros | Devuelve |
|---|---|---|
| `crear_evento` | `fecha`, `titulo`, `hora_inicio?`, `hora_fin?`, `descripcion?`, `calendario?` (id; default el principal) | `id`, `calendario_id`, `todo_el_dia`, `inicio`, `fin` |
| `crear_tarea` | `titulo`, `fecha?`, `descripcion?`, `lista?` (id; default `@default`) | `id`, `lista_id`, `titulo`, `vence` |
| `completar_tarea` | `lista_id`, `tarea_id` | `id`, `lista_id`, `estado` |

Sin `hora_inicio` el evento es de todo el día. Sin `hora_fin`, dura una hora. `hora_fin` ≤ `hora_inicio` es error (no se asume "termina al día siguiente").

### Lectura (dashboard)

| `accion` | Parámetros | Devuelve |
|---|---|---|
| `listar_calendarios` | — | `calendarios: [{id, nombre, color, principal, oculto, seleccionado}]` |
| `listar_eventos` | `desde`, `hasta` (inclusive, máx. 62 días), `calendarios?` (ids) | `eventos: [{id, calendario_id, calendario, color, titulo, descripcion, ubicacion, todo_el_dia, inicio, fin}]` |
| `listar_tareas` | `listas?` (ids), `incluir_completadas?` | `listas: [{id, nombre}]`, `tareas: [{id, lista_id, lista, titulo, notas, vence, estado, padre, actualizada}]` |

| `resumen_semana` | `desde?`, `hasta?` (default hoy + 6 días), `calendarios?`, `listas?` | `eventos`, `listas`, `tareas` (lo mismo que las dos de arriba juntas) |

- **El dashboard usa `resumen_semana`**: cada llamada a la web app tarda 1–3 s más el salto del 302, así que una sola en vez de dos. Del lado de Streamlit va con cache de unos minutos (`st.cache_data(ttl=...)`).
- `listar_eventos`: los de todo el día traen `inicio`/`fin` como fecha, con **`fin` inclusive** (último día del evento). Vienen ordenados por inicio, los de todo el día primero en su fecha. `color` es el del calendario: sirve para pintar cada calendario en el dashboard.
- `listar_tareas`: por defecto solo pendientes, ordenadas por vencimiento (las sin fecha al final). `padre` ≠ null es una subtarea.

## Briefing (`reenviarBriefingAWhatsApp`)

Busca el último mail con asunto `[Briefing-WhatsApp]` de las últimas 24 h sin la etiqueta `WA-Enviado`, **acorta los links largos con TinyURL** (en paralelo; si TinyURL falla, el link queda original) y lo manda a `POST /api/briefing` con `Authorization: Bearer <SUPERAPP_TOKEN>`. Solo lo etiqueta si la SuperApp responde 200 **y** `{"ok": true}`, o sea, si el WhatsApp salió; si no, el próximo disparo reintenta.

El acortado vive acá y no en la API a propósito: Apps Script ya tiene el texto, `fetchAll` acorta todos los links a la vez, y la API de Fly queda más simple.
