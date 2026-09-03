# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".
> Este archivo es una **foto, no una crónica**: la narrativa de cada sesión va a la `bitacora_de_trabajo.md` del módulo y a `/BITACORA.md`; lo que ya cerró se muda a `docs/archivo/ESTADO-historial.md`. Para ubicar código sin releer el repo: **`/MAPA.md`**.

<!-- ultima_actualizacion: 2026-08-27 (2ª sesión) · autor: Claude (Opus 5) · handoff: cuatro tareas chicas cerradas — vencimientos desde el cronograma de Docta, benchmark money-weighted vs SPY/Merval, requirements.lock verificado y el ciclo core↔core/auth cortado con core/context.py. Suite 664 → 740, incluido el split de view.py en paneles. Y en una 3ª sesión: ADR-0006 (captura source-first), que reescribe el rumbo del Lugar A y absorbe M4/M5 en una Fase 5 nueva. Commit pendiente de Franco. -->

## 🧭 Dónde estamos

- **Fase actual: Fase 5 — Captura *source-first* del Lugar A (ADR-0006)**, arranca. La Fase 4 queda cerrada en lo que hizo (respaldo + CI) y sus puntos 4 y 5 se absorbieron acá.
- **Fase 4 (histórico) — Mejoras del Lugar A.** Orden aceptado por Franco: (1) respaldo ✅ · (2) CI ✅ · (3) ~~voz consistente + hitos~~ **⛔ DESCARTADA por Franco el 4/8/2026** (cosmética; queda anotada en `MEJORAS.md` para que no se vuelva a proponer) · (4) **importador CSV con LLM (M4)** ← el siguiente ítem vivo · (5) API sidecar (M5) → WhatsApp.
- **Ojo:** este ESTADO arrastró hasta el 27/8 un "próximo paso" que apuntaba al punto (3), ya descartado. Corregido. La Fase 4 tiene **dos ítems vivos y nada más**: M4 y M5.
- **Cartera (Lugar B.1): Fases 3a y 3b COMPLETAS y en producción.** Última sesión de código (bitácora del 5/8, commits del 13–14/8): tanda de correcciones de Franco, scoring **retirado** (ADR-0002), vencimientos M14 y **panel de renta fija** con cronogramas de Docta (M15): calendario de cobros, TIR esperada y duration.
- **Suite:** **740 passed, 3 skipped** al cierre del 27/8 (los 3 skipped son los tests-oráculo, que solo corren en la máquina de Franco; regla del RUNBOOK: antes de un deploy, local debe dar **0 skipped**).
- **Hosting:** Fly.io, app `superapp-finanzas` (volumen `finanzas_data`, backup remoto programable con `scripts/`). Ver `docs/DEPLOY.md` y `docs/RUNBOOK.md`.
- **Repo git:** hasta `8f8ba73` (panel de renta fija). La historia completa de cómo se llegó acá: `docs/archivo/ESTADO-historial.md`, `/BITACORA.md` y las bitácoras por módulo.

## 🔵 Tarea en curso

| Tarea | Estado | Autor | Desde |
|---|---|---|---|
| Mapa vivo del repo (MAPA.md + bitácoras-router + hook) + ESTADO adelgazado | ✅ HECHA Y PUSHEADA (`2b84de3`, `83905cd`) | Claude (Fable 5) | 2026-08-18 |
| Higiene de gobernanza: reapuntar Fase 4, sincronizar ROADMAP, vaciar `Borrar/` | ✅ HECHA Y PUSHEADA (`aac89a7`, `690239f`) | Claude (Opus 5) | 2026-08-27 |
| Vencimientos desde el cronograma de Docta (AE38) | ✅ HECHA (pendiente de commit) | Claude (Opus 5) | 2026-08-27 |
| Benchmark money-weighted vs SPY/Merval | ✅ HECHA (pendiente de commit) | Claude (Opus 5) | 2026-08-27 |
| `requirements.lock` verificado en Python 3.11 | ✅ HECHA (pendiente de commit) | Claude (Opus 5) | 2026-08-27 |
| Ciclo core↔core/auth cortado (`core/context.py`, propuesta 4) | ✅ HECHA (pendiente de commit) | Claude (Opus 5) | 2026-08-27 |
| Split de `view.py` de cartera en paneles (propuesta 3) | ✅ HECHA (pendiente de commit) | Claude (Opus 5) | 2026-08-27 |
| **Fase 5 · Paso 0 — Cuentas y perímetro (M16)** | ⬜ siguiente | — | — |

