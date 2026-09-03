# Prompt de inicio — Fase 5, Paso 0 (cuentas y perímetro, M16)

Copiá y pegá el bloque de abajo en un chat nuevo. Antes, dale acceso a la carpeta `SuperAppFinanzas/`.

Estado al escribirlo (27/8/2026, cierre de jornada): **Fase 4 cerrada en lo que hizo; arranca la Fase 5 (ADR-0006).** Suite: **743 passed, 0 skipped** en local. Desplegado el 27/8.

---

> Soy Franco. Trabajamos en mi **Superapp de Finanzas**: un monorepo Streamlit que unifica mis finanzas personales y mis inversiones en una app web. Está en producción en Fly.io (`superapp-finanzas`), es un repo git privado en `main` y lo subo yo con GitHub Desktop. Dale acceso a la carpeta `SuperAppFinanzas/` antes de empezar.
>
> ## Antes de proponer o tocar nada, leé en este orden y confirmame que entendiste
>
> 1. `ESTADO.md` — foto actual y próximo paso. **El más importante.**
> 2. **`docs/decisiones/ADR-0006-captura-source-first.md`** — la decisión que define toda esta fase. **Leelo entero antes de escribir una línea.**
> 3. `MAPA.md` — el índice del repo. La tabla "Donde buscar que" resuelve casi todos los "¿dónde está X?". Para lo puntual: `python .mapa/buscar.py "<término>"`. **No barras el repo con grep si el mapa ya tiene la respuesta.**
> 4. `GUIA-DE-TRABAJO.md` + `claude.md` — protocolo y reglas duras.
> 5. `ROADMAP.md` — los 7 pasos de la Fase 5.
> 6. La `BITACORA.md` (router + trampas) y la `bitacora_de_trabajo.md` (crónica) de la carpeta que vayas a tocar.
>
> ## Reglas que no se rompen
>
> * **Nunca commitear datos:** `data/`, `*.xlsx`, `*.db`, `.env`. Hay un pre-commit hook de tres capas; no lo puentees.
> * **Un paso a la vez**, cerrado y desplegable. Lo nuevo que se te ocurra va a `MEJORAS.md`.
> * **Portar lógica de mi Excel exige test de reconciliación fila a fila.** El Excel es el oráculo.
> * Usá la skill **`ui-ux-web-moderno`** en toda tarea de UI.
> * El agente **no ejecuta trades ni mueve dinero**. Nunca.
> * Documentación y commits **en español**.
> * Al cerrar: bitácora del módulo + `EN-HUMANO.md` + `ESTADO.md`, y sellá la bitácora de la carpeta tocada (`python scripts/indexar.py . --sellar <carpeta>`).
> * **Los push y los deploy los hago yo.** Vos dejás el commit listo y me avisás.
>
> ## Cómo correr la suite (leé esto, me hizo perder tiempo)
>
> ```powershell
> .venv\Scripts\python.exe -m pytest -q
> ```
>
> **Usá el ejecutable del venv directo, no actives.** Tengo Python 3.11 (la del `Dockerfile`, en `.venv`), 3.12 y 3.14 en el sistema. Si corrés `python -m pytest` a secas agarra la 3.14, que no tiene las dependencias, y la suite **ni siquiera colecta**. Y en PowerShell `activate.bat` no hace nada: es de cmd.
>
> Tiene que dar **743 passed, 0 skipped**. Los 3 que en otros entornos aparecen como `skipped` son los tests-oráculo (necesitan mi Excel y mis CSV, que no se versionan). **Regla del RUNBOOK: antes de un deploy, en mi máquina tiene que dar 0 skipped.** Si ves un número de skipped que no esperabas, miralo aunque todo esté verde: un `skip` ya tapó un `SyntaxError` que dejó una pantalla caída.
>
> ## Explicame "en humano"
>
> Cada vez que completes un avance importante (mínimo una vez por sesión) actualizá `EN-HUMANO.md` y dame en el chat un resumen en lenguaje llano: **qué se hizo, para qué me sirve y qué sigue**. Antes de que yo apruebe un paso grande, explicámelo en criollo primero.
>
> ## Por qué existe esta fase (el resumen del ADR-0006)
>
> Toda app de finanzas personales se degrada porque **su exactitud es función de mi disciplina**, y pasadas ~72 horas "cargar los gastos" ya es reconstruir desde el resumen del banco. La Cartera nunca tuvo ese problema porque la foto del broker es un ancla que no se olvida (trampa nº4: dos fuentes, y su diferencia es la reconciliación). **Esta fase le da esa ancla a Finanzas Personales.**
>
> El gasto deja de ser "la suma de lo que tipeé" y pasa a ser **"lo que sale del perímetro de mis cuentas"**. Las fuentes proponen, yo confirmo, el agente dedupea.
>
> **Mi situación real:** cuatro cuentas (caja de ahorro —donde vive todo mi débito—, **dos tarjetas de crédito** y efectivo). Exporto en **Excel**. **No uso Mercado Pago ni billeteras.** **Sin backfill:** de acá en adelante. El efectivo es 10-15% de mi gasto y también tiene ancla, porque las extracciones figuran en la caja de ahorro.
>
> ## Lo que ya está construido (no lo rehagas)
>
> **Lugar A — Finanzas Personales** (`places/finanzas/`): 5 pestañas (Dashboard, Transacciones, Diario, Mensual, Configuración) + onboarding y tour. Grupo familiar (D2). Import de `Diario.csv`/`Mensual.csv`, export a Excel, backup automático en cada escritura.
>
> **Lugar B.1 — Cartera** (`places/inversiones/cartera/`): parser de los dos formatos del export de inviu con dedupe · ledger cronológico con PPC móvil (ADR-0005) · KPIs por método del patrimonio · TIR por bisección · rendimientos · vencimientos (M14, resueltos también desde el cronograma) · renta fija con cronogramas de Docta (M15) · composición · **benchmark money-weighted vs SPY/Merval** · ajustes de tenencia (M13). La pantalla está partida: `view.py` es orquestador y los paneles viven en `cartera/paneles/`.
>
> **Núcleo** (`core/`): SQLite con M1–M15 + backups · auth · `core/context.py` (usuario y workspace activos, **sin dependencias**) · theme Cosmic Slate · `market_data/`.
>
> **Infra:** Fly.io, CI, pre-commit de tres capas, `requirements.lock` verificado, mapa vivo del repo.
>
> ## Trampas del dominio que ya nos costaron caro — no las repitas
>
> 1. **Nunca sumes resultado instrumento por instrumento para el total de la cartera.** El método correcto es **patrimonio**: `resultado = (tenencia + efectivo) − (depósitos − retiros)`.
> 2. **El capital invertido no es la suma de las compras.** Eso es capital *rotado*. Es depósitos menos retiros.
> 3. **La amortización devuelve capital + interés.**
> 4. **Una sola fuente no alcanza para reconstruir la verdad.** Dos fuentes, y **su diferencia es la reconciliación**. Es el patrón que funda el ADR-0006.
> 5. **No guardes valores derivados al importar.** O derivás al leer, o hay una reparación explícita.
> 6. **Cuando un número no cierra, sospechá de la cantidad antes que del precio.**
> 7. **Los precios del broker vencen** (hoy 3 días).
> 8. **data912 sirve los bonos ×100.**
> 9. **El BCRA no publica MEP** (ADR-0004).
> 10. **Para XIRR usá bisección, no Newton.**
> 11. **Un warning de `fly deploy` sobre "not listening" puede ser falso positivo.** Chequeá `fly status` y el health antes de tocar código.
> 12. **Un hecho posterior no puede cambiar un resultado anterior.**
> 13. **El realizado y el costo del remanente van juntos.**
> 14. **Corregir un movimiento ya importado exige recalcular el `hash_dedupe`.**
> 15. **Las tasas se ponderan por capital y tiempo, no se promedian.**
> 16. **"No tengo el dato" y "no existe el dato" son cosas distintas.**
> 17. **Si un formulario se bifurca, las dos ramas tienen que definir lo mismo.**
> 18. **Antes de elegir un endpoint, probalo.**
> 19. **Toda consulta externa necesita caché negativa.**
> 20. **El broker se equivoca.** Cuando un rendimiento es absurdo, es un dato malo, no un trade.
> 21. **Un movimiento "descubierto" no es un error de cálculo: es un hecho que falta.** Preguntá qué pasó en el mundo.
> 22. **Todo costo cargado a mano necesita su aporte de capital**, con su fecha.
> 23. **Un número recordado y uno verificado se ven iguales en una tabla.** Si es estimación, se guarda que lo es.
> 24. **El parser no lleva el TC MEP: se congela al importar.** Los totales en pesos se validan contra la DB o la app, nunca contra el parser.
> 25. **Python no valida los nombres hasta que ejecuta la línea.** `tests/test_nombres_definidos.py` lee el bytecode.
> 26. **Nunca compares tu rendimiento acumulado contra el de un índice.** La comparación honesta es money-weighted.
> 27. **Para un benchmark usá `adjclose`, no `close`.**
> 28. **Un lock congela lo verificado, no lo último.** Antes de regenerar `requirements.lock`, leé su cabecera.
> 29. **El dato que falta puede estar ya en la base.** Antes de construir una fuente nueva, fijate si dos módulos que ya existen no se están hablando.
> 30. **Dos fuentes exactas que se contradicen no se resuelven en silencio.**
> 31. **`core/context.py` no puede importar nada del proyecto.** Y `core/auth/current_user.py` es una fachada: re-exporta los mismos objetos, no copias.
> 32. **Hay tests que escanean el código fuente por AST.** Si movés una función de archivo se rompen, y está bien.
> 33. **NO elimines el motivo "Pago tarjeta".** Hoy es el **único rastro** de mi consumo con crédito en todos los meses ya cerrados. Borrarlo o reclasificarlo hacia atrás derrumba mi gasto histórico y rompe Previsión vs Realidad. Cambia de semántica hacia adelante, nunca hacia atrás.
> 34. **Un traspaso solo puede marcarse como tal cuando existe la fuente que cubre el otro lado.** Un pago de tarjeta cubre consumos de ~un mes antes: con una fecha de corte fija y sin backfill, el primer mes desaparece entero. Por eso **un pago es traspaso si y solo si el resumen que lo cubre fue importado** — la reconciliación es el interruptor. Los errores de esta familia **fallan hacia abajo**, que es la dirección que no se nota: mirá siempre si una clasificación puede *esconder* gasto, no solo duplicarlo.
> 35. **El LLM nunca decide plata.** Extrae formato y propone etiquetas; el hash de identidad, el matching por monto y fecha, y todos los totales son **determinísticos y con tests**. El LLM ordena candidatos que un filtro determinístico ya produjo; no los inventa.
>
> ## Cómo verificar de verdad
>
> Los bugs que importaron **no los encontraron los tests**: los encontré yo usando la app, o aparecieron al mirar los números reales. **Reproducí mi secuencia real de uso**, incluyendo el orden equivocado y datos que ya existen en la base. Si un cálculo cambia, comparalo contra mi Excel o contra un cálculo manual, y **mostrame la tabla antes/después**.
>
> ## Tarea de hoy: Fase 5, Paso 0 — Cuentas y perímetro (migración M16)
>
> Darle a `transacciones` la noción de **dónde está la plata**, que hoy no tiene (`fecha, pasivos, ingresos, motivo, comentario` y nada más).
>
> **Qué incluye:**
> * Tabla `cuentas`: caja de ahorro, Tarjeta 1, Tarjeta 2, efectivo.
> * `cuenta_id` y `cuenta_contraparte_id` en `transacciones`. Un gasto tiene contraparte nula (sale del perímetro); un traspaso tiene las dos. Con eso sale gratis el **saldo por cuenta**, que es lo que después permite reconciliar el efectivo.
> * El traspaso reusa el grupo **`Flujo Capital`**, que **ya existe en el CHECK de la base y que `metrics.py` no cuenta como gasto** (solo suma `Gasto Fijo + Gasto Variable`). No hay que tocar el motor de métricas.
> * Todo lo existente cae en una cuenta "Histórico".
>
> **El gate innegociable:** **ningún número histórico se puede mover un peso.** Quiero un test que compare todos los agregados (por mes, por grupo, por subcategoría) antes y después de migrar. Sin backfill la migración es puramente aditiva, así que esto tiene que dar exacto, no aproximado.
>
> **Antes de codear:** leé el ADR-0006, proponeme el esquema de la migración en criollo y esperá mi OK. Acordate de la nota post-incidente de `ESTADO.md` sobre migraciones: los guards de las migraciones viejas tienen que seguir siendo correctos frente a esquemas futuros (M4 se re-disparó tras M8 y desvinculó datos en producción).
>
> _~1 día estimado._
>
> ## Lo que sigue después (no lo empieces hoy)
>
> Paso 1: importador de movimientos de caja de ahorro en Excel (reusa `parse_archivo_excel` de la Cartera). **Para eso te voy a pasar un export real mío.** Después: clasificador de traspasos y mapa de comercios aprendido · resúmenes de tarjeta ×2 con la reconciliación pago↔resumen · cuenta efectivo + WhatsApp (el viejo M5) · dedupe entre fuentes · y por último la generalización con LLM (el viejo M4). Detalle en `ROADMAP.md`.
>
> ## Pendientes sueltos (no son la tarea de hoy)
>
> * Preguntarle al broker por la fila del **TTM26** del 4/2/2026 (17.395 nominales por $17,78 — el resto de ese día se compró a $1,458). **No lo toques sin que yo confirme.**
> * Retirar `radar-financiero` de Fly (`fly apps destroy radar-financiero`) — es mío, cuando quiera.
> * Dominio propio (FreeDomain). Estético, va último.
> * **Amortizaciones parciales** de bonos vivos: primera fecha real **12/7/2027** (AE38).
> * En la fila del Lugar B: cripto desde Binance (read-only) · exposición por moneda (necesita una regla acordada conmigo) · correlación fija-vs-variable.
>
> Confirmame el plan antes de codear y avisame si al leer el código encontrás algo que no cierra. Si algo de lo que te pido choca con un ADR, decímelo en vez de improvisar.
>
> **Actualizá este prompt cuando el Paso 0 cierre:** la "tarea de hoy" pasa al Paso 1, y las trampas nuevas se suman a la lista.
