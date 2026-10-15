# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".
> Este archivo es una **foto, no una crónica**: la narrativa de cada sesión va a la `bitacora_de_trabajo.md` del módulo y a `/BITACORA.md`; lo que ya cerró se muda a `docs/archivo/ESTADO-historial.md`. Para ubicar código sin releer el repo: **`/MAPA.md`**.
> **Verificá antes de confiar:** `git log --oneline -15` + `git status`. Si lo que ves no coincide con esto, gana lo que ves — y corregí este archivo.

<!-- ultima_actualizacion: 2026-10-15 · autor: Claude (Opus 5.5) · handoff: Fase A (gastos por WhatsApp, ADR-0008) CERRADA en producción: carga, resumen y deshacer probados desde el celular de Franco. Costo cero. Siguiente: Fase B (briefing + Calendar/Tasks). -->
<!-- anterior: 2026-10-14 · autor: Claude (Opus 5.5) · handoff: Franco pidió retirar Inversiones entera (ADR-0007). Código, tests y página fuera; tablas cartera_* intactas en la base. Suite 359 passed, 0 skipped. -->
<!-- anterior: 2026-09-27 · autor: Claude (Opus 5.5), autónomo · handoff: el backup externo llevaba un mes sin correr (la tarea no existía y dependía de la sesión de fly, que vence). Copia sacada y scripts arreglados (token de la app, sin cuelgues, aviso en el Escritorio); falta que Franco guarde el token y registre la tarea. Además: aviso de form_motivo silenciado, tests de login, trampa 27 cerrada. Suite 909 passed, 0 skipped. Franco guardó el token, registró la tarea, pusheó y desplegó (v27) el mismo 27/9; verificado. -->

## 🧭 Dónde estamos

- **Fase actual: Fase 5 — Captura *source-first* del Lugar A (ADR-0006). Aprobada, SIN ARRANCAR.** 7 pasos, ~2,5 semanas; el prompt de arranque es `docs/PROMPT-INICIO-FASE-5.md`.
- **Fase 4 — cerrada** (27/8/2026) en lo que hizo: respaldo + CI. Su punto 3 (voz + hitos) lo **descartó Franco el 4/8**; sus puntos 4 y 5 (M4 importador con LLM, M5 API sidecar) **no son de la Fase 4**: quedaron absorbidos por la Fase 5 (M4 es su último paso, M5 su vía de captura del efectivo). No hay ítems vivos de la Fase 4.
- **Inversiones (Lugar B): RETIRADA el 14/10/2026 (ADR-0007)** a pedido de Franco: no la usaba. Salieron `places/inversiones/`, `core/market_data/`, `scripts/verificar_docta.py`, la página de la navegación y sus tests. **Las tablas `cartera_*` siguen en la base de producción, quietas** (borrarlas es una decisión aparte de Franco). Fases 6 y 7 del ROADMAP descartadas.
- **Mantenimiento del 22/9 y del 27/9/2026:** auditoría + limpieza (22/9) y backup + tres mejoras chicas (27/9), sin features. Detalle en `/BITACORA.md`.
- **Suite:** **359 passed, 0 skipped** en local (14/10/2026; eran 909 antes de retirar Inversiones). En CI salen `skipped` los tests-oráculo (necesitan los CSV de Franco). **Regla del RUNBOOK: antes de un deploy, local tiene que dar 0 skipped.** Cobertura: 78% (`--cov`, `coverage` instalado en el venv fuera del lock).
- **Hosting:** Fly.io, app `superapp-finanzas`. **Último deploy: 27/9/2026, release v27** (commit `2b544ab`): health `ok`, sin tracebacks ni el aviso de `form_motivo` en los logs (verificado).
- **Backup externo:** 🟢 token de la app guardado (**vence el 27/9/2027**; `estado_backup.ps1` avisa 30 días antes) y tarea "Backup Superapp Finanzas" registrada, diaria 09:00. Última copia: 27/9 con `auth=token`. **Pendiente:** confirmar el 28/9 que la tarea corrió sola (`scripts\estado_backup.ps1` en verde).
- **Repo git (15/10/2026):** se trabaja **siempre en `main`** (pedido de Franco). El retiro de Inversiones y la Fase A se mergearon a `main` (fast-forward, `bb53c39`); falta el push de `main` y el deploy. La rama `retiro-inversiones` quedó igual a `main` y ya no se usa.

