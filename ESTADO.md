# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".
> Este archivo es una **foto, no una crónica**: la narrativa de cada sesión va a la `bitacora_de_trabajo.md` del módulo y a `/BITACORA.md`; lo que ya cerró se muda a `docs/archivo/ESTADO-historial.md`. Para ubicar código sin releer el repo: **`/MAPA.md`**.
> **Verificá antes de confiar:** `git log --oneline -15` + `git status`. Si lo que ves no coincide con esto, gana lo que ves — y corregí este archivo.

<!-- ultima_actualizacion: 2026-09-27 · autor: Claude (Opus 5.5), autónomo · handoff: el backup externo llevaba un mes sin correr (la tarea no existía y dependía de la sesión de fly, que vence). Copia sacada y scripts arreglados (token de la app, sin cuelgues, aviso en el Escritorio); falta que Franco guarde el token y registre la tarea. Además: aviso de form_motivo silenciado, tests de login, trampa 27 cerrada. Suite 909 passed, 0 skipped. Commit local listo; push y deploy de Franco. -->

## 🧭 Dónde estamos

- **Fase actual: Fase 5 — Captura *source-first* del Lugar A (ADR-0006). Aprobada, SIN ARRANCAR.** 7 pasos, ~2,5 semanas; el prompt de arranque es `docs/PROMPT-INICIO-FASE-5.md`.
- **Fase 4 — cerrada** (27/8/2026) en lo que hizo: respaldo + CI. Su punto 3 (voz + hitos) lo **descartó Franco el 4/8**; sus puntos 4 y 5 (M4 importador con LLM, M5 API sidecar) **no son de la Fase 4**: quedaron absorbidos por la Fase 5 (M4 es su último paso, M5 su vía de captura del efectivo). No hay ítems vivos de la Fase 4.
- **Cartera (Lugar B.1):** Fases 3a y 3b completas y en producción, más renta fija con cronogramas de Docta (M15), vencimientos desde el cronograma y benchmark money-weighted vs SPY/Merval (27/8).
- **Mantenimiento del 22/9 y del 27/9/2026:** auditoría + limpieza (22/9) y backup + tres mejoras chicas (27/9), sin features. Detalle en `/BITACORA.md`.
- **Suite:** **909 passed, 0 skipped** en local (27/9/2026). En CI salen 3 `skipped` (los tests-oráculo necesitan el Excel y los CSV de Franco). **Regla del RUNBOOK: antes de un deploy, local tiene que dar 0 skipped.** Cobertura: 78% (`--cov`, `coverage` instalado en el venv fuera del lock).
- **Hosting:** Fly.io, app `superapp-finanzas`. **Último deploy: 23/9/2026** (lo del 22/9), verificado el 27/9 sobre la copia de producción: `user_version = 1`, sin filas huérfanas. Lo del 27/9 **no está desplegado**: solo cambia `.streamlit/config.toml`, un aviso del panel de benchmark y un docstring; el resto son scripts de tu PC y tests.
- **Backup externo:** 🔴→🟡 la última copia buena es del **27/9** (antes: 26/8, un mes sin backup). **Todavía no corre solo**: falta que Franco guarde el token de Fly y registre la tarea (ver abajo). `scripts\estado_backup.ps1` lo muestra en rojo hasta entonces.
- **Repo git:** `main`. Último commit pusheado: `52e7aab` (22/9). El commit del 27/9 queda **local**, pendiente de push.

## 🔵 Tarea en curso

| Tarea | Estado | Autor | Desde |
|---|---|---|---|
| Auditoría + limpieza entre fases (bugs B1–B7, excepts, código muerto, docs, smoke tests) | ✅ HECHA, pusheada y desplegada (23/9) | Claude (Opus 5.5) | 2026-09-22 |
| Backup que corra solo (token de la app, sin cuelgues, aviso en el Escritorio) + aviso `form_motivo` + tests de login + trampa 27 | ✅ HECHA — commit local; **falta: token + tarea (Franco), push** | Claude (Opus 5.5) | 2026-09-27 |
| **Fase 5 · Paso 0 — Cuentas y perímetro (M16)** | ⬜ siguiente — **no arrancar sin que Franco lo pida** | — | — |

## ✅ Hecho hasta ahora (resumen; detalle en ROADMAP.md y en el archivo)

- **Fase 0** cimientos · **Fase 1** Lugar A migrado · **Fase 2** shell unificado (el scoring se retiró el 5/8) — cerradas 07/2026.
- **Fase 3a/3b** cartera nativa y rendimientos finos — cerradas 07/2026, desplegadas.
- **Fase 4** respaldo remoto + restore ensayado + CI — 07–08/2026.
- **Renta fija, benchmark, lock, `core/context.py`, split de `view.py`** — 08/2026.
- **27/9/2026:** backup sacado (406 transacciones) y scripts arreglados para que corra solo sin tu sesión y avise si falla; el aviso de `form_motivo` en `fly logs` silenciado (no era error); 30 tests de login y contraseñas; el benchmark ya no usa en silencio un índice sin dividendos.
- **22/9/2026:** la pantalla de Cartera ya no se cae con una tasa devengada (y se puede quitar); precio del broker antes que el devengado; Docta/Yahoo ya no confunden "no contestó" con "no existe"; el mapa no lee carpetas ignoradas; las reparaciones de datos de las migraciones corren una vez; los importes ilegibles se avisan; el CLI del import de Finanzas anda; smoke tests que abren las pantallas.

