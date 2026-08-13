# ADR-0002 — El scoring se consume como snapshot remoto (no se migra el batch)

**Fecha:** 2026-07-15 · **Estado:** ⛔ **RETIRADA (5/8/2026)** · **Fase:** 2

> ## ⛔ Esta decisión ya no aplica
>
> **El 5/8/2026 Franco pidió eliminar la pestaña de Scoring de la app:** *"creo
> que es demasiado y no tiene influjo real de información"*. Mostraba un ranking
> de ~20 empresas que no cambiaba ninguna de sus decisiones.
>
> **Lo que se retiró:** `places/inversiones/scoring/` (vista y lector del
> snapshot), su test, la pestaña, y el escalón del scoring en la cascada de
> resolución de sectores.
>
> **Lo que sobrevive:** el repo `Scoring-Inversiones` y su tablero público
> siguen existiendo y corriendo por su cuenta — nunca fueron parte de esta app,
> que solo leía su snapshot. Esta decisión sigue siendo válida como registro de
> *por qué no se migró el batch*.
>
> **Consecuencia técnica:** los sectores de la cartera se resuelven ahora
> **100% con Yahoo** (`core/market_data/sectores.py`), que ya cubría el total
> de la renta variable de Franco. Sin el snapshot como primer escalón, cada
> ticker nuevo cuesta una consulta — pero se cachea en DB, incluida la caché
> negativa, así que es una vez por ticker y nunca más.
>
> **Si algún día se quiere volver atrás:** el código está en el historial de
> git; el snapshot se sigue publicando.

---

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
