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

## 🔵 Fase 3 — Cartera (Lugar B.1) — **giro a NATIVA** (ADR-0003)
El plan original (Excel-in-the-loop) se reemplazó por **cartera nativa**: DB propia de movimientos, el Excel pasa a oráculo de reconciliación. **Fase 3a** = import + carga recurrente con dedupe + alta manual + posiciones + KPIs (5 pasos). **3b** = realized PnL, cauciones/dividendos como rendimientos, análisis sector/tipo de renta.
- 🔵 **3a paso 1 ✅ (2026-07-23):** parser del broker (ambos formatos) + 43 tests. Suite 157 en verde.
- ⬜ 3a paso 2: modelo de datos (migración M9, `mov_cartera` con TC MEP histórico por fila).
- ⬜ 3a pasos 3-5: `core/market_data/` (precios + caché + override) · posiciones + KPIs + vista · gate `tests/test_cartera_recon.py`.
**Gate:** `tests/test_cartera_recon.py` (cartera app == Excel, fila por fila; cantidades y costos ARS exactos).
**Salida:** la cartera online, con los mismos números que la planilla y más al día que ella.

## ⬜ Fase 4 — Mejoras del Lugar A
Ejecutar el backlog de `MEJORAS.md` sobre Finanzas Personales (incluye lo heredado del `MEJORAS.md` de Mis-Finanzas).
**Salida:** Lugar A pulido.

## ⬜ Fase 5 — Mercado en Vivo (Lugar B.3) + fuente de datos ARG
Resolver la fuente de precios local (`docs/DATOS-MERCADO-ARG.md`), cotizaciones en vivo, cartera conectada a precios automáticos.
**Salida:** la sección más nueva; la más incierta.

## ⬜ Fase 6 (futuro) — Portar la matemática del Excel a Python
Módulo por módulo (FF de renta fija, TIRs, B&S), cada uno con reconciliación fila-a-fila antes de retirar el Excel.
**Salida:** independencia del Excel.

## ⬜ Fase 7 (futuro, opcional) — Multiusuario / escalar
Solo si se abre a otros: aislamiento de datos, planes, costos.
**Salida:** plataforma multiusuario.
