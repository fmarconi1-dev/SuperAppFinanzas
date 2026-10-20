# Puente Google ↔ SuperApp (Apps Script)

Código que corre en **Google Apps Script**, no en Fly. Vive en el repo para versionarlo; se pega a mano en el editor de Apps Script (o se sube con `clasp`).

| Archivo | Qué es |
|---|---|
| `Reenvio.gs` | Reenvío del briefing matutino de Gemini (Gmail → SuperApp → WhatsApp), con el tablero de `Mercado.gs`, y envío del cierre de las 18:30. **Reemplaza al script de CallMeBot.** |
| `Mercado.gs` | Números de mercado armados por código (ADR-0010): el tablero del matutino y el cierre entero. Va en el **mismo proyecto** que `Reenvio.gs` (se necesitan los dos). |
| `Codigo.gs` | Agenda: webhook SuperApp → Calendar/Tasks, para los comandos `evento:` / `tarea:` / `agenda`. Va en el **mismo proyecto** que `Reenvio.gs` y se publica como aplicación web. |
| `appsscript.json` | Manifiesto: zona horaria Buenos Aires, servicio avanzado **Tasks**, web app. |

## Instalación (una sola vez)

1. En el proyecto de Apps Script del reenvío (el que hoy usa CallMeBot), agregá un archivo `Codigo.gs` y pegá el de acá. `Reenvio.gs` ya tiene que estar (ver "Mudanza desde CallMeBot").
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
6. El disparador del reenvío (cada 10 minutos) ya existe si migraste desde CallMeBot; si no, corré a mano `instalarDisparadores`.
7. En Fly: `fly secrets set GOOGLE_WORKSPACE_WEBHOOK_URL=<la URL /exec> GOOGLE_WORKSPACE_SECRET=<el mismo SECRETO_WEBHOOK> -a superapp-finanzas`. Probalo mandándole `agenda` al Secretario.

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

## Briefings (`reenviarBriefingAWhatsApp`)

El disparador de cada 10 minutos hace dos cosas, bajo un lock que evita que dos corridas solapadas manden lo mismo dos veces:

1. **El matutino de Gemini:**
   - Busca los mails con asunto `[Briefing-WhatsApp]` de las últimas 24 h que todavía no tienen la etiqueta `WA-Enviado`, y los procesa del más viejo al más nuevo.
   - En cada uno pone el **tablero de `Mercado.gs`**: en el renglón `[TABLERO]` que deja Gemini (`docs/PEDIDO-GEMINI.md`), o en lugar del bloque "TABLERO" que arme Gemini.
   - Acorta los links largos con TinyURL, en paralelo. Si TinyURL falla, el link queda como estaba.
   - Lo manda a `POST /api/briefing` con `Authorization: Bearer <SUPERAPP_TOKEN>` y `tipo: "briefing"`.
   - Lo etiqueta solo si la SuperApp responde 200 **y** `{"ok": true}`: salió, o quedó en la cola hasta que le escribas al bot. Si un mail falla, corta ahí y el próximo disparo reintenta sin saltearse el orden.
   - Un mail "Cierre de Mercado" de Gemini se **descarta**: lo etiqueta sin mandarlo y lo anota en el registro.
2. **El cierre de mercado** (`cierrePendiente_`, en `Mercado.gs`):
   - De lunes a viernes, desde las 18:30 y si el cierre de hoy todavía no salió (propiedad `ULTIMO_CIERRE`), lo arma y lo manda con `tipo: "cierre"` e `id: "cierre-AAAA-MM-DD"`. Con ese `id`, si se reintenta, la SuperApp no lo duplica.
   - Si la SuperApp no lo toma, la corrida siguiente reintenta.

### Fuentes de `Mercado.gs`

