# ROADMAP — fases del proyecto

Leyenda: ⬜ pendiente · 🔵 en curso · ✅ hecho
Cada fase termina con **algo usable y desplegado**. No se pasa a la siguiente sin cerrar la anterior.

---

## ✅ Fase 0 — Cimientos (cerrada 2026-07-10)
Repo privado, `.gitignore` + pre-commit hook anti-`.xlsx/.db` (probado), estructura de carpetas, documentos de gobierno, hosting elegido con un "hola mundo" desplegado.
- ✅ Estructura de carpetas + bitácoras + READMEs + documentos de gobierno.
- ✅ Repo en GitHub (`fmarconi1-dev/SuperAppFinanzas`) + primer commit pusheado.
- ✅ Pre-commit hook instalado y probado (bloqueó un `.xlsx` de prueba; doble capa, ver ESTADO).
- ✅ Fly.io confirmado + hola mundo Streamlit desplegado (app `superapp-finanzas`).
**Salida:** repo vivo y deploy vacío funcionando. ✔

## ✅ Fase 1 — Lugar A migrado (Finanzas Personales) (cerrada 2026-07-10)
Mover Mis-Finanzas-App a `places/finanzas/`, subir auth/db/theme a `core/`, tests verdes, desplegar.
- ✅ Código migrado y re-cableado (`core/` compartido + `places/finanzas/`).
- ✅ 97 tests heredados en verde.
- ✅ Desplegada en Fly.io con la DB de producción migrada desde radar-financiero; verificada por Franco.
**Salida:** la app actual, igual pero dentro del monorepo, online. ✔

## ✅ Fase 2 — Shell unificado + Scoring (Lugar B.2) (cerrada 2026-07-15)
Navegación con login único entre lugares. Embeber el scoring leyendo el snapshot del batch (GitHub Actions).
- ✅ Shell: login único + navegación superior Finanzas / Inversiones (`st.navigation`).
- ✅ Scoring embebido: lee el snapshot de GitHub Pages con caché + fallback local (ADR-0002; el batch no se movió).
- ✅ 101 tests en verde. Pendiente: deploy verificado por Franco.
**Salida:** un login que lleva a Finanzas y a Scoring. ✔

## ✅ Fase 3 — Cartera (Lugar B.1) — **giro a NATIVA** (ADR-0003) (cerrada 2026-07-30) — ⛔ **RETIRADA el 14/10/2026 (ADR-0007)**
> Franco decidió sacar toda la sección de Inversiones: no la usaba. El código salió de la app (queda en el historial de git); las tablas `cartera_*` siguen en la base, quietas. Lo de abajo es el registro de lo que se hizo.

