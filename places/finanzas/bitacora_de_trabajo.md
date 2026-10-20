# Bitácora — Lugar A — Finanzas Personales

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: 2026-10-19 -->

## Estado del módulo
**Fase de implementación:** en producción desde Fase 1 (Fase D en curso, ADR-0009)
**Situación:** ✅ en producción

## Registro

## 2026-07-10 — Migración desde Mis-Finanzas-App (Fase 1)
- **Autor:** Claude (Fable 5), con Franco.
- **Qué:** Código migrado al monorepo: lógica de negocio en `core/` (budget, categorias, categorizer, diario, export, ingest, metrics, parsers, transactions), vistas en `views/` (dashboard, transacciones, diario, mensual, onboarding, configuracion), helpers propios en `helpers/` (_format, _html, _tour). Auth/db/theme subieron a `core/` del monorepo. Imports re-cableados (core.X → places.finanzas.core.X, ui.views → places.finanzas.views).
- **Por qué:** Fase 1 del roadmap: mover, no reescribir.
- **Estado:** ✅ 97 tests en verde, desplegado en Fly.io con datos de producción migrados y verificados por Franco.

## 2026-07-17 — Grupo familiar D2 (Cutover) completo
- **Autor:** Claude (Fable 5), con Franco. Plan heredado del MEJORAS.md de Mis-Finanzas (D1 Shadow ya estaba en producción).
- **Backend:** `core/workspaces.py` (crear/unirse/salir, código de invitación hasheado SHA-256 mostrado una sola vez, multi-owner) + contextvar `current_workspace` + migración M8 (PKs por workspace en categorias/presupuesto/configuracion, rebuild patrón M5) + cutover de TODAS las queries del dominio a `workspace_id` (transactions, categorias, budget, metrics, export, ingest, config). `user_id` queda como autor. Sin workspace elegido, todo resuelve al personal → comportamiento pre-D2 idéntico.
- **UI:** badge de modo (violeta Personal / esmeralda Familiar), switcher en sidebar, sección "Espacio compartido" en Configuración, "Firmar como" en Transacciones (etiqueta cosmética), badge grande en modo familiar, onboarding evaluado contra el personal.
- **Tests:** 11 nuevos (código único, join/leave, firma, Personal ≠ Familiar). Suite total: 112 en verde.
- **Riesgos premortem #5:** mitigados (badge por color+texto, callbacks vía session_state, label declarado cosmético, refactor verificado con grep de filtros residuales).

## 2026-07-17 (tarde) — Incidente de migración D2 resuelto
- M4 re-disparada post-M8 desvinculaba workspaces en producción. Guard corregido + reparación M8.5 + 2 tests de regresión (ver BITACORA global y nota en ESTADO.md). Verificado por Franco en producción: datos restaurados. Suite: 114 en verde.

## 2026-08-04 — Bug en producción: "Agregar gasto" reventaba desde el celular
- **Autor:** Claude (Opus 5). **Lo encontró Franco usándola**, no los tests — igual que los dos bugs de la Fase 3a.
- **Síntoma:** `UnboundLocalError: cannot access local variable 'firma_val'` al tocar **💸 Agregar gasto**. La app moría entera (traceback de Streamlit en pantalla), no era un error manejado.
- **Causa:** `_form_alta_edicion` se bifurca en **modo rápido** (importe + motivo y nada más) y **modo detallado**, pero después las dos ramas caen al **mismo** código de guardado. `firma_val` se definía únicamente dentro de la rama detallada (el selectbox "Firmar como" del espacio familiar), así que en modo rápido —el que se usa desde el teléfono— la variable no existía cuando el guardado la leía.
- **Por qué no se notó antes:** el modo rápido es reciente y el bug solo aparece al **enviar** el formulario, no al mostrarlo. Desde la compu se suele usar el detallado.
- **Fix:** `firma_val` se define **antes** del `if modo_rapido:`. En modo rápido **no se pregunta** la firma —esa es la gracia del modo— así que se asume el **miembro activo** del espacio familiar; fuera de un espacio familiar queda en `None`, igual que antes.
- **Test — `tests/test_transacciones_formulario.py` (10 tests):** no revisa `firma_val`, revisa **la forma del problema**. Lee el código con `ast` y verifica que ninguna variable leída después de la bifurcación esté definida en una sola rama, descontando las que ya existen antes y las que el guardado crea por su cuenta. Así atrapa también a la próxima variable que alguien agregue a un solo modo. Hay además un test explícito por cada variable que el guardado necesita, para que el mensaje diga **cuál** falta y en qué modo.
- **Verificado de verdad:** con el bug reintroducido a propósito, **fallan 3 tests**; con el fix, pasan los 10.
- ⚠️ **Se hace por AST y no ejecutando el formulario** porque renderizar Streamlit en un test exige un runtime entero. Es una heurística acotada, no análisis de flujo completo: apunta a la clase de error que ya ocurrió. Está dicho en el docstring.
- **Estado:** suite **362 passed, 3 skipped**.

