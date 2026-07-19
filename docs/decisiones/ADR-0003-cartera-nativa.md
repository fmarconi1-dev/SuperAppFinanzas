# ADR-0003 — Cartera nativa con DB propia (no Excel-in-the-loop)

**Fecha:** 2026-07-19 · **Estado:** aceptada · **Fase:** 3 (adelanta parte de la 6)

## Contexto
El plan original (Fase 3) preveía que la app leyera `Inversiones.xlsx` como
fuente en runtime. Franco pidió la mecánica de Transacciones: DB propia,
import inicial del histórico, carga recurrente (archivo del broker o alta
manual) y cálculos hechos por la app — incluyendo a futuro PnL por trade,
rendimientos de caución/dividendos y análisis por sector/tipo de renta.

## Decisión
- **DB nativa de movimientos** de cartera (scope por usuario; solo Franco por
  ahora, generalizable). El Excel deja de ser fuente en runtime y pasa a ser
  **oráculo de reconciliación**: `tests/test_cartera_recon.py` compara la app
  contra `Resumen Cartera` (cantidades y costos ARS exactos; USD en modo
  "MEP actual" que es la metodología del Excel).
- **TC histórico por operación** (serie MEP, BCRA): cada movimiento congela
  el TC de su fecha al importarse. Vista más fiel que el "MEP actual para
  todo" del Excel (supuesto documentado por Franco como distorsión).
- **Costo promedio ponderado** (como el Excel). FIFO → MEJORAS.
- **Precios de valuación automáticos** vía `gauss314/skills` (`data912`/
  `byma` ARG, `bcra-macro` MEP, `yahoo-finance` CEDEARs/BTC) con capa de
  abstracción por proveedor + caché + override manual (regla del repo:
  nada de "tiempo real" sin resguardo).
- **Etapas cerradas:** 3a = import histórico + carga recurrente con dedupe +
  alta manual + posiciones + KPIs + reconciliación. 3b = realized PnL por
  trade, cauciones/dividendos, análisis sector/tipo de renta.

## Consecuencias
- ✔ Actualización cotidiana sin depender de abrir el Excel.
- ✔ La lógica documentada en el LEEME del Excel se porta con red de tests.
- ✖ Adelanta la fuente de datos ARG (riesgo #4 del premortem) → mitigada
  con caché + fallback manual; la decisión definitiva de fuentes sigue
  siendo de Fase 5.
- El Excel sigue vivo y actualizable (skill Solidum) hasta que Franco
  decida jubilarlo (Fase 6 completa).
