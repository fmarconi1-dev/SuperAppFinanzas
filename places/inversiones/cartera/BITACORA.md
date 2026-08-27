# places/inversiones/cartera/

<!-- huella: 89ae5ac955b3 -->

Resumen: Cartera nativa (B.1): parser de exports del broker (2 formatos), ledger cronológico con PPC móvil, posiciones, KPIs por método del patrimonio, renta fija y la vista con upload.

## Buscar acá si

- números que no calzan con el broker o el Excel → `posiciones.py`, `tenencias.py` y el gate `tests/test_cartera_recon.py`
- importar movimientos o tenencias, dedupe, formatos viejo/nuevo del export → `parser.py`, `tenencias.py`, `ingest.py`
- rendimiento, TIR, resultado realizado → `ledger.py` (PPC móvil, ADR-0005), `kpis.py`
- cauciones, cuenta remunerada, dividendos → `rendimientos.py`
- vencimientos, cupones, TIR esperada y duration → `vencimientos.py`, `renta_fija.py`
- composición por tipo de renta y sector → `analisis.py`
- "¿me fue mejor o peor que el mercado?" → `benchmark.py` (money-weighted, con `core/market_data/indices.py`)
- un ticker que el broker no informa o cantidades a corregir a mano → `ajustes.py`
- la pantalla de Cartera, quién puede verla (`CARTERA_USER_IDS`), el orden de los paneles → `view.py`
- un panel concreto (composición, benchmark, vencimientos, renta fija, caja, ajustes, upload) → `paneles/`
- exportar la cartera a Excel → `export.py`

## Trampas

- **Nunca compares acumulados contra un índice.** Franco aportó en 24 momentos distintos y el índice no: su +36,5% y el +52% del SPY responden preguntas distintas. La comparación honesta es money-weighted (`benchmark.py`): los mismos aportes, en las mismas fechas, puestos en el índice.
- Cada índice se compara contra los flujos de **su** moneda (SPY↔USD, Merval↔ARS). Cruzarlos repite la trampa nº1 del proyecto: la devaluación aparece como rendimiento.
- Un aporte anterior al inicio de la serie del índice **no se estima**: queda en `sin_precio` y la vista dice que la comparación es parcial.

- **ORDEN DE IMPORT**: Excel primero (trae los saldos iniciales sintéticos, que no existen en el broker), exports del broker encima; al revés el capital aportado se desploma (US$11,5k → US$4,9k).
- El export de movimientos **no** reconstruye la cartera solo: el pagaré viene sin cantidad y los ajustes de ratio de CEDEAR no generan movimiento → la tenencia del broker es la foto que manda (M10). El BTC vive fuera del custodio: tenencia manual (fecha reservada `"manual"`).
- La amortización devuelve **capital + interés**: sin `costo_amortizado_*` las letras rinden ~100% de mentira.
- Todo agregado bimonetario se valida contra la identidad `patrimonio − aportes`; sumar operación por operación da resultados muy equivocados (lección del 23/7).
- `view.py`: 1.879 LOC y co-cambia con `core/db.py`; es el archivo más caro de leer del repo.

## Estado

- **Funciona:** Fases 3a y 3b completas, en producción; panel de renta fija con cronogramas de Docta (agosto).
- **Pendiente:** amortizaciones parciales de bonos vivos (primera relevante: AE38 el 9/7/2027; en MEJORAS.md).

## Proximo paso

Nada pendiente. La propuesta 3 (split de `view.py`) se **ejecutó el 27/8/2026**: de 1.990 líneas en un archivo a un orquestador de 760 y diez paneles en `paneles/`, el mayor de 231. Crónica completa en `bitacora_de_trabajo.md`.
