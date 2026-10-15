# Prompt de inicio — Fase B (briefing, agenda y cierre de mercado)

Copiá el bloque de abajo en una sesión nueva, con acceso a la carpeta `SuperAppFinanzas/`.

Estado al escribirlo (15/10/2026): **Fase A cerrada en producción** (el Secretario carga gastos, responde `resumen` y `deshacer` por WhatsApp, sin costo). Plan de la Fase B escrito y con sus 4 decisiones confirmadas. Suite: 471 passed, 0 skipped.

---

> Soy Franco. Trabajamos en mi **SuperApp**, que se está convirtiendo en mi secretario personal (ADR-0008): Streamlit + SQLite en Fly.io (`superapp-finanzas`), con una API stdlib detrás de nginx que atiende mi WhatsApp (Meta Cloud API, **costo cero sí o sí**). **Trabajamos siempre en la rama `main`**; el push y el deploy los hago yo.
>
> ## Antes de tocar nada, leé en este orden y confirmame que entendiste
>
> 1. `ESTADO.md` — foto actual y próximo paso.
> 2. **`docs/PLAN-FASE-B.md`** — el plan de esta fase, con las decisiones ya confirmadas. **Leelo entero.**
> 3. `docs/decisiones/ADR-0008-enfoque-secretario.md` y `docs/WHATSAPP-CANAL.md` — por qué el costo es cero y qué no se puede hacer (plantillas).
> 4. `MAPA.md` — para ubicar código sin barrer el repo.
> 5. `core/api/BITACORA.md` y `places/finanzas/core/BITACORA.md` — sobre todo las **trampas** (el 9 de los números argentinos, el orden del POST, el hilo trabajador).
> 6. `integraciones/google-apps-script/README.md` — el puente con Google (ya escrito, **sin instalar todavía**).
> 7. `claude.md` y `GUIA-DE-TRABAJO.md` — reglas duras.
>
> ## Qué hay que hacer (Fase B)
>
> - **Briefing matutino:** lo genera **Gemini, en su propio Apps Script de mi cuenta de Google, y se queda ahí**: no lo toques. Llega como mail con asunto `[Briefing-WhatsApp]`. Nuestro Apps Script lo levanta, acorta los links y lo manda a `POST /api/briefing`, que le suma mis finanzas del mes y me lo manda por WhatsApp.
> - **Cierre de mercado a las 18:30, lunes a viernes:** EE.UU. (S&P 500, Nasdaq, Dow; Treasuries 13 semanas, 5, 10 y 30 años) y Argentina (Merval; hard dollar AL30, GD30, GD35, GD38, GD41, AE38 en especie D; riesgo país; curva en pesos LECAP/BONCAP con TEM; CER solo variación). Datos de cierre, variación del día y **un párrafo corto por bloque, armado por reglas fijas (sin IA)**. Fuentes gratis ya probadas: Yahoo, data912 y argentinadatos.
> - **Comandos** `evento:`, `tarea:` y `agenda`, vía el Apps Script.
> - Todo lo que el bot manda por su cuenta pasa por una **cola de salida**: sale si la ventana de 24 h de Meta está abierta y, si no, espera a mi próximo mensaje. **Nunca plantillas.**
>
> ## Decisiones ya tomadas (no las reabras)
>
> Párrafos por reglas · TEM con una **tabla chica en el repo** (ticker, vencimiento, pago final) · CER solo variación de precio · cierre a las **18:30** (desde el 1/11 Wall Street cierra a las 18:00 hora argentina).
>
> ## Antes de codear, preguntame
>
> 1. El asunto exacto del mail de Gemini, y si llega a la misma cuenta de Google donde vamos a instalar nuestro Apps Script.
> 2. Qué letras van en la curva en pesos (6–8 de referencia) y sus pagos finales, o de dónde los saco.
>
> ## Orden de trabajo
>
> Seguí el "Orden de trabajo" del plan: **(1) M18 + cola de salida** → (2) cierre de mercado → (3) briefing → (4) instalar el Apps Script y los comandos → (5) deploy y pruebas reales. Un paso a la vez, con la suite en verde antes de pasar al siguiente.
>
> ## Reglas que no se rompen
>
> - Nunca commitear `data/`, `*.db`, `*.xlsx` ni `.env`. Ningún secreto con valor por defecto.
> - **Costo cero:** solo `"type": "text"`; el test de plantillas cubre todo archivo nuevo del canal.
> - "No contestó" ≠ "no existe": una fuente caída se nombra ("⚠️ Sin datos de … hoy"), nunca se rellena con el dato de ayer.
> - El agente **informa; no recomienda ni opera**.
> - Suite con el Python del venv: `.venv\Scripts\python.exe -m pytest -q` (0 skipped en local).
> - Al cerrar: bitácoras selladas (`python scripts/indexar.py . --sellar <carpeta>`), `EN-HUMANO.md`, `ESTADO.md` y `ROADMAP.md`, commit en `main` y avisarme para el push y el deploy.