El plan original (Excel-in-the-loop) se reemplazó por **cartera nativa**: DB propia de movimientos, el Excel pasa a oráculo de reconciliación. **Fase 3a** = import + carga recurrente con dedupe + alta manual + posiciones + KPIs (5 pasos). **3b** = realized PnL, cauciones/dividendos como rendimientos, análisis sector/tipo de renta.
- ✅ **3a paso 1:** parser del broker (ambos formatos) + 43 tests.
- ✅ **3a paso 2:** modelo de datos M9 (`cartera_movimientos` con TC congelado por fila, dedupe) + ingest + gate `tests/test_cartera_recon.py` (reconcilia exacto contra el Excel).
- ✅ **3a paso 3:** `core/market_data/` — MEP histórico (ADR-0004: el BCRA no publica MEP) + precios ARG/yahoo con caché y override.
- ✅ **3a paso 4:** posiciones + KPIs + **vista de Cartera con upload**; import de la tenencia del broker (M10) + tenencias manuales para activos externos; rendimiento por **método del patrimonio** en ARS/USD + **TIR**.
- ✅ **3a paso 5:** recon de **costos en USD** modo "MEP actual" (49 tickers) + divergencias conocidas congeladas en tests.
- ✅ **Fase 3a COMPLETA (2026-07-30).** Verificada con datos reales al 30/7: patrimonio US$15.741 · aportado US$11.534 · **+36,5% acumulado, TIR 24,4% anual en dólares** (602 días). Suite 229 + 3 del gate.
- ✅ **Fase 3a DESPLEGADA (2026-07-30, v11).**
- ✅ **3b punto 2 — resultado realizado por operación (ADR-0005), DESPLEGADO.** Motor cronológico `ledger.py` con PPC móvil: el costo de una venta es el vigente ESE día, no el promedio de toda la historia. Cambió el realizado en 9 tickers (−4,6%); patrimonio, TIR y el gate de recon, intactos. 45 operaciones, 38 ganadoras.
- ✅ **3b punto 3 — cauciones, dividendos y cuenta remunerada.** `rendimientos.py`: 101 cauciones apareadas, interés $33.365 a una **TNA ponderada del 25,60%**; dividendos netos de retención por instrumento; total de la caja $120.562.
- ✅ **3b punto 4 — composición por tipo de renta y sector.** `analisis.py`: renta fija 60,1% · variable 38,3% · cripto 1,3% · efectivo 0,3%; sector sobre la renta variable con 65,7% de cobertura del scoring.
- ✅ **FASE 3b COMPLETA (2026-07-30).** Suite 324 + 3 del gate. Desplegada con la tanda del **5/8/2026**.
- ⬜ **Queda de 3b para más adelante:** las **amortizaciones parciales** de bonos vivos. No urgente: la primera amortización del AE38 es el **12/7/2027** (se creía 9/7, pero **el 9 de julio es feriado** y el pago cae al hábil siguiente; verificado contra el cronograma de Docta el 5/8/2026) y el AN29 es bullet a 2029. Anotado en `MEJORAS.md`.
- ✅ **Extras posteriores al cierre (08/2026):** vencimientos de renta fija (M14) · cronogramas de Docta con caché (M15) · **panel de renta fija** con calendario de cobros, TIR esperada y duration. En `main` hasta `8f8ba73`; **⚠️ falta confirmar el deploy** — el último con registro es el del 5/8.
**Gate:** `tests/test_cartera_recon.py` (cartera app == Excel, fila por fila; cantidades y costos ARS exactos).
**Salida:** la cartera online, con los mismos números que la planilla y más al día que ella. ✔

## ✅ Fase 4 — Mejoras del Lugar A (cerrada 2026-08-27 en lo que hizo; lo pendiente pasó a la Fase 5)
Ejecutar el backlog de `MEJORAS.md` sobre Finanzas Personales. El backlog heredado de `Mis-Finanzas-App` ya se relevó y se volcó a `MEJORAS.md` el 30/7 — **no hace falta volver al repo viejo**, y dos de sus ítems más grandes (grupo familiar D2, módulo de inversiones) ya estaban hechos.
- ✅ **Punto 1 — respaldo externo + restore ensayado + RUNBOOK** (30/7 y 4/8/2026).
- ✅ **Punto 2 — CI** (`tests.yml` + job anti-datos `sin-datos`, 4/8/2026).
- ⛔ **Punto 3 — voz consistente + hitos: DESCARTADO por Franco el 4/8/2026.** Cosmético; no resuelve nada que le moleste usando la app. Anotado en `MEJORAS.md` para que no se vuelva a proponer. **No es el próximo paso** (el `ESTADO.md` lo arrastró por error hasta el 27/8).
- ↪️ **Puntos 4 y 5 — ABSORBIDOS POR LA FASE 5 (27/8/2026).** M4 (importador de CSV con LLM) y M5 (API sidecar) no se hacen tal como estaban planteados: se reordenan dentro de una arquitectura mayor. **Ver ADR-0006.** M4 pasa a ser el *último* paso de la Fase 5 en vez del primero, y M5 deja de ser un fin en sí mismo para convertirse en la vía de captura del efectivo.
**Salida:** Lugar A pulido en respaldo y CI. Lo demás se hace desde la Fase 5.

