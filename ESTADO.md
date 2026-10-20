# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".
> Este archivo es una **foto, no una crónica**: la narrativa de cada sesión va a la `bitacora_de_trabajo.md` del módulo y a `/BITACORA.md`; lo que ya cerró se muda a `docs/archivo/ESTADO-historial.md`. Para ubicar código sin releer el repo: **`/MAPA.md`**.
> **Verificá antes de confiar:** `git log --oneline -15` + `git status`. Si lo que ves no coincide con esto, gana lo que ves — y corregí este archivo.

<!-- ultima_actualizacion: 2026-10-20 · autor: Claude (Opus 5.5) · handoff: Fase D completa en código (pasos 1 a 6) y commiteada en main; suite 862 passed, 0 skipped. Sin desplegar: Franco prueba todo a fin de mes (ver el paso 4 del próximo paso) y carga GEMINI_API_KEY para las fotos. -->
<!-- anterior: 2026-10-17 · autor: Claude (Opus 5.5) · handoff: Fase B (briefings de Gemini por el Secretario + evento:/tarea:/agenda) CERRADA en producción, probada punta a punta por Franco. Siguiente: Fase C (dashboard "secretario" + rebranding). -->
<!-- anterior: 2026-10-14 · autor: Claude (Opus 5.5) · handoff: Franco pidió retirar Inversiones entera (ADR-0007). Código, tests y página fuera; tablas cartera_* intactas en la base. Suite 359 passed, 0 skipped. -->
<!-- anterior: 2026-09-27 · autor: Claude (Opus 5.5), autónomo · handoff: el backup externo llevaba un mes sin correr (la tarea no existía y dependía de la sesión de fly, que vence). Copia sacada y scripts arreglados (token de la app, sin cuelgues, aviso en el Escritorio); falta que Franco guarde el token y registre la tarea. Además: aviso de form_motivo silenciado, tests de login, trampa 27 cerrada. Suite 909 passed, 0 skipped. Franco guardó el token, registró la tarea, pusheó y desplegó (v27) el mismo 27/9; verificado. -->

## 🧭 Dónde estamos

- **Fase actual: Fase D — conciliación desde el Secretario (ADR-0009), EN CURSO desde el 18/10/2026.** Fusiona la Fase D de ADR-0008 y la Fase 5 (ADR-0006, cuyo §1 queda reemplazado). Paso 1 (ADR-0009 + `docs/PLAN-FASE-D.md`) **aprobado por Franco el 19/10/2026**, con las 8 preguntas contestadas. **Paso 2** (varios gastos en un mensaje = lotes, con el bruto) **en producción, probado por Franco**. **Paso 3** (recibir archivos) **en producción, probado por Franco**. **Pasos 4a, 4b, 5 y 6** (extracto, saldos y ajuste, resúmenes de tarjeta, fotos) **hechos en código, sin desplegar**. La fase queda completa en código; falta la prueba real de Franco a fin de mes.
- **Fases A, B y C — cerradas en producción** (15, 17 y 18/10/2026). Ver la tabla de abajo.
- **Fase 4 — cerrada** (27/8/2026) en lo que hizo: respaldo + CI. Su punto 3 (voz + hitos) lo **descartó Franco el 4/8**; sus puntos 4 y 5 (M4 importador con LLM, M5 API sidecar) **no son de la Fase 4**: quedaron absorbidos por la Fase 5 (M4 es su último paso, M5 su vía de captura del efectivo). No hay ítems vivos de la Fase 4.
- **Inversiones (Lugar B): RETIRADA el 14/10/2026 (ADR-0007)** a pedido de Franco: no la usaba. Salieron `places/inversiones/`, `core/market_data/`, `scripts/verificar_docta.py`, la página de la navegación y sus tests. **Las tablas `cartera_*` siguen en la base de producción, quietas** (borrarlas es una decisión aparte de Franco). Fases 6 y 7 del ROADMAP descartadas.
- **Mantenimiento del 22/9 y del 27/9/2026:** auditoría + limpieza (22/9) y backup + tres mejoras chicas (27/9), sin features. Detalle en `/BITACORA.md`.
- **Suite:** **862 passed, 0 skipped** en local (20/10/2026; 781 el 19/10, 618 el 18/10, 359 tras retirar Inversiones el 14/10). En CI salen `skipped` los tests-oráculo (necesitan los CSV de Franco). **Regla del RUNBOOK: antes de un deploy, local tiene que dar 0 skipped.** Cobertura: 78% (`--cov`, `coverage` instalado en el venv fuera del lock).
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
| **Fase B — briefing + cierre de mercado + agenda** (ADR-0008). Plan: `docs/PLAN-FASE-B.md` | ✅ **CERRADA en producción (17/10/2026)**: los dos briefings de Gemini llegan por el Secretario (CallMeBot apagado) y `evento:` / `tarea:` / `agenda` funcionan punta a punta (probado por Franco) | Claude (Opus 5.5) | 2026-10-17 |
| **Fase C — tablero "secretario" + rebranding** (ADR-0008). Plan: `docs/PLAN-FASE-C.md` | ✅ **Dada por buena por Franco (18/10/2026)**: marca **Secretario**, logo del moño, Inicio con el saldo de la cuenta, semana y tareas con tilde. Los dos últimos commits (saldo/logo y favicon) **faltan pushear y desplegar** | Claude (Opus 5.5) | 2026-10-17 |
| **Fase D — conciliación desde el Secretario** (fusiona la D original y la Fase 5; diseño saldado con Franco el 18/10/2026) | 🔵 **EN CURSO.** Paso 1 ✅ (ADR-0009 + `docs/PLAN-FASE-D.md`, aprobados el 19/10). **Paso 2 ✅ en producción** (lotes + bruto, M19–M20, probado por Franco el 19/10). **Paso 3 ✅ en producción** (recibir archivos). **Paso 4a ✅ en código** (extracto + conciliación, M21), commiteado en `main`, **sin desplegar**. Ajuste inicial ya cargado por Franco | Claude (Opus 5.5) | 2026-10-18 |
| **Números de mercado por código (ADR-0010)**: el 19/10 Gemini mandó cierres de otros días como de hoy. `Mercado.gs` (nuevo) arma el tablero del matutino y el cierre entero; `Reenvio.gs` pone el tablero y descarta el cierre de Gemini. La SuperApp no cambia | 🟡 **Hecho en código, probado con QuickJS contra las fuentes reales, sin commitear.** Falta lo de Franco: pegar `Mercado.gs` y `Reenvio.gs` en el Apps Script, correr `probarMercado` y pasarle a Gemini `docs/PEDIDO-GEMINI.md` | Claude (Opus 5.5) | 2026-10-19 |
| ~~Fase 5 · Paso 0 — Cuentas y perímetro (M16)~~ | Reemplazada: el modelo de cuentas de ADR-0006 §1 se cambió por "filas del banco que se desarman" (Fase D) | — | — |