## 2026-09-22 — Importes ilegibles, CLI del ingest y smoke tests
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `parsers.parse_currency_estricto` (ilegible → `None`) y el ingest avisa cada importe ilegible en `ImportResult.advertencias`, con fila y valor; el CLI `python -m places.finanzas.core.ingest` vuelve a arrancar (se sacó un `sys.path.insert` heredado que hacía resolver `core` a `places/finanzas/core`); borradas `budget.previsiones_anuales`/`realidad_mensual` (sin uso; la primera filtraba `workspace_id = user_id`), `categorizer.grupo_de`, `_format.fmt_pct*`. Smoke test que abre las 5 pestañas.
- **Por qué:** auditoría del 22/9 — un `1.5OO` entraba como gasto de $0 sin rastro, y el comentario del parser prometía un aviso que nadie daba.
- **Estado:** ✅ tus CSV reales no tienen ningún importe ilegible (importados a una base temporal: 0 advertencias); el test de reconciliación contra el Excel sigue verde.

## 2026-10-15 — Comandos de WhatsApp (Fase A, ADR-0008)
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `core/comandos.py`: carga `[fecha], monto, categoría[, comentario]` con montos y fechas estrictos, "¿quisiste decir?" para categorías parecidas o nuevas (confirmación sí/no, vence a los 10 min), `resumen` con la fórmula del dashboard, `deshacer` y `ayuda`.
- **Por qué:** que cargar un gasto sea mandar un WhatsApp, sin cargar nada a ciegas.
- **Estado:** ✅ 60 tests; sin desplegar.

## 2026-10-19 — Fase D, paso 2: varios gastos en un mensaje (lotes) y el bruto
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `lotes.py` (propuesta → `ok` → todo o nada con un backup antes → `deshacer` del lote entero, con el antes/después de cada fila); en `comandos.py`, varios renglones = una propuesta numerada, respuestas `ok`/`N categoría`/`N no`/`cancelar`, y `deshacer` de lo último (gasto o lote). El bruto de los gastos con cuenta queda en `gasto_cuentas` (M20). `insert_transaction` partido en `insertar_sin_backup` + backup.
- **Por qué:** es la base de la conciliación (ADR-0009 §6): todo lo que llegue de un extracto o un resumen va a pasar por un lote. El bruto hace falta para reconocer devoluciones y descontar del efectivo lo que salió de verdad.
- **Estado:** ✅ 677 tests en verde, 0 skipped. Sin desplegar: falta que Franco pruebe desde el celular (tres gastos en un mensaje, `ok`, `resumen`, `deshacer`).

## 2026-10-19 (noche) — Fase D, paso 4a: el Secretario lee el extracto de Galicia
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** lector del extracto (`extracto_galicia.py`, verificado contra el archivo real: 406 filas, cadena entera, $153.263,01 al 16/10) y la conciliación (`conciliacion.py`): ancla y empalme, clasificación por tipo, emparejamiento uno a uno con ±$1 y −5/+2 días, empates que se preguntan, devoluciones contra el bruto, regla del corte, sobrantes (efectivo salvo tarjeta) y cola de 5 días. Aplica como un lote y `deshacer` lo revierte entero. Franco decidió tres tipos nuevos (depósito de efectivo = Haberes SBT, transferencias a terceros = gasto por destinatario, percepción RG 5617 = línea neutra).
- **Por qué:** es el corazón de la Fase D (ADR-0009): que cada gasto quede una sola vez.
- **Ensayo con datos reales** (copia del backup, mes 16/9–16/10, solo cantidades): sumó la guarda del corte, los empates entre gastos iguales, los gastos cargados netos y los montos parecidos.
- **Estado:** ✅ 781 tests en verde, 0 skipped. Sin desplegar. Sigue el 4b (FIMA, efectivo y ajuste).

## 2026-10-20 — Fase D, paso 4b: FIMA, efectivo y el ajuste
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `saldos.py`: `fima … efectivo …` (fecha opcional) propone el ajuste como un lote; FIMA esperado = último + suscripciones − rescates; efectivo esperado = último + extracciones − lo gastado en efectivo (por el bruto) + lo cobrado; la diferencia va a Rendimiento FIMA o a Ajuste Reconciliación. Con el `ok`, el control del total. Además, el "¿es el mismo?" de WhatsApp y la sugerencia del ingreso manual antes de un depósito.
- **Estado:** ✅ 794 tests, 0 skipped. Sin desplegar: Franco lo prueba a fin de mes. Sigue el paso 5.

## 2026-10-20 (más tarde) — Fase D, paso 5: los resúmenes de tarjeta
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** lector de los resúmenes AMEX/VISA (`resumen_tarjeta.py`) y el desarmado del pago (`tarjetas.py`): gastos reales con la fecha del pago, la percepción a la línea neutra con su acumulado, los consumos en dólares como Venta divisa + gasto con el dólar del día, sin duplicar lo ya cargado, y la confirmación con el "SU PAGO" del resumen siguiente.
- **Por qué:** el pago de la tarjeta es un contenedor (ADR-0009 §3).
- **Estado:** ✅ 837 tests, 0 skipped. Con los archivos reales los tres ejemplos del diseño dan exacto. Sin desplegar.