**Mantenimiento entre fases (22/9/2026) — auditoría + limpieza, sin features nuevas.** Siete bugs corregidos (la pantalla de Cartera se caía con una tasa devengada; la caché negativa de Docta/Yahoo confundía "no contestó" con "no existe"; el mapa leía carpetas ignoradas; migraciones que re-corrían en cada arranque; importes ilegibles como $0 silencioso; el CLI del import de Finanzas roto; texto de fase viejo en la app), `except` achicados, código muerto fuera, smoke tests de pantallas con `AppTest`. **Ningún número de la base de producción cambió** (huella antes/después idéntica). Detalle en `/BITACORA.md`.

---

## ⬜ Fase 5 — Captura *source-first* del Lugar A (ADR-0006) — aprobada, sin arrancar

**El problema que resuelve.** Toda app de finanzas personales se degrada porque su exactitud es función de la disciplina del usuario, y pasadas ~72 horas "cargar los gastos" ya es reconstruir desde el resumen. La Cartera nunca tuvo ese problema porque la foto del broker es un ancla que no se olvida (trampa nº4). **Esta fase le da esa ancla a Finanzas Personales.**

**El cambio de fondo:** el gasto deja de ser "la suma de lo que Franco tipeó" y pasa a ser "lo que sale del perímetro de sus cuentas". Las fuentes proponen; Franco confirma; el agente dedupea. Alcance confirmado: 4 cuentas (caja de ahorro, 2 tarjetas, efectivo), exportación en Excel, **sin backfill**, sin billeteras.

- ⬜ **Paso 0 — Cuentas y perímetro (M16).** `cuentas` + `cuenta_id`/`cuenta_contraparte_id`; el traspaso reusa `Flujo Capital`, que ya existe y que `metrics.py` no cuenta como gasto. **Gate: ningún número histórico se mueve un peso.** ~1 día.
- ⬜ **Paso 1 — Importador de movimientos de caja de ahorro (Excel).** La fuente más grande: débito, transferencias y extracciones. Reusa el parseo de la Cartera + `hash_dedupe`/`UNIQUE` — ⚠️ desde el 14/10/2026 ese parser está solo en el historial de git (ADR-0007): recuperarlo y mudarlo a `places/finanzas/`. ~2 días.
- ⬜ **Paso 2 — Clasificador de traspasos + mapa de comercios aprendido.** ~1,5 días.
- ⬜ **Paso 3 — Resúmenes de tarjeta (×2) + reconciliación pago↔resumen.** La reconciliación **es** lo que convierte un pago en traspaso. ~2 días.
- ⬜ **Paso 4 — Cuenta efectivo + captura por WhatsApp** (acá entra el viejo M5). ~1 semana. Incluir **varios gastos en un mensaje** (texto o audio: "4.200 súper, 1.800 café" → propone tres, Franco confirma), idea anotada en `MEJORAS.md`.
- ⬜ **Paso 5 — Dedupe entre fuentes + panel de reconciliación.** ~1,5 días.
- ⬜ **Paso 6 — Generalización con LLM** (el M4 original, ahora último). ~3 días.

**Reglas duras de la fase:** el LLM **nunca decide plata** (extrae formato y propone etiquetas; el hash, el matching por monto y los totales son determinísticos y con tests) · las fuentes producen **propuestas**, nunca escrituras · un traspaso solo se marca como tal **cuando existe la fuente que cubre el otro lado**.

**Salida:** una app que no se degrada cuando Franco se atrasa. **Total ~2,5 semanas.**

## ⛔ Fase 6 — Mercado en Vivo (Lugar B.3) — DESCARTADA (14/10/2026, ADR-0007)
Se retiró el lugar Inversiones entero. Nunca tuvo código, solo un cartel.

## ⛔ Fase 7 — Portar la matemática del Excel de inversiones a Python — DESCARTADA (14/10/2026, ADR-0007)
Era FF de renta fija, TIRs y B&S: sin lugar Inversiones, no tiene dónde vivir.

## ⬜ Fase 8 (futuro, opcional) — Multiusuario / escalar
Solo si se abre a otros: aislamiento de datos, planes, costos.
**Salida:** plataforma multiusuario.
