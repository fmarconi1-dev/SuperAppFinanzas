# Herramientas y repos evaluados

Registro de repos externos estudiados, con veredicto honesto de encaje en la Superapp. Criterio rector (del premortem): **disciplina de alcance**. No todo lo útil entra ahora; meter de golpe un stack de agentes de IA + trading cripto es exactamente el riesgo de "alcance infinito". Semáforo:

- ✅ **Adoptar** (aporta ya, bajo costo/riesgo)
- 🟡 **Opcional / condicional** (si crece cierto uso)
- 🔵 **Futuro** (solo si se agrega una capa de IA; Fase 7+)
- ⛔ **Fuera de alcance** (no encaja o choca con las reglas)

---

## ✅ Adoptar

### `tradingview/lightweight-charts` — gráficos financieros
Librería JS/HTML5 canvas de TradingView (Apache-2.0, 16k★) para velas, líneas y series financieras. Chica, rapidísima, estándar de la industria.
- **Encaje:** dashboard de **cartera** (B.1) y **mercado en vivo** (B.3). Mejor que Plotly para velas/intradía. Se embebe en Streamlit vía componente HTML.
- **Fases:** 3 y 5. Se suma al stack de UI junto con `ui-ux-web-moderno`.
- **Nota de licencia:** Apache-2.0 exige mostrar atribución a TradingView (opción `attributionLogo` del propio gráfico lo resuelve).

### `DigitalPlatDev/FreeDomain` — dominio gratis
Registro gratuito de dominios (`.dpdns.org`, `.us.kg`, `.qzz.io`, `.xx.kg`, `.qd.je`) + DNS con Cloudflare. 178k★, 500k+ dominios.
- **Encaje:** darle una URL linda y gratis a la app (ej. `superappfinanzas.dpdns.org`) apuntando al deploy (Fly.io). Ahorra el costo de un dominio.
- **Fases:** 0/1 (al desplegar). Se anota en `docs/DEPLOY.md`.
- **Caveat:** son TLDs gratuitos de un proyecto independiente; para uso personal está perfecto. Si algún día es algo "serio/comercial", conviene un dominio propio pago.

---

## 🟡 Opcional / condicional

### `ccxt/ccxt` — datos y trading cripto multi-exchange
Librería que unifica 100+ exchanges cripto (precios, OHLCV, órdenes).
- **Encaje:** hoy la cartera tiene una sola línea de cripto (Bitcoin, cargada a mano). Si la exposición cripto crece, `ccxt` da precios de forma automática y confiable para `core/market_data/`. Para **datos**, no para operar.
- **Fase:** 5 (o antes si se automatiza el precio de BTC). Alternativa liviana: usar el endpoint de una sola fuente sin toda la librería.

### `Archive228/loopkit` — 33 skills + harness para agentes de código
Colección de skills de ingeniería de agentes (debug sistemático, review de seguridad, tests primero, commits limpios, decision-record, adversarial-verify) + un harness `.claude/` con loop Plan→Act→Verify y subagente verificador. MIT.
- **Encaje:** apoya el objetivo de "flujo limpio multi-Claude". Varias de sus skills se solapan con nuestro régimen (ADR, readme-audit, clean-commits). Sirve como caja de herramientas para el Claude que codee, **no** como parte de la app.
- **Fase:** transversal, opcional. Adoptar selectivamente las skills que sumen (p. ej. `adversarial-verify`, `write-failing-test-first`) sin importar todo el harness para no chocar con nuestra `GUIA-DE-TRABAJO.md`.

---

## 🔵 Futuro — solo si se agrega una capa de IA (Fase 7+)

> Estos cuatro forman un stack coherente de "analista IA" (orquestación + memoria + inferencia local). Son potentes pero **agregan complejidad real**. No entran al MVP. Si algún día querés un asistente que analice tu cartera/mercado en lenguaje natural, se evalúan juntos.

### `ollama/ollama` — LLMs locales
Corre modelos en tu propia máquina. **Ángulo fuerte para este proyecto: privacidad.** Permite análisis con IA sin mandar tus datos financieros a una API externa ni pagar tokens.

### `langgraph` (langchain-ai) — workflows de agentes con estado
Orquestación de flujos agénticos como grafos, con control fino y estado. Bueno para pipelines de análisis reproducibles.

### `crewAIInc/crewAI` — orquestación de múltiples agentes
Agentes "role-playing" que colaboran. Más alto nivel que LangGraph; útil si querés varios roles (analista fundamental, técnico, de riesgo). Se solapa con LangGraph → **elegir uno**, no ambos.

### `mem0ai/mem0` — capa de memoria para agentes
Memoria persistente para un asistente IA (recordar tu perfil de riesgo, decisiones pasadas, contexto entre sesiones). Solo tiene sentido si existe el asistente.

**Recomendación futura:** si se hace, empezar por `ollama` (privacidad) + **uno** de `langgraph`/`crewAI`, y sumar `mem0` recién si el asistente necesita memoria. Encaja con la idea ya anotada de usar `agente-tesis-inversion`.

---

## ⛔ Fuera de alcance (por ahora)

### `hyperliquid-dex/hyperliquid-python-sdk` — trading en Hyperliquid
SDK para operar en Hyperliquid (DEX de perpetuos cripto): órdenes, posiciones, cuenta.
- **Por qué no:** el proyecto es de **seguimiento y análisis** de finanzas y cartera, no de trading activo de perpetuos. Además, **ejecutar trades/mover dinero está explícitamente prohibido** en las reglas del proyecto (el agente no opera por vos).
- **Única excepción:** si vos personalmente operás en Hyperliquid y querés **leer** tus posiciones para mostrarlas en el dashboard, se usaría solo el lado de lectura (`info`), nunca el de órdenes. Aun así, es nicho; queda anotado por si acaso.

---

## Resumen

| Repo | Veredicto | Dónde |
|---|---|---|
| lightweight-charts | ✅ Adoptar | Cartera (F3) + Mercado vivo (F5) |
| FreeDomain | ✅ Adoptar | Deploy (F0/1) |
| ccxt | 🟡 Opcional | market_data cripto (F5) |
| loopkit | 🟡 Opcional | Herramientas del dev (transversal) |
| ollama | 🔵 Futuro | Capa IA privada (F7+) |
| langgraph | 🔵 Futuro | Orquestación IA (F7+) |
| crewAI | 🔵 Futuro | Orquestación IA (F7+) |
| mem0 | 🔵 Futuro | Memoria del asistente IA (F7+) |
| hyperliquid-sdk | ⛔ Fuera | Solo lectura de posiciones, si operás ahí |
