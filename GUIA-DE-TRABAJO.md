# Guía de Trabajo — cómo continuar el proyecto sin pisarse

Este proyecto lo van a llevar adelante **varias conversaciones con Claude (u otros), de a una por vez** (trabajo secuencial). Esta guía es el contrato que hace que un Claude pueda retomar donde lo dejó el anterior sin romper nada ni duplicar trabajo.

## El principio

**`ESTADO.md` es la única fuente de verdad sobre "qué está pasando ahora".** Todo lo demás (código, bitácoras) es historia. Antes de trabajar se lee `ESTADO.md`; después de trabajar se actualiza `ESTADO.md`. Si dos versiones de la realidad no coinciden, gana `ESTADO.md`.

## Protocolo de cada sesión (checklist)

**Al abrir la sesión (handoff-in):**

1. Leer `ESTADO.md` completo. Entender la fase actual, la tarea en curso y los pendientes.
2. Leer `ROADMAP.md` para ubicarse en la fase.
3. Leer el `README.md` y la `bitacora_de_trabajo.md` del módulo que vas a tocar.
4. **Revisar `docs/HERRAMIENTAS-EVALUADAS.md` y `docs/DATOS-MERCADO-ARG.md`**: antes de codear una fase, chequear si alguno de los repos/skills evaluados (o uno nuevo) aporta a *esta* etapa. Si conviene, usarlo; si aparece uno nuevo, evaluarlo y anotarlo ahí. **No reinventar lo que ya existe probado.**
5. Confirmar con Franco qué tarea se toma **antes** de empezar. Marcar en `ESTADO.md` la tarea como `🔵 EN CURSO` con fecha y quién.

**Durante la sesión:**

5. Trabajar en **una sola tarea/fase por vez.** No abrir tres frentes.
6. Respetar la arquitectura de `docs/ARQUITECTURA.md`. Si hay que desviarse, se registra una decisión (ADR) en `docs/decisiones/`.
7. No inventar features fuera del alcance de la fase actual. Lo nuevo va a `MEJORAS.md`.

**Al cerrar la sesión (handoff-out) — obligatorio:**

8. Actualizar la `bitacora_de_trabajo.md` del módulo tocado (una entrada: fecha · autor · qué · por qué · estado).
9. **Actualizar `EN-HUMANO.md`** con una entrada en lenguaje llano (qué se hizo / para qué te sirve / qué sigue) **y dar en el chat un resumen 'en humano'** del avance. Cada vez que se completa un avance importante y, como mínimo, una vez por sesión.
10. Agregar una entrada a `BITACORA.md` (raíz) si el avance es relevante a nivel proyecto.
11. Actualizar `ESTADO.md`: mover la tarea a hecha o dejarla como en curso con el punto exacto donde quedó y **el próximo paso concreto**.
12. Actualizar el estado de la fase en `ROADMAP.md` si corresponde.
13. Confirmar que los tests están verdes (cuando haya tests).

> Regla mnemónica: **"leo ESTADO → tomo una tarea → dejo ESTADO mejor de como lo encontré".**

## Reglas duras (no negociables)

- 🔒 **Nunca commitear datos.** Nada de `data/`, `*.xlsx`, `*.db`, `.env`. El `.gitignore` y el pre-commit hook son la red; el criterio sos vos. Antes de un push mental: `git status` no debe mostrar datos.
- 🔒 **Repo privado.** El monorepo con la cartera es privado. Punto.
- ✅ **Tests verdes antes de tocar UI.** El gate de `tests/` protege los números. Si rojea, se arregla antes de seguir.
- 📏 **Una fase a la vez, cerrada y desplegable.** No se pasa a la siguiente sin terminar la anterior (ver premortem: riesgo de alcance infinito).
- 🧮 **Portar matemática = reconciliar.** Cualquier lógica migrada del Excel a Python necesita un test que la compare fila-a-fila con el Excel antes de darla por buena.
- 📝 **Sin bitácora no hay cierre.** Una sesión sin entrada de bitácora se considera no terminada.
- 🙂 **Explicá 'en humano' seguido.** Cada avance importante (mínimo 1 vez por sesión): actualizá `EN-HUMANO.md` y resumí en el chat, sin tecnicismos, qué se hizo, para qué sirve y qué sigue. Antes de pedir aprobación de un paso grande, explicalo primero en llano.
- 🧰 **Revisá el toolbox en cada fase.** Antes de construir algo, mirá `docs/HERRAMIENTAS-EVALUADAS.md` y los repos listados: reutilizá lo probado (charts, datos, cálculo) en vez de reescribirlo.

## Convenciones

- **Ramas:** `main` siempre desplegable. Trabajo en `fase-N/descripcion` o `feat/descripcion`. Merge por PR (aunque trabajes solo: el PR te obliga a revisar el diff → última defensa anti-leak).
- **Commits:** en español, imperativo, con prefijo: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- **Idioma:** toda la documentación y los commits en español.
- **Skills/agentes a usar** (ver `MEJORAS.md` para el detalle):
  - `ui-ux-web-moderno` → siempre que se trabaje la estética/UI (tema en `core/theme`, dashboards, formularios).
  - `agente-tesis-inversion` → como ayudante para profundizar ideas de inversión sobre tickers del scoring (a futuro).
  - `actualizar-valuaciones-solidum` → para mantener actualizados los Excel de renta fija que lee la cartera.

## Qué NO hacer

- No empezar por "la app unificada perfecta". Se construye por capas (ver ROADMAP Fase 0→1→2…).
- No meter el cálculo del scoring dentro del servido