## 🔵 Tarea en curso

| Tarea | Estado | Autor | Desde |
|---|---|---|---|
| Auditoría + limpieza entre fases (bugs B1–B7, excepts, código muerto, docs, smoke tests) | ✅ HECHA, pusheada y desplegada (23/9) | Claude (Opus 5.5) | 2026-09-22 |
| Backup que corra solo (token de la app, sin cuelgues, aviso en el Escritorio) + aviso `form_motivo` + tests de login + trampa 27 | ✅ HECHA, pusheada y desplegada (v27); token y tarea hechos por Franco | Claude (Opus 5.5) | 2026-09-27 |
| Retirar el lugar Inversiones entero (ADR-0007) | ✅ HECHA, en `main` (`e1adc13`, `7a0c139`); **sin desplegar** | Claude (Opus 5.5) | 2026-10-14 |
| **Enfoque "secretario" (ADR-0008)**: canal decidido (Meta Cloud API, costo cero: `docs/WHATSAPP-CANAL.md`), Apps Script reescrito (`integraciones/google-apps-script/`, **sin instalar ni probar**), plan de la Fase A (`docs/PLAN-FASE-A.md`) | ✅ preparación hecha, **sin commitear** | Claude (Opus 5.5) | 2026-10-14 |
| **Fase A — gastos por WhatsApp** (`docs/PLAN-FASE-A.md`) | ✅ **CERRADA en producción (15/10/2026)**: `resumen`, carga y `deshacer` probados desde el celular de Franco; costo cero | Claude (Opus 5.5) | 2026-10-15 |
| **Fase B — briefing + agenda + cierre de mercado 18:30** (ADR-0008). Plan: `docs/PLAN-FASE-B.md`; las 4 decisiones **confirmadas por Franco el 15/10** | ⬜ **arranca el 16/10/2026** | — | — |
| **Fase 5 · Paso 0 — Cuentas y perímetro (M16)** | ⏸️ en pausa por ADR-0008 | — | — |

## ✅ Hecho hasta ahora (resumen; detalle en ROADMAP.md y en el archivo)

- **Fase 0** cimientos · **Fase 1** Lugar A migrado · **Fase 2** shell unificado (el scoring se retiró el 5/8) — cerradas 07/2026.
- **Fase 3a/3b** cartera nativa y rendimientos finos — cerradas 07/2026, desplegadas.
- **Fase 4** respaldo remoto + restore ensayado + CI — 07–08/2026.
- **Renta fija, benchmark, lock, `core/context.py`, split de `view.py`** — 08/2026.
- **27/9/2026:** backup sacado (406 transacciones) y scripts arreglados para que corra solo sin tu sesión y avise si falla; el aviso de `form_motivo` en `fly logs` silenciado (no era error); 30 tests de login y contraseñas; el benchmark ya no usa en silencio un índice sin dividendos.
- **22/9/2026:** la pantalla de Cartera ya no se cae con una tasa devengada (y se puede quitar); precio del broker antes que el devengado; Docta/Yahoo ya no confunden "no contestó" con "no existe"; el mapa no lee carpetas ignoradas; las reparaciones de datos de las migraciones corren una vez; los importes ilegibles se avisan; el CLI del import de Finanzas anda; smoke tests que abren las pantallas.

## ⏭️ Próximo paso concreto

-2. ✅ **Backup externo: vuelve a andar (15/10/2026, 13:55, 456 transacciones, `auth=token`).** Estuvo caído del 13/10 al 15/10 porque `fly.exe` quedó en 0 bytes tras una actualización a medias; Franco reinstaló flyctl. El token estaba bien: el aviso del Escritorio culpaba al token por error (`_fly_comun.ps1` no distingue "flyctl no ejecuta"; arreglo propuesto como tarea aparte).

