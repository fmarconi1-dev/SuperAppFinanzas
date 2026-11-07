# Bitácora — Lugar A — Finanzas Personales

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: 2026-10-21 -->

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

## 2026-10-20 (noche) — Fase D, paso 6: fotos con Gemini
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `fotos.py`: una foto o captura → filas (Gemini, plan gratuito) → validar → no duplicar lo ya cargado → propuesta con `ok`. Con eso la Fase D queda completa en código.
- **Estado:** ✅ 859 tests, 0 skipped. Sin desplegar; falta que Franco cargue `GEMINI_API_KEY`.

## 2026-10-21 — Rendimiento, frente 1: no dibujar lo que no se mira
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** corre solo la pestaña abierta (`st.tabs(on_change="rerun")` + `.open`, `home.py`); el Excel de Configuración se arma al tocar "Descargar" (callable con el usuario y el workspace, porque Streamlit lo corre en otro hilo); las medias móviles y "Agrupar por" del Dashboard son fragmentos.
- **Por qué:** línea base del 21/10 (`docs/perf/LINEA-BASE.md`): cada click en Finanzas costaba 1,2 s, ~3/4 en armar el Excel que nadie bajaba.
- **Estado:** ✅ 986 tests, 0 skipped. Probándolo apareció que los filtros del Dashboard volvían a su default al cambiar de pestaña: arreglado (`FILTROS_QUE_PERSISTEN`). Medido A/B contra el código anterior en el mismo momento: un click baja 86–98 % según la pestaña (Dashboard 2,1 s → 0,21 s con la PC cargada); la primera carga, −18 % (`docs/perf/FRENTE-1-RENDERS.md`). Sin commitear ni desplegar.

## 2026-10-21 (noche) — Rendimiento, frente 2: no importar lo que no se usa
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** openpyxl se importa al leer un extracto, `metrics` (pandas) al calcular totales, y cada vista de Finanzas al abrir su pestaña. Test nuevo `tests/test_arranque_liviano.py` (falla con el código anterior).
- **Por qué:** Fly apaga la máquina; el primer mensaje y la primera visita pagaban librerías que no usaban. Franco decidió **no** cambiar Plotly por los gráficos nativos (lo que más achicaba el bundle del navegador).
- **Estado:** ✅ 988 tests, 0 skipped. En frío: la API arranca 79 % más rápido (1,46 s → 0,30 s), el primer gasto por WhatsApp 76 %, el primer Inicio 20 % (`docs/perf/FRENTE-2-CARGA-DIFERIDA.md`). Sin commitear ni desplegar.

## 2026-10-21 (más tarde) — Rendimiento, frente 3: caché que no se queda vieja
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** Inicio, Dashboard y Diario reusan lo calculado mientras la base no cambie (`core.db.version_datos()`, que ve también lo que escribe el bot). Tests nuevos en `tests/test_cache_versionada.py`.
- **Estado:** ✅ 994 tests, 0 skipped. Click sin cambios: Inicio −80 %, Dashboard −67 %, Diario −90 %; después de una escritura, igual que antes (`docs/perf/FRENTE-3-CACHE.md`). Probado en el runtime real con un gasto escrito desde otro proceso. Sin commitear ni desplegar.

## 2026-10-21 (más tarde todavía) — Rendimiento, frente 4: sin loops por fila
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `categorizer.grupos_efectivos` en lugar de `iterrows` (metrics, diario, budget); el Diario clasifica solo lo que muestra; M25 en `core/db.py`. Las búsquedas por fila del bot ya tenían índice: no se tocaron.
- **Estado:** ✅ 999 tests, 0 skipped; resultados idénticos al código anterior. `compute_kpis` −92 %, Diario −80 %, Dashboard −29 % después de una escritura (`docs/perf/FRENTE-4-QUERIES.md`). Sin commitear ni desplegar.

## 2026-11-03 — El Secretario no entendía la respuesta como lista numerada
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** el 2/11 Franco contestó la conciliación del extracto renglón por renglón (`1. Compras`, `2. Ok`, … `21. ok`) y el Secretario rechazó los 21 renglones. `comandos._leer_respuesta_lote` solo aceptaba `N algo` separado por comas: el punto después del número y el salto de línea lo hacían caer al parser de varios gastos. Ahora el renglón separa como la coma, `N.`/`N)`/`N-` valen como `N`, y "N ok" deja el renglón como se propuso. `2.500 super` sigue siendo un gasto.
- **Estado:** ✅ tests nuevos en `tests/test_conciliacion.py`; 1000 passed, 1 falla ajena (`test_smoke_pantallas::test_los_controles_de_cada_grafico_del_dashboard_andan`, `KeyError: 'donut_agrupar_por'`). Sin commitear ni desplegar.

