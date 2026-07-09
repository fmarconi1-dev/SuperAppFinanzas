# ESTADO — foto actual del proyecto

> **Este es el archivo más importante para retomar el trabajo.** Se lee primero y se actualiza último, cada sesión.
> Antes de editar código, actualizá la tabla "Tarea en curso". Al cerrar, dejá el "Próximo paso concreto".

<!-- ultima_actualizacion: 2026-07-09 · autor: Claude (Opus 4.8) · sesión de scaffolding -->

## 🧭 Dónde estamos

- **Fase actual:** Fase 0 — Cimientos.
- **Situación:** Esqueleto del repo creado (estructura de carpetas, bitácoras, READMEs, documentos de gobierno). **Sin código de aplicación todavía.**
- **Hosting:** decidido en el plan (Fly.io para el MVP), **no** configurado aún.
- **Repo git:** inicializado localmente en `SuperAppFinanzas/` (rama `main`, creado con GitHub Desktop). Falta el primer commit del esqueleto y publicarlo como repo **privado** en GitHub.

## 🔵 Tarea en curso

| Tarea | Estado | Autor | Desde |
|---|---|---|---|
| — (ninguna en curso) | — | — | — |

## ✅ Hecho hasta ahora

- Premortem de la idea (`Premortem - Superapp Finanzas.html` + transcripción).
- Plan de trabajo maestro (`PLAN DE TRABAJO - Superapp Finanzas.md`).
- `EN-HUMANO.md` (diario en lenguaje llano) y `docs/PROMPT-INICIO-FABLE.md` (prompt de arranque) creados. Regla nueva: explicar 'en humano' cada avance.
- Esqueleto del monorepo: carpetas, `README` por módulo, `bitacora_de_trabajo.md` por módulo, documentos de gobierno (README, GUIA-DE-TRABAJO, ROADMAP, BITACORA, MEJORAS, claude.md), `.gitignore`, `.pre-commit-config.yaml`, `.env.example`, docs y ADR-0001.

## ⏭️ Próximo paso concreto

Completar **Fase 0** (ver `ROADMAP.md`):
1. Primer commit del esqueleto y publicar el repo como **privado** en GitHub (vía GitHub Desktop).
2. Instalar y probar el pre-commit hook (`pre-commit install`) con un commit de prueba que intente meter un `.xlsx` → debe fallar.
3. Elegir/confirmar hosting y desplegar un "hola mundo" Streamlit (sin lógica).
4. Recién entonces pasar a **Fase 1** (migrar Mis-Finanzas-App a `places/finanzas/`).

## 🚩 Bloqueos / decisiones abiertas

- Fuente de datos de mercado ARG: 🟢 candidatos identificados en `gauss314/skills` (`bcra-macro`, `data912`, `byma`, `mae`). Falta validar y elegir combinación en Fase 5. Ver `docs/DATOS-MERCADO-ARG.md`.
- Confirmar credenciales/proyecto de Fly.io a reutilizar (o crear nuevo).

## 📌 Recordatorios permanentes

- No commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`).
- Una fase a la vez, cerrada y desplegable.
- Cerrar sesión = actualizar bitácora + este archivo.
