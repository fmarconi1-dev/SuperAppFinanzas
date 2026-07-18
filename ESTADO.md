# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".

<!-- ultima_actualizacion: 2026-07-15 · autor: Claude (Fable 5) · sesión de Fase 2 -->

## 🧭 Dónde estamos

- **Fase actual:** Fase 2 ✅ + **Grupo familiar D2 completo en código** ✅ (2026-07-17, adelanto de Fase 4). Falta el redeploy de Franco y su verificación visual de ambos. Próxima: Fase 3 — Cartera.
- **Situación:** Superapp con **login único y dos lugares**: 🏠 Finanzas (la app original intacta) y 📈 Inversiones (Scoring embebido leyendo el snapshot de GitHub Pages — ADR-0002; Cartera y Mercado como placeholders de F3/F5). 101 tests en verde. radar-financiero sigue vivo como respaldo.
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

1. **Deploy pendiente (Franco):** push + `fly deploy`. Verificar: (a) tablero de scoring con las correcciones; (b) grupo familiar — crear espacio en Configuración, código de invitación, que Agustina se una, badge esmeralda, firmar como, y que Personal ≠ Familiar en el Dashboard.
2. Próxima fase: **Fase 3 — Cartera** (necesita acceso a `Inversiones.xlsx` y `Renta fija ARG.xlsx`).

**Pendientes menores heredados de Fase 1:**
- Retirar `radar-financiero` cuando la superapp esté validada unos días (`fly apps destroy radar-financiero`).
- Franco: borrar `finanzas-prod.db` de la carpeta local (copia de migración, git la ignora).
- Generar `requirements.lock` para builds reproducibles (ver `docs/DEPLOY.md`).
- Dominio personalizado (FreeDomain o propio): decisión de Franco, queda para el final — es estético. Pasos en `docs/DEPLOY.md`.

## 🚩 Bloqueos / decisiones abiertas

- Fuente de datos de mercado ARG: 🟢 candidatos en `gauss314/skills` (`bcra-macro`, `data912`, `byma`, `mae`). Se valida y elige en Fase 5. Ver `docs/DATOS-MERCADO-ARG.md`.
- Nombre de la app Fly: `superapp-finanzas`. **Fly no permite renombrar apps**; si se quiere otro nombre, crear app nueva y redeployar **antes** de crear el volumen de la DB (Fase 1), o resolverlo con dominio propio (FreeDomain).

## ⚠️ Nota operativa: git + OneDrive

La carpeta del repo vive en OneDrive y dio problemas reales en esta sesión: locks huérfanos (`HEAD.lock`, `index.lock`), archivos commiteados truncados por sync parcial y un índice corrupto (recuperado sin pérdida). **Protocolo para el Claude que trabaje acá:** editar archivos vía shell (no solo herramientas de archivo), y tras cada commit verificar `git status` limpio + `git fsck` + conteo de líneas de los archivos tocados en HEAD. Si git no ve un cambio, `touch` + `git update-index --really-refresh`. Mitigación aplicada (2026-07-10): Franco activó "mantener siempre en este dispositivo" para la carpeta, eliminando los placeholders cloud-only. El protocolo de verificación sigue vigente igual.

## 📌 Recordatorios permanentes

- No commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`).
- Una fase a la vez, cerrada y desplegable.
- Cerrar sesión = actualizar bitácora + este archivo.
