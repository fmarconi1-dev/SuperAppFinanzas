# ADR-0007 — Se retira el lugar Inversiones (Cartera + Mercado en vivo)

**Fecha:** 2026-10-14 · **Estado:** ✅ Aceptada · **Fase:** mantenimiento entre fases (antes de arrancar la Fase 5)

## Contexto

El 14/10/2026 Franco pidió sacar toda la sección de Inversiones: *"me doy cuenta que es algo que no se utiliza y no creo que valga la pena incorporarlo, creo que es momento de dejarlo ir"*.

El lugar B tenía dos pestañas:

- **Cartera** (Fases 3a/3b + extras de 08/2026, ADR-0003/0004/0005): import del broker, posiciones, rendimiento por el método del patrimonio, TIR, realizado con PPC móvil, cauciones y dividendos, composición, renta fija con cronogramas de Docta, vencimientos y benchmark contra SPY/Merval.
- **Mercado en vivo**: un cartel reservando la Fase 6, sin código.

Es la misma lógica que retiró el scoring el 5/8/2026 (ADR-0002): una sección que existe no justifica su costo si no cambia nada de lo que Franco hace. Y en este caso el costo no era chico: ~550 de los 909 tests, todo `core/market_data/` y tres fuentes externas (data912/Yahoo, argentinadatos, Docta) que mantener vivas.

## Decisión

Se saca de la app **todo el código** del lugar Inversiones, y **se conservan los datos**.

**Lo que se retiró:**

- `places/inversiones/` entero (cartera, paneles, `home.py`, el placeholder de `mercado_vivo/`).
- `core/market_data/` entero (MEP, precios, sectores, índices, cronogramas, `_errores.py`): solo lo usaba la cartera.
- `scripts/verificar_docta.py`.
- La página "Inversiones" de la navegación en `app.py`. La app queda con un solo lugar: Finanzas.
- Los tests propios (`test_cartera_*`, `test_market_data*`) y los tramos de cartera de tests compartidos (smoke, backup/restore, importes ilegibles). `test_db_concurrencia` no se borró: ahora revisa todo `places/` en vez de la vista de cartera.

**Lo que NO se tocó, a propósito:**

- **Las tablas `cartera_*` de la base y sus migraciones (M9–M15 en `core/db.py`).** Producción tiene los movimientos reales de Franco. Sacar el esquema abre un camino a perder datos de forma irreversible, y la nota post-incidente de `ESTADO.md` muestra lo frágiles que son los guards de migraciones. Los datos quedan quietos: nadie los lee ni los escribe, siguen viajando en cada backup y `scripts/verificar_backup.py` los sigue contando.
- La categoría "liquidación de inversiones" del dashboard de Finanzas: es un tipo de ingreso, no la sección.

## Alternativas consideradas

- **Ocultar la pestaña y dejar el código.** Descartada: el código muerto se sigue pagando (tests, dependencias, fuentes externas que se caen) sin que nadie lo use.
- **Borrar también las tablas.** Postergada, no descartada: es una decisión de Franco aparte, irreversible, que necesita su sí explícito y una migración nueva detrás de la marca de `_NIVEL_REPARACIONES`.

## Consecuencias

- La navegación superior desaparece de hecho (un solo `st.Page`). La URL `/inversiones` deja de existir en producción al desplegar.
- Se caen del ROADMAP la **Fase 6** (Mercado en vivo) y la **Fase 7** (portar la matemática del Excel de inversiones). Las ADR-0003, 0004 y 0005 quedan como registro histórico; no se reescriben.
- ⚠️ **Fase 5, Paso 1** decía "reusa el parseo de la Cartera + `hash_dedupe`". Ese parser (`places/inversiones/cartera/parser.py`) ya no está en el árbol. Si sirve, se recupera del historial de git (último commit que lo tiene: **`886b67c`**) y se muda a `places/finanzas/`.
- `DOCTA_CLIENT_ID`/`DOCTA_CLIENT_SECRET` salieron de `.env.example`. Si están cargados como secrets en Fly, quedan sin uso; sacarlos es de Franco (`fly secrets unset ...`).
- Skills que dejan de aplicar a este repo: `actualizar-valuaciones-solidum` (mantenía los Excel que leía la cartera) y `gauss314/skills` como referencia de `core/market_data/`.

## Si algún día se quiere volver atrás

El código está completo en el historial de git, y los datos siguen en la base. El último commit con todo el código es **`886b67c`**. Restaurar es `git checkout 886b67c -- places/inversiones core/market_data scripts/verificar_docta.py` + volver a poner la página en `app.py` + los tests.
