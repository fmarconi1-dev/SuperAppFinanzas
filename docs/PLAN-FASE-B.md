# Plan — Fase B: briefing, agenda y cierre de mercado (ADR-0008)

**Objetivo:** que el Secretario, además de cargar gastos (Fase A), **te escriba él**: el briefing de la mañana con tus finanzas del mes, un **resumen corto del cierre de mercado** a la tarde, y que puedas agendar eventos y tareas por WhatsApp.

Mismo canal, mismo costo: **cero** (ADR-0008, `docs/WHATSAPP-CANAL.md`).

**Fuera de alcance:** dashboard y rebranding (Fase C) · conciliación (Fase D) · análisis de mercado, recomendaciones o alertas de precio. **El agente informa, no recomienda ni opera.** · **Generar el briefing**: lo arma Gemini en su propio Apps Script, en la cuenta de Google de Franco, y **se queda ahí** (decisión de Franco del 15/10/2026). Esta fase no lo toca: solo lo recibe y le suma las finanzas.

## Lo que vas a recibir

| Cuándo | Qué | Quién lo dispara |
|---|---|---|
| A la mañana (cuando llega tu mail `[Briefing-WhatsApp]`, que genera Gemini) | El briefing de Gemini, con los links acortados y al final **📊 Mis finanzas del mes** | Nuestro Apps Script (cada 10 min busca el mail) |
| **18:30 hs**, lunes a viernes | **Cierre de mercado**: EE.UU. (acciones y Treasuries) y Argentina (acciones, bonos hard dollar y curva en pesos) | Apps Script (disparador diario) |
| Cuando escribís `evento: …` / `tarea: …` | ✅ Evento agendado / ✅ Tarea creada (o el error real) | Vos |
| Cuando escribís `agenda` | Eventos de la semana y tareas pendientes | Vos |

**¿Por qué 18:30 y no 18:00?** Hasta el 31/10 Wall Street cierra a las 17:00 hora argentina, pero **desde el 1/11/2026** (fin del horario de verano en EE.UU.) cierra a las **18:00**. A las 18:00 en punto los números todavía no son de cierre. 18:30 sirve todo el año y el BYMA ya cerró (17:00).

## La regla de la ventana de 24 h (costo cero)

El briefing y el cierre de mercado los manda el bot por su cuenta. Meta solo deja mandar texto gratis si le escribiste en las últimas 24 h (ADR-0008). Por eso los dos pasan por una **cola de salida**:

1. Si la ventana está abierta (tu último mensaje fue hace menos de 23 h 50 min) → **sale en el momento**.
2. Si está cerrada → **queda guardado** y te llega apenas le escribas cualquier cosa. El primero de esos mensajes dice "Te guardé esto mientras no hablábamos".
3. No hay un tercer camino pago. El test de "nada de plantillas" sigue vigente.

Con el uso normal (cargar gastos durante el día) la ventana casi siempre está abierta a las 18:30. Si un día no le escribiste, el cierre te espera.

## Cierre de mercado — formato

Corto, con datos de cierre y variación del día, y **un párrafo de una o dos frases por bloque**. Ejemplo **ilustrativo**: los niveles se parecen a los del 15/10, pero las variaciones y los textos son inventados.

```
*📈 CIERRE 15/10*

*🇺🇸 Acciones*
S&P 500 7.744 (+0,4%) · Nasdaq 26.713 (+0,9%) · Dow 52.178 (−0,1%)
Jornada positiva liderada por el Nasdaq; el Dow quedó levemente abajo.

*🇺🇸 Treasuries*
13 sem 4,09% (+3 pb) · 5 años 4,90% (−12 pb) · 10 años 5,09% (−15 pb) · 30 años 5,43% (−17 pb)
Las tasas largas bajaron fuerte y la curva se aplanó.

*🇦🇷 Acciones*
Merval 2.859.051 (+1,2%)
Suba generalizada del panel líder.

*🇦🇷 Bonos hard dollar*
AL30 56,15 (−0,1%) · GD30 57,65 (+0,1%) · GD35 75,30 (−0,1%) · GD38 80,64 (+0,1%) · GD41 70,00 (0,0%)
Riesgo país 611 pb (−8)
Jornada sin cambios relevantes en los soberanos.

*🇦🇷 Curva en pesos*
S30O6 TEM 2,1% · S13N6 TEM 2,3% · S29E7 TEM 2,4% · T30J7 TEM 2,5% …
La curva de tasa fija subió en el tramo corto.
```

