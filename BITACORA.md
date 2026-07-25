# BITÁCORA — changelog narrativo global

Qué se hizo, cuándo y **por qué**, a nivel proyecto. Una entrada por sesión relevante. Lo fino de cada módulo va en su `bitacora_de_trabajo.md`.

---

## 2026-07-23 (final) — Fase 3a paso 4: la Cartera ya vive en la app
**Autor:** Claude (Opus 4.8), con Franco. Skill `ui-ux-web-moderno` aplicada.
- **Vista de Cartera** cableada en la pestaña (reemplaza el cartel de "Fase 3"): KPI cards con tokens Cosmic Slate (tabular-nums; ganancia/pérdida con signo+flecha+color, nunca color solo), tabla es-AR, **upload del export del broker** con dedupe + congelado de TC en el mismo flujo, carga de instrumentos desde Config, caché de 5 min, estados empty/error. Scope por usuario (`CARTERA_USER_IDS`).
- **Lógica:** costo promedio ponderado + costo USD a TC histórico (`posiciones.py`), valuación y totales (`kpis.py`; el costo de lo que no tiene precio no entra a los totales). `tests/test_cartera_kpis.py` (12). Suite **200 passed, 1 skipped**.
- **Verificado end-to-end con datos reales:** $15.490.098 / US$10.101 · +19,8% · 23 posiciones valuadas; BTC vía yahoo.
- ⚠️ **Para 3b:** 6 letras/bonos en pesos vencidos quedan con cantidad residual (el vencimiento entra como AMORTIZACION y solo VENTA resta). El Excel arrastra lo mismo; no cotizan → no ensucian totales.
**Próximo:** paso 5 (recon USD modo "MEP actual") para cerrar 3a, luego merge a `main` + `fly deploy`.

---

## 2026-07-23 (cierre) — Fase 3a paso 3: `core/market_data` (MEP histórico + precios)
**Autor:** Claude (Opus 4.8), con Franco.
- **Hallazgo que corrigió una decisión cerrada:** el ADR-0003 asumía el MEP histórico "vía BCRA", pero **el BCRA no publica MEP** (sirve el mayorista A3500: 1.480,86 vs MEP 1.521,9 al 22/7). Se presentaron alternativas y Franco eligió **`argentinadatos`** → **ADR-0004**. Verificado antes de decidir: 419/419 días hábiles del historial cubiertos.
- **`core/market_data/`** (fetch inyectable, tests sin red): `mep.py` (serie, último hábil anterior, caché, fallback, override) + `precios.py` (data912 ARG, yahoo BTC, precedencia override→caché→proveedor, bonos /100) + `ingest.congelar_tc_mep` idempotente.
- **Humo real contra APIs vivas:** 585 movimientos del Excel importados con **TC congelado en las 585 filas, cero fechas sin dato**; 1.204 símbolos ARG; AE38 = 1.273,6 (broker: 1.262,6). `tests/test_market_data.py` (18). Suite **188 passed, 1 skipped**.
**Por qué:** sin TC histórico y precios automáticos, la cartera no puede valuarse ni superar al Excel (que usa un único MEP actual para todo).
**Próximo:** paso 4 — posiciones + KPIs + vista de Cartera (con upload del export).

---