## 2026-11-03 (más tarde) — Pendientes de código cerrados
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** smoke del dashboard (el fixture dependía del día del mes), `tests/test_categorias_edicion.py` (categorías 35% → 100%), y `_fly_comun.Test-FlyctlEjecuta` para que un flyctl roto no se informe como token vencido. `ajustes.listar` ya no existía (Cartera retirada).
- **Estado:** ✅ 1018 passed, 0 fallas. Sin desplegar.

## 2026-11-03 (noche) — Fase E, paso 1: el traductor
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `core/api/gemini.py` suma `traducir` (esquema cerrado: orden, pregunta, respuesta, no_entiendo); `places/finanzas/core/lenguaje.py` arma el contexto, valida la orden con los parsers y la deja esperando el *sí*; `comandos.procesar(..., traductor=)` consulta cuando la respuesta trae `entender=True`; `api.py` lo cablea con `ClienteGemini.desde_entorno()`.
- **Por qué:** ADR-0012; el 2/11 Franco contestó como habla y el Secretario rechazó todo.
- **Estado:** ✅ 1061 passed, 0 fallas (`tests/test_lenguaje_natural.py`). Sin desplegar.

## 2026-11-04 — Fase E, paso 2: la prueba con frases reales (preparada)
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `scripts/probar_lenguaje.py` con 46 frases y su evaluador (BIEN / DUDOSA / MAL), con tests. *va* es un *sí* (el 2/11 Franco contestó *va* y se rechazó). Límites de Gemini verificados en AI Studio.
- **Estado:** 🔵 falta correrlo en Fly (la clave vive ahí) y revisar los MAL antes de prender `LENGUAJE_NATURAL=1`.

## 2026-11-04 (más tarde) — Fase E, paso 2: primera corrida real y arreglos
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** la corrida en Fly dio 34 BIEN · 6 DUDOSA · 5 MAL · 1 FALLA. Arreglos: el `ok` que agrega Gemini sin que Franco acepte se saca en código; el script califica la orden que el bot muestra (no la cruda de Gemini) y no marca MAL lo que el bot descarta; pistas de categorías de Franco en el contexto; instrucciones de saldos (sin la caja).
- **Estado:** 🔵 falta la segunda corrida en Fly (con redeploy). Antes: la primera clave era de un proyecto con facturación prepaga agotada (402).

## 2026-11-04 (noche) — Fase E, paso 2: segunda corrida real
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** 44 BIEN · 1 DUDOSA · 1 MAL · 0 FALLA. El MAL (correcciones a renglones no nombrados) se arregló con `lenguaje._solo_lo_nombrado`; el script ahora califica como "descartada" la orden que el bot no deja esperando.
- **Estado:** 🔵 falta la tercera corrida; con cero MAL se prende `LENGUAJE_NATURAL=1`.

## 2026-11-04 (noche, más tarde) — Fase E, paso 2: tercera corrida real
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** 43 BIEN · 2 DUDOSA · 1 MAL · 0 FALLA. Las protecciones de antes funcionaron; el MAL nuevo (una compra de dólares traducida como ingreso) se frena con `lenguaje._signo_cruzado`.
- **Estado:** 🔵 falta la cuarta corrida; con cero MAL se prende `LENGUAJE_NATURAL=1`.

## 2026-11-04 (cierre) — Fase E, paso 2: cero MAL
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** cuarta corrida en Fly: 44 BIEN · 2 DUDOSA · 0 MAL · 0 FALLA. Arreglado el control del signo, que descartaba correcciones a categorías de ingresos.
- **Estado:** ✅ meta cumplida. Próximo: deploy, `fly secrets set LENGUAJE_NATURAL=1 -a superapp-finanzas` y prueba de Franco desde el celular.

## 2026-11-06 — Fase E, paso 3: corregir lo cargado y el modo Gemini
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** a pedido de Franco (dos casos reales: los haberes de UCEMA del 28/10 que son de noviembre, y un café de 20.400 = 19.400 con tarjeta + 1.000 de propina): órdenes `#N fecha DD/MM` y `partir #N …` (`ediciones.py`, se deshacen); regla automática de fecha para Haberes UCEMA desde el 25; modo «hola gemini» / «chau gemini» con memoria de la charla; Gemini ve lo cargado de 60 días. `scripts/probar_lenguaje.py` suma 4 frases de estos casos.
- **Estado:** 🔵 en código, sin commitear; falta la corrida en Fly. El #505 de producción (UCEMA del 28/10) se corrige con `#505 fecha 02/11` después del deploy: la regla vale para lo que entre de ahora en más.

## 2026-11-07 — Fase E, paso 3: probado en Fly
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** corrida de `scripts/probar_lenguaje.py` con las 4 frases nuevas: 48 BIEN · 2 DUDOSA · 0 MAL · 0 FALLA de 50.
- **Estado:** ✅ en main (`ff68f1a`). Falta la prueba de Franco desde el celular.
