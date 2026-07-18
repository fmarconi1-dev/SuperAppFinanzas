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

## 2026-07-17 — Grupo familiar D2 (Cutover) completo
- **Autor:** Claude (Fable 5), con Franco. Plan heredado del MEJORAS.md de Mis-Finanzas (D1 Shadow ya estaba en producción).
- **Backend:** `core/workspaces.py` (crear/unirse/salir, código de invitación hasheado SHA-256 mostrado una sola vez, multi-owner) + contextvar `current_workspace` + migración M8 (PKs por workspace en categorias/presupuesto/configuracion, rebuild patrón M5) + cutover de TODAS las queries del dominio a `workspace_id` (transactions, categorias, budget, metrics, export, ingest, config). `user_id` queda como autor. Sin workspace elegido, todo resuelve al personal → comportamiento pre-D2 idéntico.
- **UI:** badge de modo (violeta Personal / esmeralda Familiar), switcher en sidebar, sección "Espacio compartido" en Configuración, "Firmar como" en Transacciones (etiqueta cosmética), badge grande en modo familiar, onboarding evaluado contra el personal.
- **Tests:** 11 nuevos (código único, join/leave, firma, Personal ≠ Familiar). Suite total: 112 en verde.
- **Riesgos premortem #5:** mitigados (badge por color+texto, callbacks vía session_state, label declarado cosmético, refactor verificado con grep de filtros residuales).
