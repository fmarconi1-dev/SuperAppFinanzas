# Plan — Fase B: briefing, cierre de mercado y agenda (ADR-0008)

**Objetivo:** que el Secretario, además de cargar gastos (Fase A), **te escriba él**: el briefing de la mañana y el **cierre de mercado** a la tarde, **tal cual los arma Gemini**, y que puedas agendar eventos y tareas por WhatsApp.

Mismo canal, mismo costo: **cero** (ADR-0008, `docs/WHATSAPP-CANAL.md`).

**Lo que ya funciona no se toca** (Franco, 15/10/2026): la Fase A queda como está, y **los dos briefings los genera Gemini** en su propio Apps Script, en la cuenta de Google de Franco, y los manda por mail. Esta fase **no genera contenido de mercado**: recibe esos mails, les suma lo nuestro y los manda por WhatsApp.

**Fuera de alcance:** dashboard y rebranding (Fase C) · conciliación (Fase D) · traer datos de mercado o redactar análisis desde la SuperApp · recomendaciones, alertas u operaciones. **El agente informa; no recomienda ni opera.**

## Lo que vas a recibir

| Cuándo | Qué | Lo genera | Lo trae a WhatsApp |
|---|---|---|---|
| A la mañana | Briefing (mail `[Briefing-WhatsApp] Briefing Matutino y Agenda - DD/MM/AAAA`), **tal cual** | Gemini (como hoy) | Nuestro Apps Script → `/api/briefing` |
| **18:30**, lunes a viernes | **Cierre de mercado** (mail `[Briefing-WhatsApp] Cierre de Mercado - DD/MM/AAAA`): EE.UU. acciones y Treasuries; Argentina acciones, hard dollar, riesgo país y curva en pesos | **Gemini** (ya lo genera) | Nuestro Apps Script → `/api/briefing` |
| Cuando escribís `evento: …` / `tarea: …` | ✅ Evento agendado / ✅ Tarea creada (o el error real) | — | Vos → Apps Script |
| Cuando escribís `agenda` | Eventos de la semana y tareas pendientes | — | Vos → Apps Script |

**Los asuntos reales (confirmados por Franco el 15/10/2026)** comparten la etiqueta `[Briefing-WhatsApp]` y se distinguen por lo que sigue: "Briefing Matutino y Agenda" o "Cierre de Mercado". **Gemini ya genera los dos.** `docs/PEDIDO-GEMINI-CIERRE.md` queda como guía opcional, por si Franco quiere ajustar el formato o las reglas del cierre.

**¿Por qué 18:30 y no 18:00?** Hasta el 31/10 Wall Street cierra a las 17:00 hora argentina, pero **desde el 1/11/2026** (fin del horario de verano en EE.UU.) cierra a las **18:00**. A las 18:00 en punto los números todavía no son de cierre. 18:30 sirve todo el año, y el BYMA ya cerró (17:00). Nuestro Apps Script busca mails cada 10 minutos, así que el cierre llega a WhatsApp alrededor de las 18:40.

## La regla de la ventana de 24 h (costo cero)

El briefing y el cierre los manda el bot por su cuenta, y Meta solo deja mandar texto gratis si le escribiste en las últimas 24 h (ADR-0008). Por eso los dos pasan por una **cola de salida**:

1. Si la ventana está abierta (tu último mensaje fue hace menos de 23 h 50 min) → **sale en el momento**.
2. Si está cerrada → **queda guardado** y te llega apenas le escribas cualquier cosa, con un aviso: "Te guardé esto mientras no hablábamos".
3. No hay un tercer camino pago. El test de "nada de plantillas" sigue vigente.

Con el uso normal (cargar gastos durante el día), la ventana casi siempre está abierta a las 18:30.

## Mudanza desde CallMeBot

**Hoy los dos briefings llegan a WhatsApp por CallMeBot** (Franco, 15/10/2026). Los mails llegan a `fmarconi1@gmail.com`, y los reenvía un Apps Script aparte del de Gemini, que busca `[Briefing-WhatsApp]` en Gmail, los etiqueta `WA-Enviado` y los manda por CallMeBot.