## ✅ Hecho hasta ahora (resumen; detalle en ROADMAP.md y en el archivo)

- **Fase 0** cimientos · **Fase 1** Lugar A migrado · **Fase 2** shell unificado (el scoring se retiró el 5/8) — cerradas 07/2026.
- **Fase 3a/3b** cartera nativa y rendimientos finos — cerradas 07/2026, desplegadas.
- **Fase 4** respaldo remoto + restore ensayado + CI — 07–08/2026.
- **Renta fija, benchmark, lock, `core/context.py`, split de `view.py`** — 08/2026.
- **27/9/2026:** backup sacado (406 transacciones) y scripts arreglados para que corra solo sin tu sesión y avise si falla; el aviso de `form_motivo` en `fly logs` silenciado (no era error); 30 tests de login y contraseñas; el benchmark ya no usa en silencio un índice sin dividendos.
- **22/9/2026:** la pantalla de Cartera ya no se cae con una tasa devengada (y se puede quitar); precio del broker antes que el devengado; Docta/Yahoo ya no confunden "no contestó" con "no existe"; el mapa no lee carpetas ignoradas; las reparaciones de datos de las migraciones corren una vez; los importes ilegibles se avisan; el CLI del import de Finanzas anda; smoke tests que abren las pantallas.

## ⏭️ Próximo paso concreto

-3. 🟡 **Números de mercado (ADR-0010), lo de Franco:**
   1. En el proyecto de Apps Script del reenvío, agregar `Mercado.gs` y reemplazar `Reenvio.gs`, los dos de `integraciones/google-apps-script/`.
   2. Correr `probarMercado` y mirar el registro. Si Yahoo da error desde Google, el plan B es `GOOGLEFINANCE` en una planilla.
   3. Pegar en la conversación de Gemini el pedido de `docs/PEDIDO-GEMINI.md`: da de baja el cierre y rearma el matutino con `[TABLERO]`.
   4. Mañana, mirar el matutino y el cierre de las 18:30.
   5. Commit en `main` cuando dé el OK.

-2. ✅ **Backup externo: vuelve a andar (15/10/2026, 13:55, 456 transacciones, `auth=token`).** Estuvo caído del 13/10 al 15/10 porque `fly.exe` quedó en 0 bytes tras una actualización a medias; Franco reinstaló flyctl. El token estaba bien: el aviso del Escritorio culpaba al token por error (`_fly_comun.ps1` no distingue "flyctl no ejecuta"; arreglo propuesto como tarea aparte).