## ✅ Hecho hasta ahora (resumen; detalle en ROADMAP.md y en el archivo)

- **Fase 0** cimientos · **Fase 1** Lugar A migrado · **Fase 2** shell unificado (el scoring que traía se retiró el 5/8) — cerradas 07/2026.
- **Fase 3a** cartera nativa (parser 2 formatos, M9/M10, MEP histórico ADR-0004, KPIs por método del patrimonio, gate de recon contra el Excel) y **Fase 3b** rendimientos finos (ledger PPC móvil ADR-0005, cauciones/dividendos, composición por tipo de renta y sector, ajustes M13) — cerradas 07/2026, desplegadas.
- **Fase 4** arrancó por el respaldo (backup remoto + restore ensayado) y el CI (workflow `tests.yml` + job `sin-datos`) — 07–08/2026.
- **Renta fija:** vencimientos (M14) + cronogramas Docta con caché (M15) + panel con calendario de cobros, TIR y duration — 08/2026. El 27/8 los vencimientos pasaron a leerse del cronograma cuando está cacheado (el AE38 dejó de quedar sin fecha).
- **Contra el mercado (27/8):** benchmark money-weighted vs SPY y Merval en la pantalla de Cartera — los mismos aportes, en las mismas fechas, puestos en el índice.
- **Infra (27/8):** `requirements.lock` verificado en Python 3.11 · ciclo core↔core/auth cortado con `core/context.py` · **`view.py` de cartera partido en paneles** (1.990 → 760 líneas + diez módulos en `paneles/`), verificado por AST contra la versión anterior.

## ⏭️ Próximo paso concreto

1. **Franco — verificaciones:**
   - ✅ **Backup diario programado en el Programador de tareas** — confirmado por Franco el 27/8/2026. El pendiente que venía del 4/8 queda **cerrado**.
   - ⬜ ¿Se **desplegó** la tanda del 13–14/8 (Docta M15 + panel de renta fija, hasta `8f8ba73`)? El último deploy con registro en bitácora es el del **5/8**; Franco cree que sí pero no lo recuerda. Se chequea en un segundo con `fly releases -a superapp-finanzas` (o `fly status`) y se anota acá. Si no salió, el panel de renta fija está en `main` pero no en producción.
2. **Fase 5, Paso 0 — Cuentas y perímetro (migración M16).** Arranca la arquitectura del ADR-0006. **Gate innegociable: ningún número histórico se mueve un peso** — test que compara todos los agregados antes y después de migrar. Sin backfill, la migración es puramente aditiva. Antes de codear: leer `/MAPA.md` y el ADR-0006 completo, y marcar la tarea acá.
3. **No quedan decisiones abiertas del estudio del repo (2026-08-18):** las propuestas 3 (split de `view.py`) y 4 (`core/context.py`) se ejecutaron las dos el 27/8.

**Pendientes menores** (sin apuro): retirar `radar-financiero` de Fly cuando la superapp lleve unos días validada · dominio propio (estético) · amortizaciones parciales de bonos vivos (primer evento real: AE38 el **12/7/2027**; ver MEJORAS).

**Fuera de fase, lo que queda en la fila del Lugar B** (`MEJORAS.md`): traer la tenencia de cripto de Binance (read-only) · exposición por moneda (necesita una regla acordada con Franco) · correlación fija-vs-variable (necesita serie histórica del patrimonio) · amortizaciones parciales (recién en 07/2027).

