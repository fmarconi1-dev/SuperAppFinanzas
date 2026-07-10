# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".

<!-- ultima_actualizacion: 2026-07-10 · autor: Claude (Fable 5) · sesión de cierre de Fase 0 -->

## 🧭 Dónde estamos

- **Fase actual:** Fase 0 — Cimientos → **COMPLETADA** ✅. Próxima: Fase 1.
- **Situación:** Repo publicado en GitHub (`fmarconi1-dev/SuperAppFinanzas`), pre-commit hook instalado y probado, "hola mundo" Streamlit desplegado en Fly.io. **Sin código de aplicación todavía** (el `app.py` actual es solo el hola mundo).
- **Hosting:** Fly.io confirmado. App `superapp-finanzas`, región `gru`, auto-stop (costo ~0 en reposo). Ver `docs/DEPLOY.md`.
- **Repo git:** commits `3a72222` (esqueleto) → `8ed32e8` (fix doc truncado) → `083b69a` (hola mundo) → `71a552c` (DEPLOY.md), pusheados a `main`.

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

**Fase 1 — migrar Mis-Finanzas-App a `places/finanzas/`** (ver `ROADMAP.md`):
1. Dar acceso al repo de Mis-Finanzas-App al Claude de la sesión.
2. Mover el código a `places/finanzas/`; subir auth/db/theme a `core/`.
3. Tests heredados (reconciliación, KPIs, parsers) en verde tras mover.
4. Redeploy y verificación.

## 🚩 Bloqueos / decisiones abiertas

- Fuente de datos de mercado ARG: 🟢 candidatos en `gauss314/skills` (`bcra-macro`, `data912`, `byma`, `mae`). Se valida y elige en Fase 5. Ver `docs/DATOS-MERCADO-ARG.md`.
- Nombre de la app Fly: `superapp-finanzas`. **Fly no permite renombrar apps**; si se quiere otro nombre, crear app nueva y redeployar **antes** de crear el volumen de la DB (Fase 1), o resolverlo con dominio propio (FreeDomain).

## ⚠️ Nota operativa: git + OneDrive

La carpeta del repo vive en OneDrive y dio problemas reales en esta sesión: locks huérfanos (`HEAD.lock`, `index.lock`), archivos commiteados truncados por sync parcial y un índice corrupto (recuperado sin pérdida). **Protocolo para el Claude que trabaje acá:** editar archivos vía shell (no solo herramientas de archivo), y tras cada commit verificar `git status` limpio + `git fsck` + conteo de líneas de los archivos tocados en HEAD. Si git no ve un cambio, `touch` + `git update-index --really-refresh`. Mitigación aplicada (2026-07-10): Franco activó "mantener siempre en este dispositivo" para la carpeta, eliminando los placeholders cloud-only. El protocolo de verificación sigue vigente igual.

## 📌 Recordatorios permanentes

- No commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`).
- Una fase a la vez, cerrada y desplegable.
- Cerrar sesión = actualizar bitácora + este archivo.
