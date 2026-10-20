# Pedido para Gemini — dar de baja el cierre y rearmar el matutino (19/10/2026)

**Por qué.** El 19/10 el matutino trajo los números del jueves 15/10 y el cierre, los del viernes 16/10, los dos como si fueran de hoy (ADR-0010). Desde ahora, **los números los arma `Mercado.gs`** a partir de las fuentes, y Gemini se queda con la agenda y las noticias.

**Cómo se usa.** Pegá el bloque de abajo **en la conversación de Gemini donde están las acciones programadas**, y fijate que te conteste lo del punto 3. Si Gemini no puede borrar o editar una acción desde el chat, hacelo a mano en la app de Gemini, en la sección de **acciones programadas** del menú, y usá el texto del punto 2 como instrucciones nuevas.

**Hacelo después de pegar `Mercado.gs` y el `Reenvio.gs` nuevo en el Apps Script.** Si queda al revés, igual no se rompe nada:

- Un cierre de Gemini que llegue igual se descarta y no sale por WhatsApp.
- Si el matutino no trae el renglón `[TABLERO]`, el script reemplaza el bloque "TABLERO" que arme Gemini.

## El pedido (copiar desde acá)

```
Necesito que actualices mis acciones programadas. Desde hoy las cotizaciones (dólar, riesgo país, índices, tasas, commodities, bonos) las arma un script mío a partir de fuentes con fecha: vos te quedás con la agenda y las noticias.

1. DAR DE BAJA
Eliminá la acción programada de la tarde que me manda el mail "[Briefing-WhatsApp] Cierre de Mercado - DD/MM/AAAA". No la reemplaces por otra ni la pauses: borrala.

2. MODIFICAR la acción del briefing de la mañana
Mantené el mismo horario y el mismo asunto del mail, exacto: "[Briefing-WhatsApp] Briefing Matutino y Agenda - DD/MM/AAAA" (un script lo busca por ese asunto; no le cambies ni un carácter). Primero copiame sus instrucciones actuales completas. Después dejalas así: el formato y las reglas de abajo mandan; de las instrucciones viejas conservá solo lo que no choque con ellas (por ejemplo, medios preferidos o el tono) y avisame qué conservaste:

---
Armá mi briefing matutino de hoy en español rioplatense, en texto plano para leer en WhatsApp (negritas solo con *asteriscos*; sin tablas, sin HTML, sin markdown de títulos). Usá exactamente este formato:

BRIEFING MATUTINO & AGENDA - DD/MM/AAAA

📌 SÍNTESIS EJECUTIVA
Dos o tres frases con lo más importante del día: mi agenda y los temas principales de las noticias de abajo.

🗓️ AGENDA & TAREAS PENDIENTES
* Hoy <día> DD/MM:
  - Personal: <eventos de mi calendario personal, con horario, o "todo el día">
  - Libertad y Progreso: <eventos de ese calendario, con horario>
* Mañana <día> DD/MM:
  - (igual que hoy)
* Próximas tareas en Google Tasks:
  - [DD/MM] <tarea pendiente>, ordenadas por vencimiento (primero las más próximas)
Si un calendario no tiene nada ese día, escribí "Sin compromisos agendados".

[TABLERO]

📰 NOTICIAS DESTACADAS

🇦🇷 POLÍTICA Y ECONOMÍA ARGENTINA
* <Título corto>: una o dos frases. (<Medio>: <link>)
(tres noticias)

🌐 FINANZAS MUNDIALES
(tres noticias, mismo formato)

🌍 PANORAMA INTERNACIONAL
(tres noticias, mismo formato)

REGLAS
- El renglón [TABLERO] va solo y tal cual, con una línea en blanco antes y otra después. Ahí mi script pone las cotizaciones. No armes un tablero ni listes cotizaciones en ninguna parte.
- Ninguna cifra de mercado en todo el briefing, ni en la síntesis ni en las noticias: nada de precios, niveles de índices, tasas, dólar, riesgo país, precios de commodities ni variaciones porcentuales. Si una noticia es sobre mercados, contá qué pasó y por qué, sin números (por ejemplo: "Wall Street cerró en baja por temores sobre la deuda de las tecnológicas"). Las demás cifras sí van: montos de un préstamo, resultados de encuestas, fechas.
- Solo noticias publicadas en las últimas 24 horas (un lunes, desde el viernes a la tarde). Antes de usar una nota, fijate su fecha de publicación; si no podés confirmarla, no la uses. No presentes como de hoy algo que pasó antes.
- Cada noticia con el link directo a la nota, no a la portada del medio. No repitas el mismo link en dos noticias y, si se puede, usá medios distintos.
- Si en una sección no encontrás tres noticias confiables, poné las que tengas. Nunca inventes una noticia, un link ni un dato.
- Hechos, no opinión: nada de pronósticos, recomendaciones ni "conviene".
- Menos de 3.000 caracteres en total.
---

3. CONFIRMAME
- Qué acción programada borraste (nombre y horario).
- Las instrucciones de la acción de la mañana tal como quedaron guardadas, copiadas completas.
- Si alguno de los dos cambios no lo pudiste hacer, decímelo claramente para que lo haga a mano.
```

## Qué cambia respecto de antes

- **El cierre de la tarde no sale más de Gemini.** Lo arma `Mercado.gs` y sale desde las 18:30, de lunes a viernes, por el mismo disparador de cada 10 minutos.
- **El matutino:**
  - Gemini deja el renglón `[TABLERO]` y el script pone ahí los números.
  - Nada de cifras de mercado en la síntesis ni en las noticias. El 19/10 las noticias repetían números viejos, como "Dow Jones +1,08%".
  - Las notas tienen que ser de las últimas 24 horas, con fecha confirmada.
  - El mismo link no puede ir en dos noticias. El 19/10 se repitió uno del Cronista.
