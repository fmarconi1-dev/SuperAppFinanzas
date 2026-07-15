# Bitácora — Lugar B — Inversiones / Mercado

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: — -->

## Estado del módulo
**Fase de implementación:** Fases 2/3/5
**Situación:** ⬜ No iniciado

## Registro

_(sin entradas todavía — este módulo aún no se implementó; ver `/ROADMAP.md`)_

## 2026-07-15 — Lugar Inversiones inaugurado con Scoring embebido (Fase 2)
- **Autor:** Claude (Fable 5), con Franco.
- **Qué:** `home.py` con estructura triple visible (Scoring activo; Cartera y Mercado en vivo como placeholders honestos de F3/F5). `scoring/snapshot.py` lee el `data.json` publicado por el batch en GitHub Pages (caché 15 min + fallback local en `data/` + error con retry — nunca rompe por red). `scoring/view.py`: KPIs, filtros (mercado/categoría/búsqueda), tabla con scores como barras de progreso, cambios de categoría y links a Yahoo. El cálculo NO corre acá (ADR-0002).
- **Por qué:** Fase 2 del roadmap; el batch que ya funciona no se toca.
- **Estado:** ✅ 4 tests del snapshot en verde (101 totales).