| Dato | Fuente |
|---|---|
| S&P 500, Nasdaq, Dow, Brent, oro | Yahoo (`/v8/finance/chart`, con User-Agent de navegador) |
| UST 2, 10 y 30 años | Tesoro de EE.UU., CSV de la curva diaria (tarda unos 20 s). Si a esa hora no publicó la de hoy y Yahoo sí tiene el día, el 10 y el 30 salen de Yahoo (`^TNX`, `^TYX`) |
| MSCI MERVAL | BYMA (`index-price`, símbolo `MMSCI`; base 100.000 desde el 19/10/2026) |
| Dólares | dolarapi (hoy) contra argentinadatos (día hábil anterior) |
| Riesgo país | argentinadatos (suele venir con un día de atraso: sale con `[fecha]`) |
| Bonos hard dollar, Lecap, Boncap, CER | data912 (sin fecha: se usa la de la rueda del BYMA) |

Una fuente que falla sale como `s/d` en el texto y queda en el registro (`Mercado: <fuente>: <error>`). Un dato que no es de hoy lleva `[DD/MM]`.

### Instalar o actualizar el reenvío con `Mercado.gs` (19/10/2026)

1. En el proyecto de Apps Script, agregá un archivo **`Mercado.gs`** y pegá el de acá. **Reemplazá `Reenvio.gs`** por el de acá. `Codigo.gs` y `appsscript.json` no cambian.
2. Corré a mano **`probarMercado`**. Muestra en el registro el tablero y el cierre de hoy, **sin mandar nada**, y al final cuáles fuentes fallaron, si falló alguna. La primera vez Google pide permiso para conexiones externas.
   - Si **Yahoo** sale con error (429 o 403: Yahoo a veces rechaza a los servidores de Google), avisá: el plan B es leer los índices de una planilla con `GOOGLEFINANCE`.
3. Corré a mano **`instalarDisparadores`**: deja un único disparador cada 10 minutos. **El que venía del script de CallMeBot corría cada una hora** (visto el 20/10/2026 en *Activadores* y *Ejecuciones*: corridas a las :02). Con ese, el matutino salía hasta una hora después de llegar el mail y el cierre a las 19:02. Para verificar, en *Ejecuciones* las corridas tienen que aparecer cada 10 minutos.
4. En Gemini: pegá el pedido de `docs/PEDIDO-GEMINI.md`, que da de baja el cierre y rearma el matutino.

## Mudanza desde CallMeBot (16/10/2026)

Hasta ahora estos mails los reenviaba por CallMeBot un script con **la misma función** `reenviarBriefingAWhatsApp`, la misma etiqueta `WA-Enviado` y el mismo filtro. Este archivo es su reemplazo directo. **Orden, para no quedarte sin briefings ni recibirlos dos veces:**

1. **Primero** tiene que estar desplegado en la SuperApp `POST /api/briefing` (Fase B, pasos 1–2) y cargado `SUPERAPP_API_TOKEN` en `fly secrets`. **Hasta entonces, el script de CallMeBot sigue como está.**
2. En el proyecto de Apps Script donde hoy está el de CallMeBot: **borrá todo el código y pegá `Reenvio.gs`**. El manifiesto no hace falta tocarlo para el reenvío.
3. **Configuración del proyecto → Propiedades del script**: `SUPERAPP_URL` = `https://superapp-finanzas.fly.dev` y `SUPERAPP_TOKEN` = el mismo valor que `SUPERAPP_API_TOKEN` en Fly. Para el reenvío no hace falta más: `Codigo.gs`, `SECRETO_WEBHOOK` y la implementación como aplicación web son para la agenda, más adelante.
4. El disparador cada 10 minutos que ya tenías **sigue sirviendo**, porque llama a la misma función. Si querés dejarlo prolijo, corré `instalarDisparadores`.
5. Probalo con el próximo mail. Si llegó por el Secretario, CallMeBot ya quedó apagado: su código no está más en el proyecto.
6. **La clave de CallMeBot (`API_KEY`) se pegó en un chat el 16/10: tomala como quemada.** Ya no se usa, así que no hay que cargarla en ningún lado.

Diferencias con el script de CallMeBot: no cambia `$` por `ARS` (era para el PHP de CallMeBot), no parte en bloques de 650 caracteres con esperas de 6 s (el Secretario parte en 4.096 solo), procesa todos los pendientes y no solo el último, y no tiene ni el número ni claves escritas en el código.

El acortado vive acá y no en la API a propósito: Apps Script ya tiene el texto, `fetchAll` acorta todos los links a la vez, y la API de Fly queda más simple.
