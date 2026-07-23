# B.1 — Dashboard de Cartera

**Estado:** 🔵 En curso (Fase 3a — cartera nativa; ver ADR-0003) · paso 1/5 hecho: `parser.py` + tests

Web-ización de `Inversiones.xlsx`, `Renta fija ARG.xlsx` y `opciones argy.xlsx`.
Arranca **leyendo los Excel** (no reescribe la matemática). Módulos previstos:
- `ingest.py` — parser de movimientos del broker.
- `renta_fija.py` — flujos de fondos / TIRs (duales, CER, LECAPs, ONs).
- `opciones.py` — Black-Scholes.

📊 Gráficos: usar **`tradingview/lightweight-charts`** (velas/series, se embebe en Streamlit). Ver `docs/HERRAMIENTAS-EVALUADAS.md`.

⚠️ **Gate:** `tests/test_cartera_recon.py` debe verificar que la cartera de la app == la del Excel, fila por fila, antes de dar por buena esta sección.
🔧 La skill `actualizar-valuaciones-solidum` mantiene actualizados los Excel de renta fija que este módulo lee.

---
_Antes de tocar este módulo: leé `/GUIA-DE-TRABAJO.md` y `/ESTADO.md` en la raíz. Al terminar, actualizá `bitacora_de_trabajo.md` de esta carpeta._
