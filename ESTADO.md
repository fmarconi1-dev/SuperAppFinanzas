# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".
> Este archivo es una **foto, no una crónica**: la narrativa de cada sesión va a la `bitacora_de_trabajo.md` del módulo y a `/BITACORA.md`; lo que ya cerró se muda a `docs/archivo/ESTADO-historial.md`. Para ubicar código sin releer el repo: **`/MAPA.md`**.

<!-- ultima_actualizacion: 2026-08-18 · autor: Claude (Fable 5) · handoff: mapa vivo del repo instalado (MAPA.md + bitácoras-router + hook) y ESTADO adelgazado; la historia 3a/3b/4 está en docs/archivo/ESTADO-historial.md -->

## 🧭 Dónde estamos

- **Fase actual: Fase 4 — Mejoras del Lugar A**, en curso. Orden aceptado por Franco: (1) respaldo ✅ · (2) CI ✅ · (3) voz consistente + hitos · (4) importador CSV con LLM · (5) API sidecar → WhatsApp.
- **Cartera (Lugar B.1): Fases 3a y 3b COMPLETAS y en producción.** Última sesión de código (bitácora del 5/8, commits del 13–14/8): tanda de correcciones de Franco, scoring **retirado** (ADR-0002), vencimientos M14 y **panel de renta fija** con cronogramas de Docta (M15): calendario de cobros, TIR esperada y duration.
- **Suite:** **650 passed, 3 skipped** al cierre de la última sesión (los 3 skipped son los tests-oráculo, que solo corren en la máquina de Franco; regla del RUNBOOK: antes de un deploy, local debe dar **0 skipped**).
- **Hosting:** Fly.io, app `superapp-finanzas` (volumen `finanzas_data`, backup remoto programable con `scripts/`). Ver `docs/DEPLOY.md` y `docs/RUNBOOK.md`.
- **Repo git:** hasta `8f8ba73` (panel de renta fija). La historia completa de cómo se llegó acá: `docs/archivo/ESTADO-historial.md`, `/BITACORA.md` y las bitácoras por módulo.

## 🔵 Tarea en curso

| Tarea | Estado | Autor | Desde |
|---|---|---|---|
| Mapa vivo del repo (MAPA.md + bitácoras-router + hook) + ESTADO adelgazado | ✅ HECHA (pendiente de commit/push de Franco) | Claude (Fable 5) | 2026-08-18 |
| Fase 4 — punto 3: voz consistente + hitos | ⬜ siguiente | — | — |

## ✅ Hecho hasta ahora (resumen; detalle en ROADMAP.md y en el archivo)

- **Fase 0** cimientos · **Fase 1** Lugar A migrado · **Fase 2** shell unificado (el scoring que traía se retiró el 5/8) — cerradas 07/2026.
- **Fase 3a** cartera nativa (parser 2 formatos, M9/M10, MEP histórico ADR-0004, KPIs por método del patrimonio, gate de recon contra el Excel) y **Fase 3b** rendimientos finos (ledger PPC móvil ADR-0005, cauciones/dividendos, composición por tipo de renta y sector, ajustes M13) — cerradas 07/2026, desplegadas.
- **Fase 4** arrancó por el respaldo (backup remoto + restore ensayado) y el CI (workflow `tests.yml` + job `sin-datos`) — 07–08/2026.
- **Renta fija:** vencimientos (M14) + cronogramas Docta con caché (M15) + panel con calendario de cobros, TIR y duration — 08/2026.

## ⏭️ Próximo paso concreto

1. **Franco:** commitear/pushear esta sesión (mapa + ESTADO); si el hook avisa bitácoras vencidas, sellarlas (`python scripts/indexar.py . --sellar <carpeta>`). Verificar que el **backup diario** esté programado en el Programador de tareas (RUNBOOK).
2. **Fase 4, punto 3 — voz consistente + hitos** (backlog en `MEJORAS.md`). Antes de codear: leer `/MAPA.md`, confirmar la tarea con Franco y marcarla acá.
3. Decisiones abiertas del estudio del repo (2026-08-18), a confirmar con Franco: **split de `view.py` de cartera en paneles** y **cortar el ciclo core↔core/auth** con un `core/context.py` (propuestas 3 y 4).

**Pendientes menores** (sin apuro): retirar `radar-financiero` de Fly cuando la superapp lleve unos días validada · `requirements.lock` · dominio propio (estético) · amortizaciones parciales de bonos vivos (primer evento real: AE38 el **12/7/2027**; ver MEJORAS).

## 🚩 Bloqueos / decisiones abiertas

- Fuente de datos de mercado ARG: 🟢 candidatos en `gauss314/skills` (`bcra-macro`, `data912`, `byma`, `mae`). Se valida y elige en Fase 5. Ver `docs/DATOS-MERCADO-ARG.md`.
- Nombre de la app Fly: `superapp-finanzas`. **Fly no permite renombrar apps**; si se quiere otro nombre, crear app nueva y redeployar **antes** de crear el volumen de la DB (Fase 1), o resolverlo con dominio propio (FreeDomain).

## ⚠️ Nota post-incidente: migraciones (17/7/2026)

M4 (PK con user_id) se re-disparó tras M8 (PK con workspace_id) porque su guard solo miraba la PK: reconstruyó las tablas descartando `workspace_id` y desvinculó los datos en producción. Resuelto: guard de M4 exige tabla no-post-D2, y M8.5 repara filas huérfanas (idempotente, prefiere el dato original ante duplicados). **Lecciones para futuras migraciones:** (1) los guards de migraciones viejas deben seguir siendo correctos frente a esquemas futuros; (2) los tests de idempotencia deben correr CON datos y verificar vínculos, no solo que no crashee. Tests de regresión en `tests/test_workspaces_d2.py`.

## ⚠️ Nota operativa: git + OneDrive

La carpeta del repo vive en OneDrive y dio problemas reales: locks huérfanos (`HEAD.lock`, `index.lock`), archivos commiteados truncados por sync parcial y un índice corrupto (recuperado sin pérdida). **Protocolo para el Claude que trabaje acá:** editar archivos vía shell (no solo herramientas de archivo), y tras cada commit verificar `git status` limpio + `git fsck` + conteo de líneas de los archivos tocados en HEAD. Si git no ve un cambio, `touch` + `git update-index --really-refresh`. Mitigación aplicada (2026-07-10): Franco activó "mantener siempre en este dispositivo" para la carpeta, eliminando los placeholders cloud-only. El protocolo de verificación sigue vigente igual.

> **Nota (2026-07-23):** en el sandbox de Cowork, `rm` sobre el mount OneDrive da "Operation not permitted" — **solo `mv` funciona**. Por eso, cuando git deja locks/temporales huérfanos (`*.lock`, `.git/objects/**/tmp_obj_*`) que bloquearían el push, el Claude los **mueve a la carpeta `Borrar/` de la raíz** (gitignoreada) en vez de borrarlos, y **avisa a Franco en el chat** para que borre `Borrar/` a mano antes del push. En el Windows de Franco el `rm` anda normal; el bloqueo es solo del sandbox. Tras cada commit: barrer locks/tmp a `Borrar/` → confirmar que no queda ningún `*.lock` activo → avisar.

## 📌 Recordatorios permanentes

- No commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`).
- Una fase a la vez, cerrada y desplegable.
- Cerrar sesión = actualizar bitácora + este archivo (+ reindexar el mapa: el hook lo hace solo al commitear).
