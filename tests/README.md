# tests/ — El gate del proyecto

Ningún merge a `main` sin estos tests en verde. Corren en CI (`.github/workflows/tests.yml`).

Tests previstos (heredados / nuevos):
- `test_reconciliacion.py` — Caja calculada de la app == Caja del origen (finanzas). *Heredado.*
- `test_kpis.py` — Ingresos, gastos, fijos/variables cuadran. *Heredado.*
- `test_parsers.py` — parse_currency / parse_date / parse_expression. *Heredado.*
- `test_cartera_recon.py` — **NUEVO.** Cartera de la app == cartera del Excel, fila por fila. Gate de la Fase 3.

> Si algún test rojea, no se confía en los números de la app hasta resolverlo.