## 2026-07-23 (tarde) — Excel-oráculo actualizado + reconciliado 20/20 + modelo M9
**Autor:** Claude (Opus 4.8), con Franco.
- Franco pasó el export completo de inviu + la Tenencia del broker. Se reconstruyó `Inversiones.xlsx` (con respaldo): export + saldos sintéticos + ajuste de ratio SPY (+70); Procesado con Moneda alineada; Config + Resumen corregidos; MEP/BTC al día. **Recalc con LibreOffice: 20/20 posiciones exactas vs broker.** El parser reprodujo 19/20 solo con movimientos → validación fuerte del motor.
- **M9** (aditiva, `core/db.py`): tablas `cartera_instrumentos`, `cartera_movimientos` (dedupe por `UNIQUE(user_id, hash_dedupe)`, `tc_mep` para paso 3), `cartera_precios_cache`; scope por user_id. `tests/test_cartera_db.py` (8).
- **Ingest** (`ingest.py` + `posiciones.py`): carga de instrumentos desde Config + import de movimientos con dedupe; posiciones portando `Resumen Cartera`. Gate `tests/test_cartera_recon.py` **reconcilia exacto** contra el Excel (verificado con recalc; skip elegante sin Excel/caché). `tests/test_cartera_ingest.py` (5). Suite **170 passed, 1 skipped**.
- Convención `Borrar/` para basura de git del mount OneDrive (gitignoreada).
**Próximo:** `core/market_data` (paso 3) — MEP histórico + precios ARG/CEDEARs/BTC con caché + override.

---

## 2026-07-23 — Fase 3a, paso 1: parser del broker construido y testeado
**Autor:** Claude (Opus 4.8), con Franco.
- Se **rescató y completó** el borrador `places/inversiones/cartera/parser.py` (estaba untracked y no compilaba). 3 arreglos: `SyntaxError` de la línea 196 (carácter U+0640 incrustado, probable sync OneDrive); espejo de dividendos/renta apareado por `(fecha, ticker_base)` tolerante a categoría para cubrir el **formato nuevo**; detección de saldo inicial sintético sin el paréntesis. Se agregó `__init__.py` y `tests/test_cartera_parser.py` (**43 tests**).
- **Verificado contra el Excel** (crudo real): mapeo de columnas de ambos formatos, `MAPA_OPERACION == Config!A5:B16`, patrones de espejo viejo/nuevo.
- **Hallazgo nuevo:** la col Moneda de `Movimientos Procesado` está **desalineada ~30 filas** (lee la moneda de otra operación); no afecta cantidades del recon y el parser infiere la moneda → app inmune. Fila 32 de Procesado ya borrada por Franco (sin `#REF!`).
- **Estado:** suite completa **157 en verde**. Commit local en `fase-3a/cartera-nativa`, pendiente de push (GitHub Desktop).
**Por qué:** es el cimiento de la carga recurrente; sin un parser con red de tests, todo el recon posterior queda sobre arena.
**Próximo:** paso 2 — modelo de datos (migración M9, `mov_cartera`).

---

## 2026-07-19 — Fase 3a diseñada: cartera nativa (handoff listo para construir)
**Autor:** Claude (Fable 5), con Franco.
- Se estudió `Inversiones.xlsx` a fondo y se decidió el **giro a cartera nativa** (ADR-0003): DB propia de movimientos con mecánica tipo Transacciones — import del histórico, carga recurrente del archivo del broker con dedupe, alta manual — en lugar del espejo Excel-in-the-loop. El Excel pasa a ser **oráculo de reconciliación**.
- Decisiones cerradas con Franco: TC MEP histórico por operación (BCRA) · costo promedio ponderado · precios automáticos (data912/BYMA/BCRA/yahoo vía gauss314/skills, caché + override manual) · Cartera visible solo para Franco (generalizable) · renta fija fuera de cartera (futura sección de análisis de mercado).
- **Hallazgos en el Excel:** el broker cambió el formato del export y la planilla no procesa 31 movimientos desde el 20/5/2026 (avisado); 2 celdas #REF! con reparación indicada. El parser nativo soportará ambos formatos → la app quedará más al día que el Excel.
- Spec completa del parser (12 categorías, espejos, sintéticos, cauciones) documentada en `ESTADO.md`.
**Por qué:** Franco quiere actualización cotidiana sin depender del Excel; el LEEME de la planilla documenta la lógica lo bastante bien como para portarla con red de reconciliación.
**Estado al cierre:** diseño completo, cero código de cartera aún. La próxima sesión arranca construyendo el parser (necesita acceso a la carpeta "Cartera personal").

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
