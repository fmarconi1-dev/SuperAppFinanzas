# MEJORAS — backlog e ideas a futuro

Todo lo que **no** entra en la fase actual vive acá. Es el "estacionamiento" de ideas: se anota, se prioriza, y se saca cuando le toca. Sirve para no meter alcance de más en la fase en curso (ver premortem: riesgo de alcance infinito).

Prioridad: 🔴 alta · 🟡 media · 🟢 baja / oportunista
Estado: 💡 idea · 📋 planeada · 🔵 en curso · ✅ hecha

---

## Skills y agentes a integrar en el flujo

Estas capacidades ya existen como skills/agentes y deben usarse en las fases indicadas.

### `ui-ux-web-moderno` — 🔴 obligatoria en toda tarea de UI
Inteligencia de diseño UX/UI web moderno (tokens de color, tipografía, spacing, dashboards financieros, micro-interacciones, dark mode, accesibilidad, y aplicación en Streamlit vía CSS injection).
- **Cuándo:** siempre que se trabaje el tema (`core/theme`), dashboards, formularios, o se toque "cómo se ve/siente" la app.
- **Fases:** transversal, con foco en Fase 1 (unificar estética "Cosmic Slate"), Fase 3 (dashboard de cartera) y Fase 6 (mercado en vivo).

### `agente-tesis-inversion` — ⛔ sin lugar en la app (scoring e Inversiones retirados)
Genera tesis de inversión institucional sobre un ticker (múltiplos + DCF, deuda, comparables, 5 escenarios, técnicos).
- **Idea:** conectar la salida del **scoring** con este agente. Cuando el scoring marque un ticker como "atractivo" o "consagrado", ofrecer un botón/flujo que dispare una tesis profunda sobre ese papel como ayuda a la decisión.
- **Fases:** después de Fase 2 (scoring embebido). No es parte del MVP.
- **Nota:** es apoyo al análisis, no recomendación automática de inversión.

### `actualizar-valuaciones-solidum` — ⛔ ya no aplica (Cartera retirada, ADR-0007)
Actualiza las valuaciones de los Excel de renta fija (soberanos, CER, LECAPs, duales, provinciales, ONs) a una fecha dada (tasas BCRA, cierres IAMC, MEP, flujos de fondos).
- **Cuándo:** para mantener frescos los Excel que la cartera lee en modo Excel-in-the-loop (Fase 3).

---

### `gauss314/skills` — ⛔ ya no aplica (`core/market_data/` retirado, ADR-0007)
Colección pública de skills (estándar SKILL.md, MIT) para consumir datos de mercado. **Su sección Argentina resuelve el riesgo #4 del premortem** (fuente de datos local). Instalación: `npx skills add gauss314/skills --skill <nombre>`.
- **Argentina (gratis):** `bcra-macro` (MEP/CCL/CER/UVA/tasas, oficial), `data912` (mercado en vivo ~20s: acciones/CEDEARs/bonos/opciones/MEP/CCL), `byma` (panel + bonos + cronograma de amortización), `mae` (renta fija + flujos de fondos para TIR), `cafci` (FCI), `indec` (inflación/macro, oficial).
- **Globales:** `yahoo-finance` (ya en uso), `sec-data`, `morningstar` (CEDEARs), `tradingview`, `google-finance`, `fred-macro`.
- **Herramientas:** `option-pricing` (BS/binomial/MC/griegas/IV → reemplaza `opciones argy.xlsx`), `backtesting` (ratios de riesgo, Altman Z, Piotroski, DuPont, Markowitz → enriquece el scoring).
- **Cuándo:** `bcra-macro`/`byma`/`mae` en Fase 3 (cartera); `data912` en Fase 6 (mercado en vivo); `option-pricing` al portar opciones (Fase 7); `sec-data`/`morningstar`/`backtesting` como apoyo del scoring y del agente de tesis.
- **Cómo:** diseñar `core/market_data/` con capa de abstracción por proveedor + caché + **fallback a carga manual**. Priorizar las fuentes oficiales (`bcra-macro`, `indec`); tratar las comunitarias (`data912`/`byma`/`mae`) con caché y monitoreo. Detalle y caveats en `docs/DATOS-MERCADO-ARG.md`.

## Mejoras de producto — Lugar A (Finanzas Personales)

> **Backlog heredado de `Mis-Finanzas-App` y revisado el 4/8/2026.** Ya no hace falta ir al repo viejo: lo vigente está acá abajo. Dos ítems grandes de aquel backlog **ya estaban hechos** al revisarlo.