## ⏭️ Próximo paso concreto

1. **Franco — que el backup corra solo (una vez, desde la carpeta `SuperAppFinanzas`):**
   - `powershell -ExecutionPolicy Bypass -File scripts\guardar_token_fly.ps1` (con la sesión de fly activa; si venció, antes `fly auth login`).
   - `powershell -ExecutionPolicy Bypass -File scripts\programar_backup.ps1`
   - Al día siguiente: `powershell -ExecutionPolicy Bypass -File scripts\estado_backup.ps1` tiene que dar todo en verde.
2. **Franco:** revisar y **pushear** el commit del 27/9; deploy cuando quieras (cambios menores, ver arriba). Vaciar la Papelera (los dos `.tar.gz` del 18/8).
3. **Decisión abierta para Franco:** ¿login sin distinguir mayúsculas? (el celular pone "Franco" y no entra). Detalle en `MEJORAS.md`.
4. **Después, cuando Franco lo pida:** Fase 5, Paso 0 — Cuentas y perímetro (M16). **Gate innegociable: ningún número histórico se mueve un peso.** Arrancar por `docs/PROMPT-INICIO-FASE-5.md`.

**Pendientes menores** (sin apuro; detalle en `MEJORAS.md`): tests del panel de importar y de la edición de categorías (cobertura 18% y 35%) · retirar `radar-financiero` de Fly (Franco) · preguntar al broker por la fila del TTM26 del 4/2/2026 (no tocar sin confirmación) · dominio propio (estético) · amortizaciones parciales de bonos vivos (primer evento: AE38 el **12/7/2027**) · migrar a pandas 3 (tarea deliberada, con su propio día).

## 🚩 Bloqueos / decisiones abiertas

- Ninguna decisión abierta. La fuente de datos de mercado ARG para **Mercado en vivo** se valida y elige en la **Fase 6** (candidatas en `docs/DATOS-MERCADO-ARG.md`).
- Nombre de la app Fly: `superapp-finanzas`. **Fly no permite renombrar apps**; si se quiere otro nombre, resolverlo con dominio propio (FreeDomain).

## ⚠️ Nota post-incidente: migraciones (17/7/2026, ampliada el 22/9/2026)

M4 (PK con user_id) se re-disparó tras M8 (PK con workspace_id) porque su guard solo miraba la PK: reconstruyó las tablas descartando `workspace_id` y desvinculó los datos en producción. Resuelto: guard de M4 exige tabla no-post-D2, y M8.5 reparó las filas huérfanas. **Lecciones:** (1) los guards de migraciones viejas deben seguir siendo correctos frente a esquemas **y datos** futuros; (2) los tests de idempotencia corren CON datos y verifican vínculos. **El 22/9** apareció la otra mitad de la lección: M3, M7 y M8.5 (reparaciones de filas) corrían en **cada arranque** y pisaban decisiones del usuario. Ahora son únicas (`PRAGMA user_version`, ver `_NIVEL_REPARACIONES` en `core/db.py`) y M5 tiene el guard post-D2. **Una migración nueva que haga `UPDATE`/`DELETE` de filas va detrás de esa marca.** Tests: `tests/test_workspaces_d2.py`, `tests/test_db_reparaciones_unicas.py`.

## ⚠️ Nota operativa: git + OneDrive

La carpeta del repo vive en OneDrive y dio problemas reales: locks huérfanos (`HEAD.lock`, `index.lock`), archivos commiteados truncados por sync parcial y un índice corrupto (recuperado sin pérdida). **Protocolo:** tras cada commit verificar `git status` limpio + `git fsck` + conteo de líneas de los archivos tocados en HEAD. Si git no ve un cambio: `git update-index --really-refresh`. La suite puede pasar de ~20 s a ~100 s por el sync: si algo parece colgado, probablemente sea eso.

- **Cómo correr la suite:** `.venv\Scripts\python.exe -m pytest -q` (Python 3.11 del venv). `python` a secas agarra la 3.14 del sistema y la suite ni colecta.
- **`Borrar/`** (gitignoreada) guarda a propósito solo el código del scoring retirado (`scoring-retirado-*/` + `test_scoring_snapshot.py`, referenciados desde `MAPA.md`). Barrerla al cerrar cada sesión: nada más debería acumularse ahí.

## 📌 Recordatorios permanentes

- No commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`, y desde el 22/9 también `*.db-shm`/`*.db-wal` por nombre).
- Una fase a la vez, cerrada y desplegable.
- Cerrar sesión = bitácora del módulo + `EN-HUMANO.md` + este archivo, sellar la `BITACORA.md` de cada carpeta tocada (el hook reindexa al commitear).