## 🚩 Bloqueos / decisiones abiertas

- Fuente de datos de mercado ARG: 🟢 candidatos en `gauss314/skills` (`bcra-macro`, `data912`, `byma`, `mae`). Se valida y elige en Fase 5. Ver `docs/DATOS-MERCADO-ARG.md`.
- Nombre de la app Fly: `superapp-finanzas`. **Fly no permite renombrar apps**; si se quiere otro nombre, crear app nueva y redeployar **antes** de crear el volumen de la DB (Fase 1), o resolverlo con dominio propio (FreeDomain).

## ⚠️ Nota post-incidente: migraciones (17/7/2026)

M4 (PK con user_id) se re-disparó tras M8 (PK con workspace_id) porque su guard solo miraba la PK: reconstruyó las tablas descartando `workspace_id` y desvinculó los datos en producción. Resuelto: guard de M4 exige tabla no-post-D2, y M8.5 repara filas huérfanas (idempotente, prefiere el dato original ante duplicados). **Lecciones para futuras migraciones:** (1) los guards de migraciones viejas deben seguir siendo correctos frente a esquemas futuros; (2) los tests de idempotencia deben correr CON datos y verificar vínculos, no solo que no crashee. Tests de regresión en `tests/test_workspaces_d2.py`.

## ⚠️ Nota operativa: git + OneDrive

La carpeta del repo vive en OneDrive y dio problemas reales: locks huérfanos (`HEAD.lock`, `index.lock`), archivos commiteados truncados por sync parcial y un índice corrupto (recuperado sin pérdida). **Protocolo para el Claude que trabaje acá:** editar archivos vía shell (no solo herramientas de archivo), y tras cada commit verificar `git status` limpio + `git fsck` + conteo de líneas de los archivos tocados en HEAD. Si git no ve un cambio, `touch` + `git update-index --really-refresh`. Mitigación aplicada (2026-07-10): Franco activó "mantener siempre en este dispositivo" para la carpeta, eliminando los placeholders cloud-only. El protocolo de verificación sigue vigente igual.

> **Nota (2026-07-23):** en el sandbox de Cowork, `rm` sobre el mount OneDrive da "Operation not permitted" — **solo `mv` funciona**. Por eso, cuando git deja locks/temporales huérfanos (`*.lock`, `.git/objects/**/tmp_obj_*`) que bloquearían el push, el Claude los **mueve a la carpeta `Borrar/` de la raíz** (gitignoreada) en vez de borrarlos, y **avisa a Franco en el chat** para que borre `Borrar/` a mano antes del push. En el Windows de Franco el `rm` anda normal; el bloqueo es solo del sandbox. Tras cada commit: barrer locks/tmp a `Borrar/` → confirmar que no queda ningún `*.lock` activo → avisar.
>
> **Actualización (2026-08-27):** `Borrar/` había acumulado **355 archivos / 5,8 MB** de `HEAD.lock`, `maintenance.lock` y `tmp_obj_*` desde el 4/8. Se vaciaron todos (el sandbox ahora puede borrar si se pide permiso explícito, ya no hace falta solo `mv`). **Quedaron a propósito** tres cosas que no son basura y las decide Franco: `scoring-retirado-*/` + `test_scoring_snapshot.py` (el código del scoring retirado, referenciado desde `MAPA.md`) y los dos `*.tar.gz` de respaldo del 18/8 (`gitdir_snapshot`, `superapp_snapshot`, 4 MB). Conviene **barrer `Borrar/` al cerrar cada sesión**, no dejarlo crecer meses.

## 📌 Recordatorios permanentes

- No commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`).
- Una fase a la vez, cerrada y desplegable.
- Cerrar sesión = actualizar bitácora + este archivo (+ reindexar el mapa: el hook lo hace solo al commitear).