-1. ✅ **Fase A (ADR-0008) — CERRADA el 15/10/2026.** El Secretario carga gastos, responde `resumen` y `deshace`, desde WhatsApp y sin costo. Cómo quedó armado (y las trampas: el 9 de los números argentinos, la suscripción de la app a la cuenta de WhatsApp Business): `core/api/BITACORA.md` y `docs/WHATSAPP-CANAL.md`.
   1. ✅ **Costo cero confirmado (15/10):** el texto libre llegó al teléfono sin tarjeta. El primer intento no llegaba porque el número estaba en el panel sin el 9; cargado con el 9, llegó.
   2. ✅ **Desplegado el 15/10/2026** desde `main`, con backup previo. Verificado desde afuera: `/_stcore/health` ok, `/api/health` ok, `/api/privacidad` publicada, `/api/whatsapp` → 503 `sin_configurar` (esperado hasta cargar los secretos). Inversiones ya no está en producción.
   3. ✅ **15/10:** token permanente, secretos en Fly, webhook verificado, `messages` suscripto y **app suscripta a la cuenta de WhatsApp Business** (faltaba: solo estaba la app de prueba de Meta). El primer mensaje real **llegó** a la app (20:50, `from` = `549…`); la respuesta rebotó con 131030 porque se mandaba con el 9 → **corregido en código, falta desplegar**.
   4. ✅ **Prueba real (15/10, 20:58–20:59):** `resumen` (los números de octubre de la base de producción), carga y `deshacer`, todos respondidos.
   ✅ **Fase B cerrada (17/10/2026):** briefings de Gemini (mañana y cierre de las 18:30) por el Secretario, tal cual y respetando la ventana de 24 h; `evento:` / `tarea:` / `agenda` vía `Codigo.gs` (aplicación web); cuentas en el monto. **Siguiente: Fase C** (dashboard que junte finanzas + eventos de la semana + tareas, con `resumen_semana` del Apps Script; rebranding; skill `ui-ux-web-moderno`). Después D (conciliación).
0. ✅ **Retiro de Inversiones mergeado a `main` y desplegado el 15/10/2026** (junto con la Fase A). Sigue abierto, de Franco: si las tablas `cartera_*` se borran de la base (irreversible; hoy quedan quietas).
1. **Franco, el 28/9 o después:** `powershell -ExecutionPolicy Bypass -File scripts\estado_backup.ps1` → tiene que dar todo en verde (la tarea todavía no corrió nunca al 27/9). Si aparece "BACKUP SUPERAPP - FALLO.txt" en el Escritorio, dice qué pasó.
2. **Franco:** vaciar la Papelera cuando quieras (los dos `.tar.gz` del 18/8).
3. ~~Login sin distinguir mayúsculas~~ — descartado por Franco el 27/9 (ver `MEJORAS.md`).
4. **Fase D, pasos 4a, 4b y 5 — en código (20/10/2026), sin desplegar.** Franco: push de `main` y deploy (trae M21 y M22, aditivas, y `pdfplumber` nuevo en el lock: el deploy reconstruye la imagen; backup antes). La prueba, a fin de mes y en este orden: (1) el extracto que termina el 16/10 → `ok` (punto de partida de la caja); (2) los saldos de partida: `18/10, fima 485.428,94 efectivo 154.400` → `ok`; (3) los resúmenes nuevos de AMEX y VISA (cierre 29/10): se guardan; (4) **después del 11/11**, un extracto desde el 1/10 → revisar y `ok`; ahí propone el desarmado de cada resumen → `ok`; (5) los saldos del día → `ok`. Dejar de cargar a mano: "Pago tarjeta", "Venta divisa", los gastos con tarjeta en dólares, y **no desarmar más los pagos a mano** (lo hace el Secretario). Confirmar que el ajuste inicial está en la categoría "Ajuste Reconciliación". **Paso 6 (fotos con Gemini) también en código:** para activarlo, Franco crea una clave en Google AI Studio **en un proyecto sin facturación** y la carga con `fly secrets set GEMINI_API_KEY=... -a superapp-finanzas`; sin ella, el Secretario dice que no puede leer fotos. **La Fase D queda completa en código** (el paso 7 es opcional).

**Pendientes menores** (sin apuro; detalle en `MEJORAS.md`): tests de la edición de categorías (cobertura 35%) · retirar `radar-financiero` de Fly (Franco) · dominio propio (estético) · bajar la memoria de Fly ahora que no hay cartera (decisión aparte; `test_scripts_backup` la fija en 1 GB) · migrar a pandas 3 (tarea deliberada, con su propio día).

## 🚩 Bloqueos / decisiones abiertas

- 🔴 **20/10/2026: el Secretario está caído.** El deploy v38 falló con *insufficient memory available on the current host* y la máquina `6832406f6703e8` quedó detenida en la v37. Desde las 12:46 Fly contesta "machine can't start at the moment" a cada arranque: el servidor físico donde está el volumen (`vol_vwnoex5lqmnz5p9v`, zona cdc5, que Fly creó a las 12:00 al mudarlo desde `vol_vdekqoeo9k5dgz14`, cuyo servidor no responde) no tiene lugar. No es el código. Respaldo verificado: `backups-remotos/superapp-20261020-091556.db` (462 movimientos, integridad ok); lo cargado después de las 9:15 está solo en el volumen. Salida propuesta, en orden: reintentar el arranque; si no, copiar el volumen a otro servidor (`fly volumes fork`) y clonar la máquina sobre la copia. Decide Franco.
- El ajuste inicial quedó cargado por **$82.758,28** (el diseño decía $82.758,25), en "Ajuste Reconciliación" el 18/10 (verificado en el backup del 20/10).

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
