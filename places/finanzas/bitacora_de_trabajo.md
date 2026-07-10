# Bitácora — Lugar A — Finanzas Personales

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: — -->

## Estado del módulo
**Fase de implementación:** Fase 1 / 4
**Situación:** ⬜ No iniciado

## Registro

_(sin entradas todavía — este módulo aún no se implementó; ver `/ROADMAP.md`)_

## 2026-07-10 — Migración desde Mis-Finanzas-App (Fase 1)
- **Autor:** Claude (Fable 5), con Franco.
- **Qué:** Código migrado al monorepo: lógica de negocio en `core/` (budget, categorias, categorizer, diario, export, ingest, metrics, parsers, transactions), vistas en `views/` (dashboard, transacciones, diario, mensual, onboarding, configuracion), helpers propios en `helpers/` (_format, _html, _tour). Auth/db/theme subieron a `core/` del monorepo. Imports re-cableados (core.X → places.finanzas.core.X, ui.views → places.finanzas.views).
- **Por qué:** Fase 1 del roadmap: mover, no reescribir.
- **Estado:** ✅ 97 tests en verde, desplegado en Fly.io con datos de producción migrados y verificados por Franco.
