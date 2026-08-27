# Prompt de inicio — Fase 4, punto 4 (M4: importador de CSV con LLM)

Copiá y pegá el bloque de abajo en un chat nuevo. Antes, dale acceso a la carpeta `SuperAppFinanzas/`.

Estado al escribirlo (27/8/2026, cierre de jornada): **Fase 4 con los puntos 1 y 2 hechos, el 3 descartado y el 4 (M4) como siguiente.** Suite: **743 passed, 0 skipped** en local. Desplegado el 27/8.

---

> Soy Franco. Trabajamos en mi **Superapp de Finanzas**: un monorepo Streamlit que unifica mis finanzas personales y mis inversiones en una app web. Está en producción en Fly.io (`superapp-finanzas`), es un repo git privado en `main` y lo subo yo con GitHub Desktop. Dale acceso a la carpeta `SuperAppFinanzas/` antes de empezar.
>
> ## Antes de proponer o tocar nada, leé en este orden y confirmame que entendiste
>
> 1. `ESTADO.md` — foto actual y próximo paso. **El más importante.**
> 2. `MAPA.md` — el índice del repo. La tabla "Donde buscar que" resuelve casi todos los "¿dónde está X?". Para lo puntual: `python .mapa/buscar.py "<término>"`. **No barras el repo con grep si el mapa ya tiene la respuesta.**
> 3. `GUIA-DE-TRABAJO.md` + `claude.md` — protocolo y reglas duras.
> 4. `MEJORAS.md` — el backlog. Lo que no es de la fase actual va ahí, no al código.
> 5. La `BITACORA.md` (router + trampas) y la `bitacora_de_trabajo.md` (crónica) de la carpeta que vayas a tocar.
> 6. `docs/decisiones/` — los cinco ADR. Son decisiones tomadas: no se reabren sin motivo.
>
> ## Reglas que no se rompen
>
> * **Nunca commitear datos:** `data/`, `*.xlsx`, `*.db`, `.env`. Hay un pre-commit hook de tres capas; no lo puentees.
> * **Una fase a la vez**, cerrada y desplegable. Lo nuevo que se te ocurra va a `MEJORAS.md`.
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
> ## Lo que ya está construido (no lo rehagas)
>
> **Lugar A — Finanzas Personales** (`places/finanzas/`): 5 pestañas (Dashboard, Transacciones, Diario, Mensual, Configuración) + onboarding y tour. Grupo familiar / espacios compartidos (D2) completo. Import de `Diario.csv`/`Mensual.csv`, export a Excel, backup automático en cada escritura.
>
> **Lugar B.1 — Cartera** (`places/inversiones/cartera/`): parser de los dos formatos del export de inviu con dedupe · ledger cronológico con PPC móvil (ADR-0005) · posiciones y KPIs por método del patrimonio · TIR por bisección · rendimientos (cauciones, dividendos, cuenta remunerada) · vencimientos (M14, ahora resueltos también desde el cronograma) · panel de renta fija con cronogramas de Docta (M15: calendario de cobros, TIR esperada, duration) · composición por tipo de renta / sector / industria / emisor · **benchmark money-weighted contra SPY y Merval** · ajustes de tenencia (M13) · export a Excel.
> La pantalla está partida: `view.py` es el **orquestador** (760 líneas) y cada panel vive en `cartera/paneles/`.
>
> **Núcleo** (`core/`): SQLite con migraciones M1–M15 + backups · auth con bcrypt y tokens firmados · `core/context.py` (usuario y workspace activos, **sin dependencias**) · theme Cosmic Slate · `market_data/` (MEP de argentinadatos, precios data912/Yahoo, sectores, cronogramas de Docta, series de índices).
>
> **Infra:** Fly.io, CI (`tests.yml`), pre-commit de tres capas, `requirements.lock` verificado, mapa vivo del repo con indexador.
>
> ## Trampas del dominio que ya nos costaron caro — no las repitas
>
> Cada punto fue un error real.
>
> 1. **Nunca sumes resultado instrumento por instrumento para el total de la cartera.** En una cartera bimonetaria, pasar USD a pesos con el TC de cada fecha hace que la devaluación infle el resultado ($9,92M por componentes contra $2,27M por patrimonio). El método correcto es **patrimonio**: `resultado = (tenencia + efectivo) − (depósitos − retiros)`.
> 2. **El capital invertido no es la suma de las compras.** Eso es capital *rotado*. Es depósitos menos retiros.
> 3. **La amortización devuelve capital + interés.** Sin restar el costo del capital de esas unidades, las letras dan 100%+.
> 4. **El export de movimientos NO alcanza para reconstruir la cartera.** Dos fuentes: movimientos = histórico y costos; tenencia del broker = foto actual. Su diferencia **es** la reconciliación.
> 5. **No guardes valores derivados al importar.** O derivás al leer, o hay una reparación explícita.
> 6. **Cuando un número no cierra, sospechá de la cantidad antes que del precio.**
> 7. **Los precios del broker vencen** (hoy 3 días).
> 8. **data912 sirve los bonos ×100** (AE38: 127.360 contra 1.262,6 del broker).
> 9. **El BCRA no publica MEP** (su serie es el mayorista A3500). Fuente: `argentinadatos` (ADR-0004).
> 10. **Para XIRR usá bisección, no Newton** — con flujos irregulares Newton diverge.
> 11. **Un warning de `fly deploy` que dice "not listening on the expected address" puede ser falso positivo.** Antes de tocar código: `fly status`, `fly releases` y `/_stcore/health`.
> 12. **Un hecho posterior no puede cambiar un resultado anterior.** El realizado se mide con el PPC vigente al momento de la venta (ADR-0005).
> 13. **El realizado y el costo del remanente van juntos:** `costo liberado + costo remanente = total comprado`.
> 14. **Corregir un movimiento ya importado exige recalcular el `hash_dedupe`.**
> 15. **Las tasas se ponderan por capital y tiempo, no se promedian.**
> 16. **"No tengo el dato" y "no existe el dato" son cosas distintas.** A un bono no le *falta* el sector: no tiene.
> 17. **Si un formulario se bifurca, las dos ramas tienen que definir lo mismo.** Definí las variables compartidas **antes** del `if`.
> 18. **Antes de elegir un endpoint, probalo.** Y exigí coincidencia exacta de símbolo.
> 19. **Toda consulta externa necesita caché negativa**, o un ticker desconocido dispara una búsqueda por carga, para siempre.
> 20. **El broker se equivoca.** Una compra vino con dos ceros de menos. Cuando un rendimiento es absurdo, es un dato malo, no un trade.
> 21. **Una venta "descubierta" no es un error de cálculo: es un hecho que falta.** Antes de tocar el ledger, preguntá **qué pasó en el mundo**.
> 22. **Todo costo cargado a mano necesita su aporte de capital**, con su fecha, o la TIR sale inflada.
> 23. **Un número recordado y uno verificado se ven iguales en una tabla.** Si es estimación, se guarda que lo es.
> 24. **El parser NO lleva el TC MEP: se congela al importar.** Los totales en pesos se validan contra la DB o la app, **nunca contra el parser**.
> 25. **Python no valida los nombres hasta que ejecuta la línea.** `tests/test_nombres_definidos.py` lee el bytecode. Corré la suite antes de dar por buena cualquier vista.
> 26. **Nunca compares tu rendimiento acumulado contra el de un índice.** Yo aporté en 24 momentos distintos y el índice no: son dos preguntas diferentes. La comparación honesta es **money-weighted** (`cartera/benchmark.py`): los mismos aportes, en las mismas fechas, puestos en el índice. Hay un test construido a propósito para que dé +10% donde el índice hizo +100%.
> 27. **Para un benchmark usá `adjclose`, no `close`.** El cierre ajustado incluye dividendos reinvertidos; la app ya cuenta los míos, así que compararme contra un SPY sin dividendos me regala ~1,3% anual.
> 28. **Un lock congela lo verificado, no lo último.** El 27/8 `pip` resolvía `pandas>=2.0.0` como **pandas 3.0.5**, un major contra el que la suite nunca corrió. `requirements.lock` quedó en pandas 2.3.3 con topes explícitos. **Antes de regenerarlo, leé su cabecera.**
> 29. **El dato que falta puede estar ya en la base.** Los vencimientos parseaban la descripción y resolvían 1 de 3, mientras el cronograma de Docta —guardado desde M15— tenía la fecha exacta. Antes de construir una fuente nueva, fijate si dos módulos que ya existen no se están hablando.
> 30. **Dos fuentes exactas que se contradicen no se resuelven en silencio.** Gana la mejor, pero la descartada queda visible (`Vencimiento.discrepancia`) y la vista avisa.
> 31. **`core/context.py` no puede importar nada del proyecto**, o vuelve el ciclo core↔core/auth. Y `core/auth/current_user.py` es una **fachada**: re-exporta los mismos objetos, no copias. Hay tests que miden el grafo de imports en procesos limpios.
> 32. **Hay tests que escanean el código fuente por AST**, no que importan el módulo (`view.py` arrastra Streamlit entero). Si movés una función de archivo se rompen, y está bien: apuntalos a los dos lugares, para que afirmen *qué hace* la función y no dónde vive.
>
> ## Cómo verificar de verdad
>
> Los bugs que importaron **no los encontraron los tests**: los encontré yo usando la app, o aparecieron al mirar los números reales. Los tests pasaban porque probaban el camino limpio. **Reproducí mi secuencia real de uso**, incluyendo el orden equivocado y datos que ya existen en la base. Si un cálculo cambia, comparalo contra mi Excel o contra un cálculo manual, y **mostrame la tabla antes/después**.
>
> ## Tarea de hoy: Fase 4, punto 4 — M4, el importador inteligente de CSV
>
> Es el ítem grande que queda vivo de la Fase 4 (el punto 3, "voz consistente + hitos", **lo descarté el 4/8/2026**: es cosmético; no lo vuelvas a proponer).
>
> **Qué quiero:** subir el CSV de cualquier banco y que la app infiera sola el mapeo de columnas (fecha, descripción, importe, signo) y sugiera categorías, apoyándose en el `categorizer.py` que ya existe.
>
> **La condición que no se negocia:** **preview obligatorio antes de tocar la base.** El modo de falla de esto es *silencioso* — categoriza mal y no me entero — así que tengo que poder ver y corregir fila por fila lo que va a entrar, antes de que entre. Nada de "importar y después arreglás".
>
> **Esfuerzo estimado:** 3-5 días. **Riesgo:** medio.
>
> **Antes de codear:** proponeme el diseño en criollo y esperá mi OK. En particular quiero decidir juntos: de dónde sale la inferencia (llamada a un LLM vs. heurísticas locales), qué pasa cuando el CSV trae una moneda o un formato de fecha que no esperábamos, y cómo se ve el preview.
>
> ## Pendientes sueltos (no son la tarea de hoy)
>
> * Preguntarle al broker por la fila del **TTM26** del 4/2/2026 (17.395 nominales por $17,78 — el resto de ese día se compró a $1,458). **No lo toques sin que yo confirme.**
> * Retirar `radar-financiero` de Fly (`fly apps destroy radar-financiero`) — es mío, cuando quiera.
> * Dominio propio (FreeDomain). Estético, va último.
> * **Amortizaciones parciales** de bonos vivos: primera fecha real **12/7/2027** (AE38). Queda fuera con motivo; ver `MEJORAS.md`.
> * En la fila del Lugar B: cripto desde Binance (read-only) · exposición por moneda (necesita una regla acordada conmigo) · correlación fija-vs-variable (necesita serie histórica del patrimonio).
>
> Confirmame el plan antes de codear y avisame si al leer el código encontrás algo que no cierra. Si algo de lo que te pido choca con un ADR, decímelo en vez de improvisar.
>
> **Actualizá este prompt cuando M4 cierre:** la "tarea de hoy" pasa a ser M5 (API sidecar), y las trampas nuevas se suman a la lista.
