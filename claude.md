# claude.md — reglas para agentes IA en este repo

Contexto operativo para cualquier Claude (u otro agente) que trabaje acá. Resumen duro; el detalle está en `GUIA-DE-TRABAJO.md`.

## Qué es este proyecto
**Secretario** (hasta el 17/10/2026 "Superapp de Finanzas" / "Radar Financiero"): app web personal de Franco, su secretario por WhatsApp (ADR-0008) con **Inicio** (el día: finanzas, agenda, tareas) y **Finanzas Personales** (ex Mis-Finanzas-App), en un monorepo Streamlit/Python. **Inversiones (cartera + mercado en vivo) se retiró el 14/10/2026 (ADR-0007)**: el código está en el historial de git y las tablas `cartera_*` siguen en la base, quietas — no las borres sin el OK explícito de Franco. Uso personal primero; escalable después. **En producción** (Fly.io); la fase vigente está en `ESTADO.md`.

**La suite se corre con el Python del venv:** `.venv\Scripts\python.exe -m pytest -q`. `python` a secas agarra la 3.14 del sistema, que no tiene dependencias, y la suite ni siquiera colecta.

## Antes de trabajar (siempre)
1. Leé `ESTADO.md`. Es la foto actual y el handoff (corto a propósito; la historia está en `docs/archivo/`).
2. Leé `MAPA.md` para ubicar código sin releer el repo (`python .mapa/buscar.py "<término>"` para lo puntual). Después leé `ROADMAP.md` y la `BITACORA.md` + `bitacora_de_trabajo.md` de la carpeta a tocar.
3. **Revisá `docs/HERRAMIENTAS-EVALUADAS.md` antes de codear** cada fase: reutilizá los repos/skills que apliquen (charts, datos, cálculo) en vez de reinventar; si aparece uno nuevo, evalualo y anotalo.
4. Confirmá la tarea con Franco antes de codear. Marcala como EN CURSO en `ESTADO.md`.

## Al terminar (siempre)
0. Si tocaste código de una carpeta, actualizá su `BITACORA.md` y sellala (`python scripts/indexar.py . --sellar <carpeta>`); el reindexado lo hace el hook pre-commit.
1. Actualizá la `bitacora_de_trabajo.md` del módulo.
1b. Actualizá `EN-HUMANO.md` (lenguaje llano: qué se hizo / para qué sirve / qué sigue) y dá un resumen 'en humano' en el chat. Cada avance importante; mínimo 1 vez por sesión.
2. Actualizá `ESTADO.md` con el próximo paso concreto.
3. Actualizá `BITACORA.md` y `ROADMAP.md` si el avance es relevante.
4. Tests en verde.

## Reglas duras
- 🔒 **Nunca** commitear `data/`, `*.xlsx`, `*.db`, `.env`. Repo privado.
- 📏 Una fase a la vez, cerrada y desplegable. Nada de alcance infinito.
- 🧮 Portar lógica del Excel exige test de reconciliación fila-a-fila contra el Excel.
- 🧠 Nada de cómputo pesado en el servidor web (la regla nació con el scoring, que se calculaba en batch; el scoring se retiró el 5/8/2026, ADR-0002).
- 🚫 No prometer "tiempo real" de mercado ARG sin fuente confiable resuelta.
- 🚫 Multiusuario/SaaS: recién en Fase 8, opcional.
- 🕳️ `except Exception: return <vacío>` está prohibido: una fuente caída se nombra con su propia excepción (el patrón era `FuenteNoDisponible`, en el historial de git desde ADR-0007), una base sin migración es `es_tabla_faltante()` (`core/db.py`), y todo lo demás se deja ver. "No contestó" ≠ "no existe" (trampas 16 y 36).
- ✍️ Documentación y commits en español.

## Skills / agentes a usar
- **`ui-ux-web-moderno`** — obligatoria al trabajar estética/UI (tema `core/theme`, dashboards, formularios, dark mode).
- **`agente-tesis-inversion`** — ayudante para profundizar ideas de inversión (a futuro; pensado para los tickers del scoring, hoy retirado; ver `MEJORAS.md`).
- ~~`actualizar-valuaciones-solidum`~~ y ~~`gauss314/skills`~~ — ya no aplican a este repo: servían a la cartera y a `core/market_data/`, retirados el 14/10/2026 (ADR-0007).


## Stack y herramientas externas
- **Dominio:** `DigitalPlat FreeDomain` (URL gratis para el deploy).
- **Futuro (capa IA, Fase 7+):** `ollama` (local/privado) + `langgraph` o `crewAI` + `mem0`. Detalle y veredictos en `docs/HERRAMIENTAS-EVALUADAS.md`.
- ⛔ No usar `hyperliquid-sdk` para operar (regla: el agente no ejecuta trades).

## Arquitectura en una línea
`core/` compartido (auth, db, config, theme) + un package por *lugar* en `places/` (hoy solo `finanzas`). La app unificada es la meta, no el arranque: primero se migra, después se integra.
