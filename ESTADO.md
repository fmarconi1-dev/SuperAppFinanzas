# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".

<!-- ultima_actualizacion: 2026-07-17 · autor: Claude (Fable 5) · cierre: D2 + incidente resuelto -->

## 🧭 Dónde estamos

- **Fase actual:** Fase 2 ✅ + **Grupo familiar D2 desplegado y verificado** ✅ (2026-07-17). Próxima: **Fase 3 — Cartera**.
- **Situación:** Superapp en producción con login único, dos lugares (Finanzas + Inversiones/Scoring), y **espacios compartidos** (grupo familiar D2) funcionando. 114 tests en verde. Incidente de migración del 17/7 resuelto (ver Nota post-incidente). radar-financiero sigue vivo como respaldo.
- **Hosting:** Fly.io. App `superapp-finanzas` (gru, 1 GB, auto-stop, volumen `finanzas_data` con snapshots diarios). Sin secrets (radar tampoco tenía; SIGNUP_CODE/SESSION_SECRET opcionales, ver `.env.example`). Ver `docs/DEPLOY.md`.
- **Repo git:** hasta `8a5087a` (migración Fase 1) + commits de cierre. Verificar push al retomar.

## 🔵 Tarea en curso

| Tarea | Estado | Autor | Desde |
|---|---|---|---|
| — (ninguna en curso) | — | — | — |

## ✅ Hecho hasta ahora

- Premortem de la idea (`Premortem - Superapp Finanzas.html` + transcripción).
- Plan de trabajo maestro (`PLAN DE TRABAJO - Superapp Finanzas.md`).
- `EN-HUMANO.md` (diario en lenguaje llano) y `docs/PROMPT-INICIO-FABLE.md` (prompt de arranque).
- Esqueleto del monorepo: carpetas, READMEs, bitácoras, documentos de gobierno, `.gitignore`, `.pre-commit-config.yaml`, `.env.example`, docs y ADR-0001.
- **Fase 0 completa (2026-07-10):**
  - Primer commit del esqueleto pusheado al repo GitHub.
  - Pre-commit hook instalado con **dos capas**: chequeo anti-datos puro `sh` (funciona también desde GitHub Desktop/Windows, sin dependencias) + framework `pre-commit` cuando está disponible. **Probado:** un `.xlsx` de prueba fue bloqueado en ambas capas.
  - Hola mundo Streamlit desplegado en Fly.io (`app.py`, `Dockerfile`, `fly.toml`, `.dockerignore` anti-leak). Deploy verificado por Franco.

## ⏭️ Próximo paso concreto

**Fase 3 — Cartera (Excel-in-the-loop)**, ver `ROADMAP.md`:
1. Franco da acceso a la carpeta con `Inversiones.xlsx` y `Renta fija ARG.xlsx`.
2. `places/inversiones/cartera/` lee el Excel y arma el dashboard (posiciones, estructura, TIR de renta fija).
3. Gate obligatorio: `tests/test_cartera_recon.py` — cartera app == Excel, fila por fila.
4. Revisar antes `docs/HERRAMIENTAS-EVALUADAS.md` (lightweight-charts para gráficos) y `docs/DATOS-MERCADO-ARG.md`.

**Pendientes menores:**
- Retirar `radar-financiero` cuando la superapp esté validada unos días (`fly apps destroy radar-financiero`).
- Generar `requirements.lock` para builds reproducibles (ver `docs/DEPLOY.md`).
- Dominio personalizado (FreeDomain o propio): decisión de Franco, queda para el final — es estético. Pasos en `docs/DEPLOY.md`.

## 🚩 Bloqueos / decisiones abiertas

- Fuente de datos de mercado ARG: 🟢 candidatos en `gauss314/skills` (`bcra-macro`, `data912`, `byma`, `mae`). Se valida y elige en Fase 5. Ver `docs/DATOS-MERCADO-ARG.md`.
- Nombre de la app Fly: `superapp-finanzas`. **Fly no permite renombrar apps**; si se quiere otro nombre, crear app nueva y redeployar **antes** de crear el volumen de la DB (Fase 1), o resolverlo con dominio propio (FreeDomain).

## ⚠️ Nota post-incidente: migraciones (17/7/2026)

M4 (PK con user_id) se re-disparó tras M8 (PK con workspace_id) porque su guard solo miraba la PK: reconstruyó las tablas descartando `workspace_id` y desvinculó los datos en producción. Resuelto: guard de M4 exige tabla no-post-D2, y M8.5 repara filas huérfanas (idempotente, prefiere el dato original ante duplicados). **Lecciones para futuras migraciones:** (1) los guards de migraciones viejas deben seguir siendo correctos frente a esquemas futuros; (2) los tests de idempotencia deben correr CON datos y verificar vínculos, no solo que no crashee. Tests de regresión en `tests/test_workspaces_d2.py`.

## ⚠️ Nota operativa: git + OneDrive

La carpeta del repo vive en OneDrive y dio problemas reales en esta sesión: locks huérfanos (`HEAD.lock`, `index.lock`), archivos commiteados truncados por sync parcial y un índice corrupto (recuperado sin pérdida). **Protocolo para el Claude que trabaje acá:** editar archivos vía shell (no solo herramientas de archivo), y tras cada commit verificar `git status` limpio + `git fsck` + conteo de líneas de los archivos tocados en HEAD. Si git no ve un cambio, `touch` + `git update-index --really-refresh`. Mitigación aplicada (2026-07-10): Franco activó "mantener siempre en este dispositivo" para la carpeta, eliminando los placeholders cloud-only. El protocolo de verificación sigue vigente igual.

## 📌 Recordatorios permanentes

- No commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`).
- Una fase a la vez, cerrada y desplegable.
- Cerrar sesión = actualizar bitácora + este archivo.
