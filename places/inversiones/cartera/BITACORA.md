# places/inversiones/cartera/

<!-- huella: 3ac66b0c73e5 -->

Resumen: Cartera nativa (B.1): parser de exports del broker (2 formatos), ledger cronológico con PPC móvil, posiciones, KPIs por método del patrimonio, renta fija y la vista con upload.

## Buscar acá si

- números que no calzan con el broker o el Excel → `posiciones.py`, `tenencias.py` y el gate `tests/test_cartera_recon.py`
- importar movimientos o tenencias, dedupe, formatos viejo/nuevo del export → `parser.py`, `tenencias.py`, `ingest.py`
- rendimiento, TIR, resultado realizado → `ledger.py` (PPC móvil, ADR-0005), `kpis.py`
- cauciones, cuenta remunerada, dividendos → `rendimientos.py`
- vencimientos, cupones, TIR esperada y duration → `vencimientos.py`, `renta_fija.py`
- composición por tipo de renta y sector → `analisis.py`
- un ticker que el broker no informa o cantidades a corregir a mano → `ajustes.py`
- la pantalla de Cartera, el upload, quién puede verla (`CARTERA_USER_IDS`) → `view.py`
- exportar la cartera a Excel → `export.py`

## Trampas

- **ORDEN DE IMPORT**: Excel primero (trae los saldos iniciales sintéticos, que no existen en el broker), exports del broker encima; al revés el capital aportado se desploma (US$11,5k → US$4,9k).
- El export de movimientos **no** reconstruye la cartera solo: el pagaré viene sin cantidad y los ajustes de ratio de CEDEAR no generan movimiento → la tenencia del broker es la foto que manda (M10). El BTC vive fuera del custodio: tenencia manual (fecha reservada `"manual"`).
- La amortización devuelve **capital + interés**: sin `costo_amortizado_*` las letras rinden ~100% de mentira.
- Todo agregado bimonetario se valida contra la identidad `patrimonio − aportes`; sumar operación por operación da resultados muy equivocados (lección del 23/7).
- `view.py`: 1.879 LOC y co-cambia con `core/db.py`; es el archivo más caro de leer del repo.

## Estado

- **Funciona:** Fases 3a y 3b completas, en producción; panel de renta fija con cronogramas de Docta (agosto).
- **Pendiente:** amortizaciones parciales de bonos vivos (primera relevante: AE38 el 9/7/2027; en MEJORAS.md).

## Proximo paso

Split de `view.py` en paneles (propuesta 3 del estudio del repo, a confirmar con Franco). Crónica completa en `bitacora_de_trabajo.md`.
