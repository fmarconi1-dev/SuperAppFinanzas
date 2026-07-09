# BITÁCORA — changelog narrativo global

Qué se hizo, cuándo y **por qué**, a nivel proyecto. Una entrada por sesión relevante. Lo fino de cada módulo va en su `bitacora_de_trabajo.md`.

---

## 2026-07-09 — Evaluación de 9 repos externos
**Autor:** Claude (Opus 4.8), con Franco.
- Se estudiaron 9 repos y se registró el veredicto en `docs/HERRAMIENTAS-EVALUADAS.md`.
- **Adoptar:** `lightweight-charts` (gráficos de cartera/mercado) y `FreeDomain` (URL gratis del deploy).
- **Opcional:** `ccxt` (datos cripto si crece) y `loopkit` (skills de dev).
- **Futuro (capa IA, F7+):** `ollama` + `langgraph`/`crewAI` + `mem0`.
- **Fuera de alcance:** `hyperliquid-sdk` (operar perpetuos choca con la regla de no ejecutar trades).
**Por qué:** sumar valor sin caer en alcance infinito; solo 2 entran al MVP.
**Estado al cierre:** sin cambios de fase; Fase 0 sigue pendiente de cierre.

---

## 2026-07-09 — Arranque: premortem, plan y esqueleto
**Autor:** Claude (Opus 4.8), con Franco.

- Se corrió un **premortem** sobre la idea de unificar Mis-Finanzas-App + Scoring-Inversiones + los Excel de inversiones. 7 modos de fallo. Conclusión: factible como *integración progresiva de activos que ya funcionan*, no como app nueva desde cero. Riesgo #1 = alcance/refactor; más peligroso = fuga de datos al repo. → `Premortem - Superapp Finanzas.html`.
- Se redactó el **plan de trabajo maestro** con prefactibilidad, arquitectura de "dos lugares" (Finanzas / Inversiones-Mercado, esta con estructura triple), comparativa de hosting (recomendado Fly.io para el MVP) y roadmap por fases. → `PLAN DE TRABAJO - Superapp Finanzas.md`.
- Decisiones: monorepo con `core/` compartido + package por lugar · repo privado · MVP = integrar lo existente · renta fija/opciones Excel-in-the-loop primero · multiusuario a futuro.
- Se creó el **esqueleto del monorepo**: estructura de carpetas, `README` y `bitacora_de_trabajo.md` por módulo, y documentos de gobierno (README, ESTADO, GUIA-DE-TRABAJO, ROADMAP, MEJORAS, claude.md), `.gitignore`, `.pre-commit-config.yaml`, `.env.example`, `docs/` con ARQUITECTURA y ADR-0001.

**Por qué:** dejar un flujo de trabajo limpio para que varias conversaciones/Claudes continúen el proyecto (secuencialmente) sin pisarse.

**Estado al cierre:** Fase 0 en curso — falta `git init`/repo privado, probar el hook y el deploy "hola mundo". Ver `ESTADO.md`.

---

<!-- Plantilla de entrada:
## AAAA-MM-DD — Título corto
**Autor:** …
- Qué se hizo.
**Por qué:** …
**Estado al cierre:** …
-->