**Los párrafos se arman con reglas fijas a partir de los números, no con IA.** Es gratis, sale igual todos los días y **no puede inventar una cifra**. Por ejemplo: si los tres índices suben, "Jornada positiva"; el que más se movió, "liderada por…"; si la tasa a 10 años se mueve más de 10 pb, "las tasas largas bajaron/subieron fuerte"; si el tramo largo baja más que el corto, "la curva se aplanó". Si más adelante querés un tono más redactado, se puede sumar un modelo de IA, pero eso tiene costo y queda como mejora opcional.

**Días sin mercado:** si EE.UU. cerró (feriado) y Argentina no, sale solo Argentina, y al revés. Si cerraron los dos, no sale nada. Se detecta mirando la fecha del último precio, sin calendario de feriados a mano.

**Si una fuente no contesta,** el bloque sale con "⚠️ Sin datos de <fuente> hoy". Nunca se rellena con el dato de ayer sin decirlo (regla de `CLAUDE.md`: "no contestó" ≠ "no existe").

## Fuentes (todas gratis, sin clave, probadas el 15/10/2026)

| Bloque | Fuente | Qué trae | Ojo |
|---|---|---|---|
| Acciones EE.UU. | Yahoo `v8/finance/chart` — `^GSPC`, `^IXIC`, `^DJI` | cierre y hora del último precio | No oficial; pedir `range=5d` y calcular la variación contra el **cierre anterior** de la serie (el `chartPreviousClose` de 5 días no es el de ayer) |
| Treasuries | Yahoo — `^IRX` (13 sem), `^FVX` (5 a), `^TNX` (10 a), `^TYX` (30 a) | rendimiento en % | **No hay 2 años** en Yahoo. El oficial (treasury.gov, curva diaria) se publica tarde para las 18:30: queda como mejora |
| Merval | Yahoo `^MERV` | cierre | — |
| Bonos hard dollar | data912 `/live/arg_bonds` — `AL30D`, `GD30D`, `GD35D`, `GD38D`, `GD41D`, `AE38D` | precio en USD c/100 VN y `pct_change` | Comunitaria: puede cambiar sin aviso. Se usa la especie **D** (MEP) |
| Riesgo país | argentinadatos `/v1/finanzas/indices/riesgo-pais/ultimo` | puntos básicos y fecha | El valor puede ser del día hábil anterior: se muestra con su fecha |
| Curva en pesos | data912 `/live/arg_notes` (LECAP `S…`) y `/live/arg_bonds` (BONCAP `T…`) | precios | La TEM necesita el **valor de pago al vencimiento** de cada letra (ver Decisión 2) |

Todo esto es **lectura de unos pocos precios por día**: no viola la regla de "nada de cómputo pesado en el servidor web".

## Decisiones — ✅ confirmadas por Franco el 15/10/2026

> **Elegido:** párrafos por **reglas fijas** (1), TEM con **tabla chica en el repo** (2a), CER **solo variación de precio** (3) y cierre a las **18:30** de lunes a viernes (4). Lo de abajo queda como registro de las alternativas.

1. **Párrafos: reglas fijas (recomendado) o IA.** Reglas: gratis, sin inventos. IA: más natural, pero con costo y con riesgo de cifras mal dichas.
2. **TEM de la curva en pesos.** Para calcular la tasa de una LECAP/BONCAP hace falta cuánto paga al vencer.
   - **(a) Recomendado: tabla chica en el repo** (`places/finanzas/core/curva_pesos.toml` o similar) con ticker, vencimiento y pago final de las 6–8 letras de referencia. Se actualiza a mano cuando hay licitación nueva (cada ~2 semanas, un renglón). Cero dependencias.
   - **(b) Docta**: trae los cronogramas sola (el código está en el historial, `886b67c`), pero depende de credenciales y de un cupo de 15 consultas por día.
   - **(c) Sin TEM:** solo variación de precio. Es lo más simple, pero no es "la curva".
