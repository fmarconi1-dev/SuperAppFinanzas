# Prompt de inicio — Balances de la semana por WhatsApp

Copiá el bloque de abajo en una sesión nueva, con acceso a la carpeta `SuperAppFinanzas/`.

Estado al escribirlo (20/10/2026): **Fases A, B, C y D en producción** (v39, región `iad` desde la caída de Fly del 20/10). La Fase D (conciliación) espera la prueba real de Franco a fin de mes; esta tarea no depende de esa prueba. La idea es de Franco del 19/10/2026 y está entera en `MEJORAS.md`, "Balances de la semana por WhatsApp": esas decisiones no se reabren.

---

> Soy Franco. Trabajamos en mi **Secretario** (ADR-0008): Streamlit + SQLite en Fly.io (`superapp-finanzas`, región `iad`), con una API stdlib detrás de nginx que atiende mi WhatsApp (Meta Cloud API, **costo cero sí o sí**). La agenda va a Google por el Apps Script (`integraciones/google-apps-script/`). **Trabajamos siempre en la rama `main`**; el push y el deploy los hago yo.
>
> ## Antes de tocar nada, leé en este orden y confirmame que entendiste
>
> 1. `ESTADO.md` — foto actual.
> 2. **Este prompt entero.**
> 3. `MEJORAS.md`, la entrada **"Balances de la semana por WhatsApp"**: todo lo que ya decidí (universo, mi lista de tickers, formato, cuándo llega). No se reabre.
> 4. `docs/decisiones/ADR-0010-numeros-de-mercado-por-codigo.md` — por qué los números de mercado los arma `Mercado.gs` y no Gemini, y las fuentes que ya se probaron.
> 5. `docs/decisiones/ADR-0008-enfoque-secretario.md` y `docs/WHATSAPP-CANAL.md` — costo cero: solo `"type": "text"`, ventana de 24 h, cola de salida (`encolar_saliente`).
> 6. `MAPA.md` y las `BITACORA.md` de `core/api/`, `places/finanzas/core/` e `integraciones/google-apps-script/`. Ojo con la propuesta numerada de los lotes (`comandos._proponer_varios`, `_leer_respuesta_lote`, `lotes.py`) y con cómo `evento:` agenda en Google (`google.py`, `Codigo.gs`).
> 7. `claude.md` y `GUIA-DE-TRABAJO.md` — reglas duras.
>
> ## El objetivo
>
> **El domingo a la noche** el Secretario me manda las empresas que presentan balance esa semana: primero mi lista y las argentinas, después las ~15 más grandes del S&P 500 (`balances todas` muestra el resto). Cada una con el día y si es antes de la apertura o después del cierre. Le contesto como en los lotes (`1 3 7`, tickers, `todas`, `ninguna`) y **las elegidas quedan agendadas en mi Google Calendar** (📊, sin duplicar si reintenta). `deshacer` borra lo agendado.
>
> **El día que presenta una de las agendadas** me llega, en un **mensaje aparte** y sin IA, una línea por empresa:
>
> ```
> 📊 Balances
> MSFT (post-cierre): ganancia 6% por encima de lo esperado, ingresos 2% por encima. Posmercado: positiva (+4,1%).
> KO (pre-apertura): ganancia 3% por debajo de lo esperado, ingresos en línea. Rueda: negativa (−2,3%).
> ```
>
> Las de antes de la apertura salen con el **cierre** de ese día (rueda del día); las de después del cierre, con el **briefing de la mañana siguiente** (posmercado contra el cierre). "Neutra" si se movió menos de ±1%. Si la fuente no trae la estimación de los analistas, va `s/d`: **nunca se calcula una estimación propia**. Las empresas del día salen de mi Calendar (es la fuente de verdad: entra lo que elegí agendar).
>
> ## Lo primero que hay que resolver (antes del plan)
>
> **Dónde vive cada parte.** El 19/10 decidí dos cosas que tironean: en `MEJORAS.md`, que el resumen "lo arma la SuperApp"; en la ADR-0010, que los números de mercado los arma `Mercado.gs` para no cargar la app. La elección por WhatsApp (`1 3 7`) solo puede vivir en la SuperApp, que es la que recibe mis mensajes. Traeme una recomendación de qué va en cada lado (calendario, elección, agendado, resumen) con el porqué, y la decido yo.
>
> ## Lo que hay que verificar (no lo sabemos todavía)
>
> - **Fuente del calendario de balances**, gratis: Finnhub o Alpha Vantage (con clave gratis) o el JSON de Nasdaq (sin clave). Que el plan gratis siga incluyendo el calendario, que traiga antes/después de la apertura, y si marca las fechas estimadas (se agendan marcadas como estimadas). **No** Investing ni Yahoo para el calendario: no tienen API y sus términos prohíben leerlos con un programa.
> - **Lista del S&P 500**: la tabla de Wikipedia, refrescada una vez por mes.
> - **Resultados contra lo esperado**: que la fuente traiga la ganancia por acción y los ingresos reales **y** la estimación de los analistas a tiempo (a las 18:30 o a la mañana siguiente).
> - **Posmercado**: el `chart` de Yahoo con `includePrePost=true` es candidato (ya está probado en `Mercado.gs`). Verificar desde dónde se pide (los servidores de Google a veces son rechazados).
> - **SPCX** es SpaceX: confirmar que la fuente no lo confunda con el ETF de SPACs del mismo ticker. **PAM** es Pampa (no PAMP).
>
> Si alguna fuente necesita clave, va en `fly secrets` (o en las propiedades del script), **sin valor por defecto**, y está en `.env.example` sin valor.
>
> ## Orden de trabajo (un paso a la vez, desplegable, suite en verde)
>
> 1. **La recomendación de dónde vive cada parte** y **`docs/PLAN-BALANCES.md`** con las fuentes verificadas. **Mostrámelo antes de codear.**
> 2. **El calendario y la elección**: la lista del domingo por la cola de salida y la respuesta numerada, sin agendar todavía.
> 3. **El agendado en Google Calendar** con clave estable por ticker y fecha, y `deshacer`.
> 4. **El resumen del balance** en un mensaje aparte, junto al cierre o al briefing de la mañana.
>
> ## Reglas que no se rompen
>
> - **Costo cero:** solo `"type": "text"`, dentro de la ventana de 24 h, por la cola de salida. Nunca plantillas. El test de costo cero recorre `core/api/` y `places/finanzas/core/` enteros: un archivo nuevo del canal queda vigilado solo.
> - **Lo menos IA posible:** fechas y cifras salen de una fuente de datos, nunca de Gemini ni de otro LLM. Solo cifras y una palabra para la reacción: nada de análisis ni recomendaciones.
> - `except Exception: return <vacío>` está prohibido. Una fuente que no contesta se nombra con su excepción y se ve como `s/d`, nunca como un número viejo ("No contestó" ≠ "no existe").
> - Los tests no salen a internet: fuentes de mentira en un puerto local, como `tests/test_cotizaciones.py` o `tests/test_archivos_whatsapp.py`.
> - Suite con el Python del venv: `.venv\Scripts\python.exe -m pytest -q` (0 skipped en local).
> - Al cerrar cada paso: bitácoras selladas (`python scripts/indexar.py . --sellar <carpeta>`), `EN-HUMANO.md`, `ESTADO.md` y `ROADMAP.md`, commit en `main` y avisarme para el push y el deploy.