**Resuelto el 16/10/2026, al ver ese script:** como el de CallMeBot ya es un reenviador de Gmail con la misma función, la misma etiqueta y el mismo filtro que nuestro puente, se **reemplaza entero** por `integraciones/google-apps-script/Codigo.gs`, que ya trae la corrección. El script de Gemini no se toca. Así CallMeBot se apaga en el mismo cambio y queda un solo script para todo: reenvío y agenda.

Qué se corrigió respecto del de CallMeBot: manda a `POST /api/briefing` con `tipo` (cierre si el asunto dice "Cierre de Mercado"); procesa todos los pendientes en orden, no uno por corrida; sin `$`→`ARS` ni bloques de 650; lock contra corridas solapadas; nada de número ni claves en el código. Pasos de la mudanza: `integraciones/google-apps-script/README.md`, sección "Mudanza desde CallMeBot".

**Orden obligatorio:** primero se despliega `/api/briefing`, después se cambia el script. Si se hace al revés, no llega ningún briefing hasta el deploy. La clave de CallMeBot quedó expuesta en un chat el 16/10: se da por quemada.

## Decisiones (15/10/2026)

- ✅ **Lo genera Gemini, por mail, igual que el briefing.** Reemplaza el diseño anterior, en el que la SuperApp traía los datos (Yahoo, data912, argentinadatos) y armaba los párrafos por reglas. Ese diseño ya no se hace. Los criterios que Franco había confirmado pasan como **instrucciones del pedido a Gemini**: poco análisis, un párrafo corto por bloque que solo describe los números mostrados, CER solo variación de precio, y **ninguna cifra sin fuente**.
- ✅ **18:30, lunes a viernes.**
- ⚠️ **Exactitud de los números:** quedan a cargo de Gemini. La SuperApp no los puede validar. El pedido le exige fecha de cada dato, "sin dato" antes que inventar, y separar lo medido de lo comentado. Si un día un número no cierra, se ajusta el pedido, no el código.

## Diseño

### Archivos nuevos o tocados

| Archivo | Qué |
|---|---|
| `places/finanzas/core/briefing.py` | Puro: valida el tipo y el texto, y lo devuelve **tal cual**. Decisión de Franco (16/10): *"El briefing es una cosa, mis finanzas son otra"*; las finanzas se piden aparte con `resumen` |
| `places/finanzas/core/comandos.py` | `evento:`, `tarea:`, `agenda` |
| `core/api/servidor.py` | `POST /api/briefing` (con `tipo`), cola de salida, entrega de pendientes al recibir un mensaje |
| `core/api/google.py` | Cliente del Apps Script: `crear_evento`, `crear_tarea`, `resumen_semana`; sigue el 302 y **lee `ok`** |
| `core/db.py` | **M18**, aditiva: `whatsapp_salientes` (id, tipo, texto, creado_en, enviado_en, error) |
| `integraciones/google-apps-script/Codigo.gs` | El reenvío ya busca `[Briefing-WhatsApp]`, así que agarra los dos mails. Cambios: (1) manda `tipo: "cierre"` si el asunto contiene "Cierre de Mercado" y `briefing` si no; (2) procesa **todos** los hilos sin etiquetar, no solo el último (hoy toma uno por corrida); (3) los manda en orden de llegada |

### Endpoint (autenticado con `Authorization: Bearer <SUPERAPP_API_TOKEN>`)

| Ruta | Qué |
|---|---|
| `POST /api/briefing` `{"texto": "...", "tipo": "briefing" \| "cierre"}` | Arma el mensaje y lo manda o lo encola. Devuelve `{"ok": true, "estado": "enviado" \| "en_cola"}`. Sin `tipo`, `briefing` (compatibilidad con el Apps Script ya escrito) |

