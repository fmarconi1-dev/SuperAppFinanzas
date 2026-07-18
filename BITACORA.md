# BITÁCORA — changelog narrativo global

Qué se hizo, cuándo y **por qué**, a nivel proyecto. Una entrada por sesión relevante. Lo fino de cada módulo va en su `bitacora_de_trabajo.md`.

---

## 2026-07-17 (tarde) — Incidente en producción y resolución mismo día
**Autor:** Claude (Fable 5), con Franco.
- **Síntoma:** tras deployar D2, la app mostró onboarding como usuario nuevo (datos "desaparecidos") y luego crash de migración (UNIQUE en configuracion_new).
- **Causa raíz:** el guard de M4 ("¿la PK contiene user_id?") daba falso tras M8 (PK por workspace) → M4 se re-ejecutó, reconstruyó las tablas **descartando `workspace_id`** y desvinculó todas las filas. El crash posterior fue por duplicados escritos en la ventana rota.
- **Resolución:** guard de M4 corregido (exige tabla no-post-D2) + **M8.5**: reparación idempotente que re-vincula filas huérfanas al workspace personal de su usuario, prefiriendo el dato original ante duplicados. Deploy verificado por Franco: datos restaurados por completo.
- **Autocrítica:** el test de idempotencia original corría sobre DB vacía y no detectaba la desvinculación. Se agregaron 2 tests de regresión que reproducen el incidente (doble migración con datos + estado roto). Suite final: **114 en verde**. Lecciones anotadas en `ESTADO.md`.
- Los datos nunca estuvieron en riesgo real: `user_id` intacto en cada fila + snapshots diarios del volumen + radar-financiero como respaldo.
**Estado al cierre:** D2 en producción, verificado. Próximo: Fase 3 (Cartera).

---

## 2026-07-17 — Grupo familiar D2: gastos compartidos completos (código)
**Autor:** Claude (Fable 5), con Franco.
- Cutover completo del modelo de datos a **workspaces**: migración M8 (PKs por workspace), `core/workspaces.py`, contextvar, y refactor de todas las queries del dominio (`user_id` queda como autor). Sin switcher, todo cae al espacio personal → cero cambio de comportamiento.
- UI completa: badge por modo (violeta/esmeralda), switcher en sidebar, "Espacio compartido" en Configuración (crear con código de un solo uso visible, unirse, salir), "Firmar como" en Transacciones.
- 11 tests nuevos; suite total **112 en verde**. Riesgos del premortem #5 mitigados.
- En la misma sesión: correcciones del tablero de scoring pedidas por Franco (categorías Resto/señal, filtros persistentes, popover de metodología, encabezado simple, NU y SATL → USA en el repo Scoring).
**Por qué:** D1 ya estaba en producción y la feature es de uso real con Agustina; se adelantó de Fase 4 con alcance cerrado.
**Estado al cierre:** código completo y commiteado; falta deploy + verificación de Franco. Próximo: Fase 3 (Cartera).

---

## 2026-07-15 — Fase 2: un solo login, dos lugares, scoring adentro
**Autor:** Claude (Fable 5), con Franco.
- **Shell unificado:** `app.py` ahora es auth gate + `st.navigation` (barra superior) entre 🏠 Finanzas (`places/finanzas/home.py`, la app original intacta) y 📈 Inversiones (`places/inversiones/home.py`, estructura triple con placeholders honestos para F3/F5).
- **Scoring embebido (ADR-0002):** el batch NO se migró — sigue corriendo en el repo público con su cron y su tablero en Pages. La superapp lee el `data.json` publicado con caché 15 min + fallback local + estado de error con retry. Vista nativa Cosmic Slate: KPIs, filtros, scores como barras, cambios de categoría, links a Yahoo (skill `ui-ux-web-moderno` aplicada).
- **Tests:** 101 en verde (4 nuevos para el lector de snapshot, sin red).
**Por qué:** Fase 2 del roadmap; consumir el snapshot en vez de mover el batch mantiene vivo el tablero público y no arriesga lo que ya funciona.
**Estado al cierre:** código completo y commiteado; falta `fly deploy` + verificación visual de Franco. Próximo: Fase 3 (Cartera) o grupo familiar D2.

---

## 2026-07-10 — Fase 1 cerrada: Mis-Finanzas vive en el monorepo, con datos de producción
**Autor:** Claude (Fable 5), con Franco.
- **Migración de código** (~7.000 LOC): lógica de negocio a `places/finanzas/core`, vistas a `places/finanzas/views`, helpers a `places/finanzas/helpers`; auth/db/theme subieron a `core/` compartido. Imports re-cableados con `core.db` como módulo plano (los tests monkeypatchean sus atributos — no convertirlo en paquete).
- **Tests:** 97/97 en verde (reconciliación, KPIs, parsers, premortems, backup). Los CSV ancla (`Diario.csv`/`Mensual.csv`) viven solo en local, ignorados por git.
- **Deploy:** Dockerfile/fly.toml/entrypoint heredados de la config probada de radar-financiero (puerto 8501, volumen `finanzas_data` 1 GB con snapshots, health check). Máquinas del hola mundo destruidas.
- **Datos:** DB de producción copiada de radar-financiero → superapp-finanzas vía backup consistente de sqlite + `fly ssh sftp get/put` (el shell sftp interactivo se come caracteres en Windows; usar `fly ssh sftp put` directo). Verificado por Franco: mismos números.
- radar-financiero queda vivo como respaldo hasta validar la superapp unos días.
**Por qué:** Fase 1 del roadmap — mover sin reescribir, con los tests como gate y sin arrancar de cero en datos.
**Estado al cierre:** Fase 1 ✅. Próximo: Fase 2 (shell unificado + scoring embebido; requiere acceso al repo Scoring-Inversiones).

---

## 2026-07-10 — Fase 0 cerrada: repo publicado, hook probado, hola mundo en Fly.io
**Autor:** Claude (Fable 5), con Franco.
- Primer commit del esqueleto (`3a72222`, 53 archivos, cero datos) pusheado a `fmarconi1-dev/SuperAppFinanzas`.
- Pre-commit hook instalado con doble capa: chequeo anti-datos en `sh` puro (protege también los commits desde GitHub Desktop en Windows, donde no hay `pre-commit`) + framework completo cuando está disponible. Probado: `prueba-hook.xlsx` bloqueado en ambas capas; `pre-commit run --all-files` en verde.
- Hola mundo Streamlit desplegado en Fly.io: `app.py` mínimo, `Dockerfile`, `fly.toml` (región `gru`, auto-stop), `.dockerignore` anti-leak. Deploy verificado por Franco.
- Incidentes resueltos (git + OneDrive): locks huérfanos que bloqueaban GitHub Desktop, archivos commiteados truncados por sync parcial (restaurados) y un índice corrupto que generó un commit destructivo (nunca pusheado; recuperado con `git reset`, sin pérdida). Protocolo de verificación anotado en `ESTADO.md`.
**Por qué:** cerrar los candados y el pipeline de deploy antes de tocar código real (mitigación directa del premortem: fuga de datos y deploy como cuello de botella).
**Estado al cierre:** Fase 0 ✅ completa. Próximo: Fase 1 (migrar Mis-Finanzas-App a `places/finanzas/`).

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
