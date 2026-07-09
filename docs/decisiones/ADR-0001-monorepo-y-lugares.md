# ADR-0001 — Monorepo con núcleo compartido + "lugares"

**Estado:** ✅ Aceptada · **Fecha:** 2026-07-09

## Contexto
Hay que unificar tres proyectos (Mis-Finanzas-App, Scoring-Inversiones y la lógica de los Excel de inversiones) en una sola app web, mantenible por varias conversaciones/Claudes, sin estancarse en un refactor gigante (riesgo #1 del premortem).

## Decisión
Un **monorepo** con:
- un `core/` compartido (auth, db, config, market_data, theme),
- un package por **lugar** en `places/` (finanzas; inversiones = cartera + scoring + mercado_vivo).

La integración es **progresiva**: primero se migra cada pieza casi tal cual, después se integra bajo un login único. La "app unificada de verdad" es la meta, no el punto de partida.

## Alternativas consideradas
- **Multi-repo** (seguir con proyectos separados): descartado, no cumple el objetivo de unificar bajo un login.
- **Reescritura de una sola app desde cero**: descartado, alto riesgo de alcance infinito y de perder lógica validada.

## Consecuencias
- ➕ Reutiliza el código y los tests existentes; reduce el refactor.
- ➕ Cada lugar evoluciona sin romper a los otros.
- ➖ Exige disciplina de imports y de fronteras entre `core/` y `places/`.
- ➖ El monorepo debe ser privado (contiene datos de cartera) → candados anti-leak.