3. **Bonos CER** (`TX26`, `TX28`, `TZX…`): en la v1 solo variación de precio. La tasa real necesita proyectar el CER, y eso no es "poco análisis".
4. **Horario:** 18:30 de lunes a viernes, por el cambio de hora de EE.UU.

## Diseño

### Archivos nuevos o tocados

| Archivo | Qué |
|---|---|
| `core/mercado/fuentes.py` | Clientes de Yahoo, data912 y argentinadatos con timeout y su propia excepción (`FuenteNoDisponible`). Normaliza data912 (precios c/100 VN). Módulo nuevo y mínimo; **no** revive el `core/market_data/` retirado (ADR-0007) |
| `places/finanzas/core/cierre_mercado.py` | Puro: datos → texto (formato de arriba y párrafos por reglas). Testeable sin red |
| `places/finanzas/core/briefing.py` | Puro: texto del mail + finanzas del mes → mensaje (reusa `comandos.resumen_mes`) |
| `places/finanzas/core/comandos.py` | `evento:`, `tarea:`, `agenda` |
| `core/api/servidor.py` | `POST /api/briefing`, `POST /api/mercado/cierre`, cola de salida, entrega de pendientes |
| `core/api/google.py` | Cliente del Apps Script: `crear_evento`, `crear_tarea`, `resumen_semana`; maneja el 302 y **lee `ok`** |
| `core/db.py` | **M18**, aditiva: `whatsapp_salientes` (id, tipo, texto, creado_en, enviado_en, error) |
| `integraciones/google-apps-script/Codigo.gs` | Disparador nuevo `avisarCierreDeMercado` (18:30, lunes a viernes) |

### Endpoints nuevos (autenticados con `Authorization: Bearer <SUPERAPP_API_TOKEN>`)

| Ruta | Qué |
|---|---|
| `POST /api/briefing` `{"texto": "..."}` | Le suma el bloque de finanzas y lo manda o lo encola. Devuelve `{"ok": true, "estado": "enviado" | "en_cola"}` |
| `POST /api/mercado/cierre` | Junta los datos, arma el mensaje y lo manda o lo encola. Mismo formato de respuesta |

`SUPERAPP_API_TOKEN` sin valor por defecto: si falta, esas rutas responden 503 (mismo patrón que el webhook). El token `franquito77` del borrador original está quemado: no se usa.

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

1. **M18 + cola de salida + entrega de pendientes** (sin esto, nada de lo que el bot inicia es gratis seguro).
2. **Cierre de mercado** (fuentes + texto + endpoint), con tests de las reglas de los párrafos y de los días sin mercado.
3. **Briefing** (`/api/briefing`). Entrada: el mail `[Briefing-WhatsApp]` que ya manda el Apps Script de Gemini, **sin tocar ese script**. Confirmar con Franco el asunto exacto del mail y que llega a la misma cuenta de Google donde se instala nuestro Apps Script.
4. **Apps Script**: instalarlo (`integraciones/google-apps-script/README.md`), los disparadores de briefing y cierre, y los comandos `evento:` / `tarea:` / `agenda`.
5. Deploy y pruebas reales: un cierre a las 18:30, un briefing a la mañana, un evento y una tarea desde el celular.

## Tests (gate: suite completa en verde, 0 skipped)

- Cola: ventana abierta → envía; cerrada → encola; el próximo mensaje entrante entrega lo pendiente en orden y lo marca enviado; un fallo de envío queda en `error`, no se pierde.
- Cierre: formato exacto con datos sintéticos; párrafos por reglas (sube todo, baja todo, mixto, aplanamiento); feriado de un solo mercado; fuente caída → "⚠️ Sin datos"; TEM contra un caso calculado a mano.
- Fuentes: parseo de respuestas reales guardadas como fixtures (sin red en los tests).
- Briefing: links intactos, bloque de finanzas igual al `resumen`.
- Google: `ok: false` no confirma; el 302 se sigue; `id_solicitud` viaja.
- Endpoints: sin token → 401; token mal → 401; sin configurar → 503.
- Costo cero: el test de plantillas cubre los archivos nuevos.

## Cierre de la fase

Bitácoras selladas, `EN-HUMANO.md`, `ESTADO.md`, `ROADMAP.md`, `docs/DEPLOY.md` (secretos nuevos) y `docs/RUNBOOK.md` ("el cierre no llegó"). Commit en `main`; push y deploy, Franco.
