# claude.md — reglas para agentes IA en este repo

Contexto operativo para cualquier Claude (u otro agente) que trabaje acá. Resumen duro; el detalle está en `GUIA-DE-TRABAJO.md`.

## Qué es este proyecto
Superapp web personal de Franco que unifica **Finanzas Personales** (ex Mis-Finanzas-App) e **Inversiones/Mercado** (cartera + scoring + mercado en vivo) en un monorepo Streamlit/Python. Uso personal primero; escalable después. Estado: esqueleto (Fase 0).

## Antes de trabajar (siempre)
1. Leé `ESTADO.md`. Es la foto actual y el handoff.
2. Leé `ROADMAP.md` y el `README.md` + `bitacora_de_trabajo.md` del módulo a tocar.
3. **Revisá `docs/HERRAMIENTAS-EVALUADAS.md` antes de codear** cada fase: reutilizá los repos/skills que apliquen (charts, datos, cálculo) en vez de reinventar; si aparece uno nuevo, evalualo y anotalo.
4. Confirmá la tarea con Franco antes de codear. Marcala como EN CURSO en `ESTADO.md`.

## Al terminar (siempre)
1. Actualizá la `bitacora_de_trabajo.md` del módulo.
1b. Actualizá `EN-HUMANO.md` (lenguaje llano: qué se hizo / para qué sirve / qué sigue) y dá un resumen 'en humano' en el chat. Cada avance importante; mínimo 1 vez por sesión.
2. Actualizá `ESTADO.md` con el próximo paso concreto.
3. Actualizá `BITACORA.md` y `ROADMAP.md` si el avance es relevante.
4. Tests en verde.

## Reglas duras
- 🔒 **Nunca** commitear `data/`, `*.xlsx`, `*.db`, `.env`. Repo privado.
- 📏 Una fase a la vez, cerrada y desplegable. Nada de alcance infinito.
- 🧮 Portar lógica del Excel exige test de reconciliación fila-a-fila contra el Excel.
- 🧠 El scoring se calcula en **batch (GitHub Actions)**, no en el servidor web.
- 🚫 No prometer "tiempo real" de mercado ARG sin fuente confiable resuelta.
- 🚫 Multiusuario/SaaS: recién en Fase 7, opcional.
- ✍️ Documentación y commits en español.

## Skills / agentes a usar
- **`ui-ux-web-moderno`** — obligatoria al trabajar estética/UI (tema `core/theme`, dashboards, formularios, dark mode).
- **`agente-tesis-inversion`** — ayudante para profundizar ideas de inversión sobre tickers destacados por el scoring (a futuro; ver `MEJORAS.md`).
- **`actualizar-valuaciones-solidum`** — mantiene actualizados los Excel de renta fija que lee la cartera.
- **`gauss314/skills`** — colección de datos de mercado (estándar SKILL.md). Resuelve la fuente de datos ARG: `bcra-macro`, `data912`, `byma`, `mae` (Argentina) + `option-pricing`, `backtesting` (herramientas) + `yahoo-finance`, `sec-data` (global). Ver `docs/DATOS-MERCADO-ARG.md`. Usar como implementación de referencia de `core/market_data/`.


## Stack y herramientas externas
- **Gráficos:** `tradingview/lightweight-charts` (velas/series financieras).
- **Dominio:** `DigitalPlat FreeDomain` (URL gratis para el deploy).
- **Datos:** `gauss314/skills` (ver arriba). **Cripto (opcional):** `ccxt`.
- **Futuro (capa IA, Fase 7+):** `ollama` (local/privado) + `langgraph` o `crewAI` + `mem0`. Detalle y veredictos en `docs/HERRAMIENTAS-EVALUADAS.md`.
- ⛔ No usar `hyperliquid-sdk` para operar (regla: el agente no ejecuta trades).

## Arquitectura en una línea
`core/` compartido (auth, db, config, market_data, theme) + un package por *lugar* en `places/`. La app unificada es la meta, no el arranque: primero se migra, después se integra.