⚠️ **Una decisión cerrada de aquel repo está REVERTIDA:** *"NO reemplazar el Excel de Inviu para inversiones"* (premortem #2). El **ADR-0003** decidió lo contrario y las Fases 3a/3b construyeron la cartera nativa completa. Si alguien lee el `MEJORAS.md` viejo, que no la tome como vigente.

### Hecho
- 🔴 ✅ **Grupo familiar — D2 Cutover** (2026-07-17): queries por `workspace_id`, UI crear/unirse/salir, badge de modo, "firmar como". Era el ítem más grande del backlog viejo (estimado en 4-5 días).
- 🔴 ✅ **Módulo de inversiones** (Fases 3a/3b): superó ampliamente el alcance que planteaba la Sección 9 de aquel backlog.
- 🟡 ✅ **Respaldo externo + restore + RUNBOOK** (4/8/2026): ver `docs/RUNBOOK.md`.
- 🟡 ✅ **Workflow de CI** (4/8/2026).

### Pendiente
- 🟡 ↪️ **M4 · Importador inteligente de CSV con LLM — ABSORBIDO POR LA FASE 5** (27/8/2026, ADR-0006). No se descarta: se **reordena**. Era el primer paso y pasa a ser el último, porque construir el extractor genérico antes de tener la arquitectura de cuentas y fuentes era resolver el problema fácil primero. Ver ROADMAP Fase 5, Paso 6.
   Subir el CSV de cualquier banco y que una llamada offline infiera el mapeo de columnas y sugiera categorías, con **preview obligatorio** antes de tocar la base. **Esfuerzo:** 3-5 días. **Riesgo:** medio — el modo de fallo es silencioso (categoriza mal y no te enterás), por eso el preview no es opcional.
- 🟡 ↪️ **M5 · API sidecar — ABSORBIDO POR LA FASE 5** (27/8/2026, ADR-0006): deja de ser un fin en sí mismo y pasa a ser la **vía de captura del efectivo** (Paso 4), que es el 10-15% del gasto que ninguna fuente automática ve.
- 🟡 💡 **(detalle original de M5)** FastAPI en la misma máquina de Fly, misma SQLite, token bearer rotable + rate-limit por IP + validación Pydantic + log de auditoría. Endpoints `GET /summary` y `POST /transaction`. **Esfuerzo:** 1 semana. **Riesgo:** medio, hay que cuidar la superficie de ataque del endpoint público.
- 🟢 💡 **Chatbot de WhatsApp.** Tier gratis de WhatsApp Business Cloud API. **Pre-requisito: M5.**
- 🟡 💡 **Dictar varios gastos en un solo mensaje** (idea tomada de Kesef, 29/9/2026). "Gasté 4.200 en el súper, 1.800 de café y 12.000 de nafta" → la app **propone** tres gastos y Franco confirma. Entra en el **Paso 4 de la Fase 5** (efectivo por WhatsApp), por texto o audio. Respeta la regla de la fase: el LLM extrae y propone, **nunca escribe ni decide montos**; la confirmación y el guardado son determinísticos.
- 🟡 💡 **Gastos recurrentes automáticos** (idea tomada de Kesef, 29/9/2026): expensas, servicios, suscripciones que se repiten cada mes se cargan solos (o se proponen para confirmar). **Ojo con la Fase 5:** cuando la caja de ahorro y las tarjetas entren por archivo, un recurrente cargado a mano **duplicaría** el mismo pago; o se hace antes de la Fase 5 y se integra al dedupe (Paso 5), o se hace como "esperado" que el import confirma en vez de como gasto.
- 🟡 💡 **Espacio compartido en el Secretario** (idea de Franco, 18/10/2026; **para pensar después de la Fase D**). Que más de una persona cargue gastos a un mismo espacio, como el grupo familiar D2 que ya existe en la app (`workspace_id`, código de invitación, "Firmar como").
   **Lo que ya decidió Franco:**
   - Se carga **desde la app y por WhatsApp**, como hoy.
   - El espacio compartido **convive** con el personal: no lo reemplaza.
   - Se quiere ver **el total gastado** entre todos, **no** quién le debe a quién (nada de Splitwise).

   **Lo que falta pensar:**
   - **WhatsApp atiende un solo número** (`WHATSAPP_NUMERO_AUTORIZADO`) y todo va al espacio personal. Hay que sumar números autorizados (verificar cuántos acepta gratis el número de prueba de Meta) y decidir a qué espacio va cada mensaje, por ejemplo con un prefijo o con un espacio por defecto para cada número.
   - **Conciliación:** la Fase D concilia la caja, el FIMA y el efectivo de Franco. En un espacio compartido los gastos salen de cuentas de distintas personas: hay que decidir qué extracto concilia cada uno y si se controla algún saldo del espacio.
   - **Doble conteo entre espacios:** un gasto que Franco paga y carga en el compartido aparece igual en su extracto personal. El emparejamiento de la Fase D tiene que reconocerlo como ya cargado (en el otro espacio) y no duplicarlo.
- 🟢 💡 Portar lo que quede del backlog de UX del repo original (`docs/MEJORAS-UX.md` allá).

### Descartado
- ⛔ **Voz consistente + hitos de celebración** (1ª transacción, 10ª, 50ª, 100ª, 365ª). Estaba estimado en 1 día con riesgo cero, pero **Franco lo evaluó el 4/8/2026 y decidió que no vale la pena**: es cosmético y no resuelve nada que le moleste usando la app. Anotado para que no se vuelva a proponer.
- ⛔ **Migrar el stack a React + Firestore + Gemini** (premortem #4, 26/6/2026). Costos de $0 a $25-60/mes, vendor lock-in, superficie 5x más grande, riesgo de pérdida de datos en la migración. **Trigger para reconsiderar:** 20+ usuarios activos pagando, o una feature concreta bloqueada por Streamlit.
- ⛔ **Publicidad como monetización.** Freemium o suscripción si algún día toca; diferido hasta 5-10 usuarios activos.
- ⛔ **Toggle claro/oscuro** — bajo impacto y choca con el dark de Cosmic Slate.

---

## Mejoras de producto — Lugar B (Inversiones / Mercado) — ⛔ RETIRADO el 14/10/2026 (ADR-0007)

> **Franco sacó la sección de Inversiones entera: no la usaba.** Todo lo de esta sección (Binance, amortizaciones del AE38, la fila del TTM26, mercado en vivo, alertas de cartera) queda como registro. **No volver a proponerlo** salvo que Franco decida traer Inversiones de vuelta.

### Cartera (B.1)
- 🟡 💡 **Traer la tenencia de cripto directo de Binance** (pedido de Franco, 23/7/2026). Hoy la cantidad de BTC se carga a mano en "Activos fuera del broker" y el precio se busca solo (yahoo). Con la API de Binance (read-only, sin permisos de trading — regla del repo: el agente no opera) la cantidad se actualizaría sola. Alternativa evaluada: `ccxt` (ya en `docs/HERRAMIENTAS-EVALUADAS.md`, 🟡 opcional) que unifica exchanges. Ojo: requiere API key del usuario → guardar en `.env`, nunca en el repo.
- 🟡 💡 **Amortizaciones parciales** de bonos vivos. **Actualizado 2026-07-30:** la convención argentina es **por precio, nunca por nominales** (dato de Franco) — el broker deja la cantidad quieta y el precio absorbe la devolución de capital. El modelo binario actual (`cant_amortizada` = 0 o todo) alcanza hasta que un bono amortice en cuotas. **Primera amortización real: 12/07/2027** (AE38, 22 cuotas del 4,545% = 100/22; verificado contra el cronograma de Docta el 5/8/2026 — se creía 9/7, pero **el 9 de julio es feriado** y el pago cae al hábil siguiente); AN29 es bullet a 2029. Cuando toque, falta resolver si el precio del broker viene por 100 de nominal **original** o **residual** — se decide con la foto de la tenencia del día que amortice, no antes. Queda fuera de la 3b por eso.
- 🟢 💡 **Exposición por moneda** (dólar vs pesos) como tercer corte de la composición. Sale de `categoria_activo` + `moneda_cotiz`, pero tiene juicio de por medio: un CEDEAR cotiza en pesos y es exposición en dólares. Requiere una regla explícita acordada con Franco.
- 🟡 ✅ **Workflow de CI** (hecho 4/8/2026): `tests.yml` corre la suite en Python 3.11 en cada push y PR, más un gate anti-datos del lado del servidor.
- 🔴 💡 **Análisis enriquecido** (en curso desde el 5/8/2026):
  - ✅ Exposición por **sector e industria** (Fase 3b).
  - ✅ **Vencimientos** de renta fija (M14 + cronograma). Al principio las fechas se leían solo de la descripción del instrumento y de la renta fija **viva** eso resolvía 1 de 3. **Resuelto el 27/8/2026**: cuando hay cronograma de Docta cacheado, el vencimiento sale de ahí (la última fecha de pago), así que el AE38 dejó de quedar en `s/d`. El pagaré sigue a mano: no tiene cronograma en ninguna fuente.
  - ✅ **TIR esperada y duration** — **HECHO (13-14/8/2026, `f1f892b`+`8f8ba73`).** Fuente `Docta Capital` (ver `docs/CRONOGRAMAS-RENTA-FIJA.md`); la cuenta ya está creada y las credenciales viven en `.env` (`DOCTA_CLIENT_ID`/`SECRET`). Cronogramas cacheados (M15): el plan gratuito de 15 req/día alcanza de sobra porque un cronograma es dato estático.
  - ✅ **Calendario de cobros** — **HECHO (13-14/8/2026)**, en el panel de renta fija. Sale del mismo cronograma. Para un bono amortizable importa más que el vencimiento: el AE38 no vence hasta 2038 pero empieza a devolver capital el **12/7/2027**.
  - 🟡 Correlación fija-vs-variable — necesita serie histórica del patrimonio.
- 🔴 ✅ **Comparación contra benchmarks (SPY, Merval)** — **HECHO el 27/8/2026.** Money-weighted como estaba planteado: los mismos aportes, en las mismas fechas, puestos en el índice. `core/market_data/indices.py` trae la serie (con `adjclose`, para no comparar contra un SPY sin dividendos) y `places/inversiones/cartera/benchmark.py` hace la simulación; el panel está en la pantalla de Cartera. Los aportes anteriores al inicio de la serie no se estiman: se informan.
- ✅ Alertas de vencimientos de bonos/ON — hecho el 5/8/2026 (M14). Ver arriba el caveat sobre su alcance real.
- 🟢 💡 Simulador "qué pasa si" (agregar/quitar posiciones y ver impacto en estructura).

### Scoring (B.2) — ⛔ retirado el 5/8/2026 (ADR-0002)
> Queda anotado por si algún día vuelve; hoy no es backlog vivo.

- 🟡 💡 Escalar el universo de tickers (hoy ~20).
- 🟡 💡 Métricas de solvencia propias para bancos/financieras (Tier 1) — hoy se excluye el D/E.
- 🟢 💡 Histórico de scores por ticker (evolución en el tiempo).

### Mercado en vivo (B.3)
- 🔴 💡 **Resolver la fuente de datos de mercado ARG** (bloqueante de esta sección). Investigación en `docs/DATOS-MERCADO-ARG.md`.
- 🟡 💡 Watchlist configurable con cotizaciones y variaciones intradía.

---

## Plataforma / infra

- 🟡 💡 **Pendientes de la auditoría del 22/9/2026** (no se hicieron por alcance; ver `/BITACORA.md`):
  - ✅ Tests de login y contraseñas — hecho el 27/9 (`tests/test_auth.py`).
  - ✅ Benchmark sin dividendos silencioso (trampa 27) — hecho el 27/9.
  - Tests de la **edición de categorías** (35%). (El panel de importar era de la cartera: retirado, ADR-0007.)
  - ⛔ **Login sin distinguir mayúsculas — DESCARTADO por Franco el 27/9/2026** ("no me parece relevante"). El login distingue mayúsculas ("Franco" ≠ "franco"); queda así a propósito. No volver a proponerlo.
  - `ajustes.listar` descarta en silencio un ajuste con fecha corrupta (hoy imposible desde la app, que guarda ISO).
  - ✅ Ramas viejas borradas en `origin` (Franco, 23/9).
- 🟢 ✅ **`requirements.lock`** (27/8/2026): builds reproducibles, verificado corriendo la suite en Python 3.11 con los pines exactos. Ojo al regenerarlo con el tope de pandas — ver la cabecera del archivo.
- 🟢 ✅ **Ciclo core↔core/auth cortado** con `core/context.py` (27/8/2026, propuesta 4 del estudio del repo).
- 🟢 ✅ **Split de `view.py` de cartera en paneles** (27/8/2026, propuesta 3): de 1.990 líneas a un orquestador de 760 + diez paneles en `paneles/`. Verificado por AST contra la versión anterior: 23 funciones idénticas, 0 perdidas.
- 🟡 💡 Migrar de Fly.io a DonWeb VPS si se prioriza pago en ARS e infra local (evaluar costo operativo — ver premortem).
- 🟢 💡 Multiusuario / SaaS (**Fase 8**): tenancy, planes, aislamiento de datos, billing.
  - **Publicar en App Store / Play Store:** requisitos, costos y trampas anotados en `docs/PUBLICAR-EN-TIENDAS.md` (29/9/2026). Exige app nativa (p. ej. Expo) sobre una API, que es el M5.
  - **Importar pagos de Mercado Pago automáticamente** (idea tomada de Kesef, 29/9/2026: los pagos entran solos en 10–30 min; AR, BR, CL, CO, MX, PE, UY). **Franco no usa billeteras** —por eso quedó fuera de la Fase 5 (ADR-0006)—, pero para otros usuarios sería una fuente más del mismo modelo *source-first*: propone movimientos, el usuario confirma, el dedupe cruza contra la tarjeta/caja de ahorro que la fondeó.
- 🟢 💡 App móvil / PWA.
- 🟢 💡 Notificaciones (email/push) para alertas de cartera y vencimientos.

---

## Cómo usar este documento
1. Idea nueva fuera del alcance actual → se anota acá con prioridad y estado.
2. Al planificar una fase → se revisa este backlog y se suben los ítems que correspondan al ROADMAP.
3. Al completar un ítem → se marca ✅ (o se mueve a `BITACORA.md`).