-1. ✅ **Fase A (ADR-0008) — CERRADA el 15/10/2026.** El Secretario carga gastos, responde `resumen` y `deshace`, desde WhatsApp y sin costo. Cómo quedó armado (y las trampas: el 9 de los números argentinos, la suscripción de la app a la cuenta de WhatsApp Business): `core/api/BITACORA.md` y `docs/WHATSAPP-CANAL.md`.
   1. ✅ **Costo cero confirmado (15/10):** el texto libre llegó al teléfono sin tarjeta. El primer intento no llegaba porque el número estaba en el panel sin el 9; cargado con el 9, llegó.
   2. ✅ **Desplegado el 15/10/2026** desde `main`, con backup previo. Verificado desde afuera: `/_stcore/health` ok, `/api/health` ok, `/api/privacidad` publicada, `/api/whatsapp` → 503 `sin_configurar` (esperado hasta cargar los secretos). Inversiones ya no está en producción.
   3. ✅ **15/10:** token permanente, secretos en Fly, webhook verificado, `messages` suscripto y **app suscripta a la cuenta de WhatsApp Business** (faltaba: solo estaba la app de prueba de Meta). El primer mensaje real **llegó** a la app (20:50, `from` = `549…`); la respuesta rebotó con 131030 porque se mandaba con el 9 → **corregido en código, falta desplegar**.
   4. ✅ **Prueba real (15/10, 20:58–20:59):** `resumen` (los números de octubre de la base de producción), carga y `deshacer`, todos respondidos.
   **Siguiente: Fase B (arranca el 16/10/2026)** → `docs/PLAN-FASE-B.md`: briefing matutino con finanzas del mes, **cierre de mercado a las 18:30** (EE.UU.: acciones y Treasuries; Argentina: Merval, hard dollar, riesgo país y curva en pesos) y `evento:` / `tarea:` / `agenda` vía Apps Script. **Decisiones confirmadas (15/10):** párrafos por reglas, TEM con tabla chica en el repo, CER solo variación de precio, 18:30 lunes a viernes. Empezar por el paso 1 del plan (M18 + cola de salida). Después C (dashboard + rebranding) y D (conciliación).
0. **Franco:** el retiro de Inversiones ya está commiteado en `retiro-inversiones`; falta mergearlo y desplegarlo (sale junto con la Fase A, ver -1) (al desplegar, `/inversiones` deja de existir en producción). Decidir aparte si las tablas `cartera_*` se borran de la base (irreversible; hoy quedan quietas).
1. **Franco, el 28/9 o después:** `powershell -ExecutionPolicy Bypass -File scripts\estado_backup.ps1` → tiene que dar todo en verde (la tarea todavía no corrió nunca al 27/9). Si aparece "BACKUP SUPERAPP - FALLO.txt" en el Escritorio, dice qué pasó.
2. **Franco:** vaciar la Papelera cuando quieras (los dos `.tar.gz` del 18/8).
3. ~~Login sin distinguir mayúsculas~~ — descartado por Franco el 27/9 (ver `MEJORAS.md`).
4. **Después, cuando Franco lo pida:** Fase 5, Paso 0 — Cuentas y perímetro (M16). **Gate innegociable: ningún número histórico se mueve un peso.** Arrancar por `docs/PROMPT-INICIO-FASE-5.md`.

**Pendientes menores** (sin apuro; detalle en `MEJORAS.md`): tests de la edición de categorías (cobertura 35%) · retirar `radar-financiero` de Fly (Franco) · dominio propio (estético) · bajar la memoria de Fly ahora que no hay cartera (decisión aparte; `test_scripts_backup` la fija en 1 GB) · migrar a pandas 3 (tarea deliberada, con su propio día).

## 🚩 Bloqueos / decisiones abiertas

- **¿Borrar las tablas `cartera_*` de la base?** Abierta, de Franco. Irreversible; si sí, va como migración nueva detrás de `_NIVEL_REPARACIONES` y con backup antes.
- **Fase 5, Paso 1** contaba con reusar el parser de la Cartera: ahora está solo en el historial de git (ver ADR-0007).
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
