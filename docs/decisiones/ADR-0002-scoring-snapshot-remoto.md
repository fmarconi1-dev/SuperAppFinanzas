# ADR-0002 — El scoring se consume como snapshot remoto (no se migra el batch)

**Fecha:** 2026-07-15 · **Estado:** aceptada · **Fase:** 2

## Contexto
El plan maestro (§4/§6) preveía mover `Scoring-Inversiones` a
`places/inversiones/scoring/` + `jobs/build_snapshot.py` + workflow propio.
Pero el batch actual ya corre solo (cron 22:00 UTC hábiles), publica
`data.json` en GitHub Pages y mantiene el tablero público
`fmarconi1-dev.github.io/Scoring-Inversiones/` — que Franco quiere conservar
abierto (previsto en el plan §9).

## Decisión
En Fase 2 la superapp **consume el snapshot publicado** (`data.json` de Pages)
vía `places/inversiones/scoring/snapshot.py`: caché en memoria 15 min +
copia local de fallback en `data/` (ignorada por git) + estado de error con
retry. El código de cálculo (src/, data/build_snapshot.py) NO se copia al
monorepo; sigue viviendo en el repo público.

## Consecuencias
- ✔ El batch no se toca (cero riesgo de romper lo que funciona); el tablero
  público sigue vivo; se respeta la regla "el scoring corre en batch".
- ✔ Menos código duplicado en el monorepo.
- ✖ Dependencia de GitHub Pages en runtime → mitigada con caché + fallback.
- Si algún día se cierra el tablero público, ahí sí se porta el batch a
  `jobs/` con su workflow (reabrir esta ADR).
