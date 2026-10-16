# Prompt de inicio — Fase B (briefing, cierre de mercado y agenda)

Copiá el bloque de abajo en una sesión nueva, con acceso a la carpeta `SuperAppFinanzas/`.

Estado al escribirlo (15/10/2026): **Fase A cerrada en producción** (el Secretario carga gastos, responde `resumen` y `deshacer` por WhatsApp, sin costo). Plan de la Fase B escrito: los dos briefings los genera Gemini por mail y la SuperApp solo los reenvía. Suite: 471 passed, 0 skipped.

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
> - **Lo que ya funciona no se toca.** La Fase A queda como está.
> - **Los dos briefings los genera Gemini, en su propio Apps Script de mi cuenta de Google, y los manda por mail.** No toques ese script ni generes contenido de mercado desde la SuperApp:
>   - **Mañana:** mail `[Briefing-WhatsApp] Briefing Matutino y Agenda - DD/MM/AAAA` (como hoy).
>   - **Cierre de mercado, 18:30 de lunes a viernes:** mail `[Briefing-WhatsApp] Cierre de Mercado - DD/MM/AAAA`. Gemini ya lo genera; `docs/PEDIDO-GEMINI-CIERRE.md` es una guía opcional por si lo ajusto.
> - **Hoy los dos ya me llegan a WhatsApp por CallMeBot**, y llegan a mi mail `fmarconi1@gmail.com` (la misma cuenta del Apps Script). Los quiero **mudar al Secretario** y apagar CallMeBot en el mismo paso, para no recibir todo dos veces. Ver la sección "Mudanza desde CallMeBot" del plan.
> - **Nuestra parte:** nuestro Apps Script levanta los dos mails (busca `[Briefing-WhatsApp]`; es cierre si el asunto dice "Cierre de Mercado"), acorta los links y los manda a `POST /api/briefing` con `tipo` (`briefing` o `cierre`). Al briefing la SuperApp le suma mis finanzas del mes; al cierre, nada. Los dos salen por WhatsApp.
> - **Comandos** `evento:`, `tarea:` y `agenda`, vía el Apps Script.
> - Todo lo que el bot manda por su cuenta pasa por una **cola de salida**: sale si la ventana de 24 h de Meta está abierta y, si no, espera a mi próximo mensaje. **Nunca plantillas.**
>
> ## Antes de codear, preguntame
>
> 1. (Resuelto el 16/10: el script de CallMeBot ya se vio y su reemplazo está en `integraciones/google-apps-script/Codigo.gs`; ver "Mudanza desde CallMeBot" en el plan.)
> 2. A qué hora sale hoy el de cierre (tiene que ser 18:30: desde el 1/11 Wall Street cierra a las 18:00 hora argentina).
>
> ## Orden de trabajo
>
> Seguí el "Orden de trabajo" del plan: **(1) M18 + cola de salida** → (2) `/api/briefing` con `tipo` → (3) Apps Script (instalación y comandos) → (4) mudanza desde CallMeBot, apagándolo en el mismo paso → (5) deploy y pruebas reales. Un paso a la vez, con la suite en verde antes de pasar al siguiente.
>
> ## Reglas que no se rompen
>
> - Nunca commitear `data/`, `*.db`, `*.xlsx` ni `.env`. Ningún secreto con valor por defecto.
> - **Costo cero:** solo `"type": "text"`; el test de plantillas cubre todo archivo nuevo del canal.
> - "No contestó" ≠ "no existe": una fuente caída se nombra ("⚠️ Sin datos de … hoy"), nunca se rellena con el dato de ayer.
> - El agente **informa; no recomienda ni opera**.
> - Suite con el Python del venv: `.venv\Scripts\python.exe -m pytest -q` (0 skipped en local).
> - Al cerrar: bitácoras selladas (`python scripts/indexar.py . --sellar <carpeta>`), `EN-HUMANO.md`, `ESTADO.md` y `ROADMAP.md`, commit en `main` y avisarme para el push y el deploy.
