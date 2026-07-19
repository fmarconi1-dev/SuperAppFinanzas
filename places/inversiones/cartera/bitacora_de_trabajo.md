# Bitácora — B.1 — Dashboard de Cartera

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: — -->

## Estado del módulo
**Fase de implementación:** Fase 3 / 6
**Situación:** ⬜ No iniciado

## Registro

_(sin entradas todavía — este módulo aún no se implementó; ver `/ROADMAP.md`)_

## 2026-07-19 — Estudio de los Excel + diseño de la cartera nativa (sin código aún)
- **Autor:** Claude (Fable 5), con Franco.
- **Qué:** se estudió `Inversiones.xlsx` completo (LEEME, Cartera, Resumen Cartera, General, Config, Apoyo, Movimientos Crudo/Procesado) y se decidió con Franco el giro a **cartera nativa** (DB propia, mecánica tipo Transacciones) en vez de Excel-in-the-loop → `docs/decisiones/ADR-0003-cartera-nativa.md`. Decisiones: TC histórico por operación (BCRA), costo promedio ponderado, precios automáticos vía gauss314/skills con caché+override, alcance 3a = import + carga recurrente + posiciones + KPIs.
- **Hallazgos:** (1) el broker cambió el formato del export en mayo 2026 y el Excel no procesa 31 movimientos desde el 20/5 — el parser nativo debe soportar ambos formatos; (2) dos `#REF!` en Resumen Cartera por una fila huérfana (reparación indicada: eliminar fila 32 de Movimientos Procesado); (3) columna Moneda del formato viejo poco confiable.
- **Estado:** diseño cerrado y spec del parser documentada en `ESTADO.md`. Próximo: construir el parser con tests.