`SUPERAPP_API_TOKEN` sin valor por defecto: si falta, la ruta responde 503 (mismo patrón que el webhook). El token `franquito77` del borrador original está quemado: no se usa.

### Comandos

| Mensaje | Hace |
|---|---|
| `evento: 20/10, 15:00, 16:00, Dentista, Llevar estudios` | `crear_evento` → "✅ Evento agendado: Dentista (20/10 15:00–16:00)" |
| `evento: 20/10, Cumple de Juan` | evento de todo el día |
| `tarea: 25/10, Pagar seguro` / `tarea: Llamar al contador` | `crear_tarea` → "✅ Tarea creada: …" |
| `agenda` | `resumen_semana` → eventos de hoy a 7 días + tareas pendientes |

Las fechas y horas se validan con el mismo rigor que en la Fase A: una fecha imposible se repregunta. Se confirma **solo** si el Apps Script responde `ok: true`. El `id_solicitud` es el wamid, así un reintento de Meta no crea dos eventos.

### Variables de entorno nuevas

`SUPERAPP_API_TOKEN` · `GOOGLE_WORKSPACE_WEBHOOK_URL` (la URL `/exec`) · `GOOGLE_WORKSPACE_SECRET` (= `SECRETO_WEBHOOK` del Apps Script). Sin defaults; a `.env.example` sin valores.

## Orden de trabajo

> ✅ **FASE B CERRADA en producción (17/10/2026).** Pasos 1–5 hechos: cola de salida y `/api/briefing` (M18); mudanza desde CallMeBot (`Reenvio.gs`, 16/10); agenda (`core/api/google.py`, `agenda.py`, `Codigo.gs` publicado como aplicación web, 17/10). Franco lo probó punta a punta.

1. **M18 + cola de salida + entrega de pendientes** (sin esto, nada de lo que el bot inicia es gratis seguro).
2. **`/api/briefing` con `tipo`** (los dos tal cual, sin agregados).
3. **Apps Script:** reenvío de los dos asuntos, instalación (`integraciones/google-apps-script/README.md`) y comandos `evento:` / `tarea:` / `agenda`.
4. **Mudanza desde CallMeBot** (ver arriba): con `/api/briefing` ya desplegado, reemplazar el script de CallMeBot por `Codigo.gs`, que lo apaga en el mismo paso. Confirmar que el cierre sale a las **18:30** (desde el 1/11 Wall Street cierra a las 18:00 hora argentina).
5. Deploy y pruebas reales: un cierre a las 18:30, un briefing a la mañana, un evento y una tarea desde el celular.

**Asuntos confirmados (15/10/2026):** `[Briefing-WhatsApp] Briefing Matutino y Agenda - DD/MM/AAAA` y `[Briefing-WhatsApp] Cierre de Mercado - DD/MM/AAAA`, los dos a `fmarconi1@gmail.com` (la misma cuenta del Apps Script). El script de CallMeBot ya se vio (16/10) y su reemplazo está en `Codigo.gs`. Queda por confirmar a qué hora sale el cierre.

## Tests (gate: suite completa en verde, 0 skipped)

- Cola: ventana abierta → envía; cerrada → encola; el próximo mensaje entrante entrega lo pendiente en orden y lo marca enviado; un fallo de envío queda en `error`, no se pierde.
- Briefing: el texto llega intacto en los dos tipos, **sin nada agregado** (ni finanzas ni montos); un texto largo se parte en mensajes de 4096 sin cortar renglones.
- Google: `ok: false` no confirma; el 302 se sigue; `id_solicitud` viaja.
- Endpoint: sin token → 401; token mal → 401; sin configurar → 503.
- Costo cero: el test de plantillas cubre los archivos nuevos.

## Cierre de la fase

Bitácoras selladas, `EN-HUMANO.md`, `ESTADO.md`, `ROADMAP.md`, `docs/DEPLOY.md` (secretos nuevos) y `docs/RUNBOOK.md` ("el briefing o el cierre no llegó"). Commit en `main`; push y deploy, Franco.
