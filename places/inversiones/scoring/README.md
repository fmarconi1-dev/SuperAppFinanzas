# B.2 — Análisis y Scoring

**Estado:** ⬜ No iniciado · **Se implementa en:** Fase 2

Origen: `Scoring-Inversiones` (fundamental estilo value + técnico de 5 indicadores + 'consagrada').
**El cálculo sigue siendo batch EOD en GitHub Actions** (`/jobs/build_snapshot.py`), NO dentro del servidor web. La web solo lee el snapshot generado. Así no se rompe lo que hoy funciona gratis.
Idea a futuro: usar el agente `agente-tesis-inversion` como ayudante para profundizar ideas de inversión sobre los tickers que el scoring marca como atractivos (ver `/MEJORAS.md`).

---
_Antes de tocar este módulo: leé `/GUIA-DE-TRABAJO.md` y `/ESTADO.md` en la raíz. Al terminar, actualizá `bitacora_de_trabajo.md` de esta carpeta._
