# Prompt de inicio — Fase 3b (Rendimientos finos)

Copiá y pegá el bloque de abajo en un chat nuevo. Antes, dale acceso a la carpeta `SuperAppFinanzas/`.

Estado al escribirlo: **Fase 3a cerrada y en producción** (Fly.io, release v11, verificada por Franco usando la app). Repo hasta `3d77641`. Suite: 249 passed, 3 skipped.

---

> Soy Franco. Trabajamos en mi **Superapp de Finanzas**: un monorepo Streamlit que unifica mis finanzas personales y mis inversiones en una app web. Está en producción en Fly.io (`superapp-finanzas`), es un repo git privado en `main` y lo subo yo con GitHub Desktop. Dale acceso a la carpeta `SuperAppFinanzas/` antes de empezar.
>
> **La Fase 3a (Cartera nativa) está cerrada y desplegada. Hoy arrancamos la Fase 3b (Rendimientos finos).**
>
> ## Antes de proponer o tocar nada, leé en este orden y confirmame que entendiste
>
> 1. `ESTADO.md` — foto actual, el cierre de 3a y el plan de 3b. **El más importante.**
> 2. `docs/decisiones/ADR-0003-cartera-nativa.md` y `ADR-0004-fuente-mep-historico.md` — las decisiones de diseño que ya están tomadas y no se reabren sin motivo.
> 3. `GUIA-DE-TRABAJO.md` + `claude.md` — protocolo y reglas duras.
> 4. `places/inversiones/cartera/bitacora_de_trabajo.md` — el detalle de cómo se construyó el módulo y por qué cada cosa está como está.
> 5. `MEJORAS.md` y `docs/HERRAMIENTAS-EVALUADAS.md` — el backlog y las herramientas ya evaluadas (**reutilizá en vez de reinventar**).
>
> ## Reglas que no se rompen
>
> - **Nunca commitear datos:** `data/`, `*.xlsx`, `*.db`, `.env`. Hay un pre-commit hook que lo bloquea; no lo puentees.
> - **Una fase a la vez**, cerrada y desplegable.
> - **Portar lógica de mi Excel exige test de reconciliación fila a fila.** El Excel es el oráculo.
> - Usá la skill **`ui-ux-web-moderno`** en toda tarea de UI.
> - **El agente no ejecuta trades ni mueve dinero.** Nunca.
> - Documentación y commits **en español**.
> - Al cerrar: actualizás la bitácora del módulo, `EN-HUMANO.md` y `ESTADO.md`.
> - **Los push y los deploy los hago yo.** Vos dejás el commit listo y me avisás.
> - **Ojo con git + OneDrive:** `rm` falla con "Operation not permitted", solo `mv` funciona. Los `.git/index.lock` que queden se mueven a `Borrar/` (carpeta que yo borro antes de cada push). Está en la nota operativa de `ESTADO.md`.
>
> ## Explicame "en humano"
>
> Cada vez que completes un avance importante (mínimo una vez por sesión) actualizá `EN-HUMANO.md` y dame en el chat un resumen en lenguaje llano: qué se hizo, para qué me sirve y qué sigue. Antes de que yo apruebe un paso grande, explicámelo en criollo primero.
>
> ## Lo que ya está construido (no lo rehagas)
>
> Módulo `places/inversiones/cartera/` (~3.600 líneas) + `core/market_data/`:
>
> - **`parser.py`** — lee los dos formatos de export del broker (inviu): el viejo con columna "Operación" y el nuevo sin ella. Infiere la moneda (la columna del Excel no es confiable), aparea dividendos espejo, maneja pagarés (`#TICKER`).
> - **`ingest.py`** — importa con dedupe por `UNIQUE(user_id, hash_dedupe)`, congela el TC MEP por operación, autodetecta el tipo de archivo subido, y `remapear_tickers_base()` repara importaciones viejas.
> - **`posiciones.py`** — costo promedio ponderado, costo USD a TC histórico, capital aportado, TIR por bisección.
> - **`kpis.py`** — valuación y KPIs en dos planos: tenencia viva y rendimiento total.
> - **`tenencias.py`** — foto del custodio + tenencias manuales (activos fuera del broker).
> - **`view.py`** — la pestaña Cartera: un solo uploader multi-archivo, la app decide el orden.
> - **`export.py`** — export a Excel con el formato de mi Resumen.
> - **`core/market_data/`** — MEP histórico (argentinadatos) y precios (data912 + yahoo), con `fetch` inyectable, caché, fallback y override.
>
> **249 tests, 3 skipped.** El gate `tests/test_cartera_recon.py` reconcilia contra mi Excel y se saltea solo si no está la variable `CARTERA_XLSX` (así corre en CI). **Corré la suite antes y después de tocar cualquier cosa.**
>
> ## Trampas del dominio que ya nos costaron caro — no las repitas
>
> Esto es lo más valioso de la fase anterior. Cada punto fue un error real que costó horas:
>
> 1. **Nunca sumes resultado instrumento por instrumento para obtener el total de la cartera.** En una cartera bimonetaria, pasar importes en USD a pesos con el TC de cada fecha hace que la devaluación infle el resultado. Verificado: $9,92M por componentes contra $2,27M por patrimonio. **El método correcto es patrimonio:** `resultado = (tenencia + efectivo) − (depósitos − retiros)`, cada aporte al MEP de su fecha. Todo agregado nuevo se contrasta contra una identidad contable independiente **antes** de mostrarse.
> 2. **El capital invertido no es la suma de las compras.** Eso es capital *rotado*: cuenta la misma plata cada vez que se reinvierte. Es depósitos menos retiros.
> 3. **La amortización devuelve capital + interés.** Si no le restás el costo del capital de esas unidades, las letras dan rendimientos de 100%+. Existe `costo_amortizado_ars/usd` por esto.
> 4. **El export de movimientos NO alcanza para reconstruir la cartera.** Dos casos probados: los pagarés (`Compra cheque` trae el monto pero no la cantidad) y los ajustes de ratio de CEDEAR (no generan movimiento). Por eso hay **dos fuentes**: movimientos = histórico y costos; tenencia del broker = foto actual de cantidades. Su diferencia *es* la reconciliación.
> 5. **No guardes valores derivados en el momento del import.** `ticker_base` se guardaba al importar; si el import corría sin el mapa de instrumentos, las variantes en dólares quedaban como posiciones separadas (`SPYD` aparte de `SPY`) — y **el dedupe después impedía que se autocorrigiera al reimportar**. O derivás al leer, o hay una reparación explícita.
> 6. **Cuando un número no cierra, sospechá de la cantidad antes que del precio.** El BTC mostraba US$192 en vez de US$203: la cantidad venía del saldo inicial del Excel (0,003) y la real era 0,00316847.
> 7. **Los precios del broker vencen.** Sin expiración (hoy 3 días) la cartera queda congelada en la fecha del snapshot.
> 8. **data912 sirve los bonos multiplicados por 100** (AE38: 127.360 contra 1.262,6 del broker).
> 9. **El BCRA no publica MEP** (su serie es el mayorista A3500). La fuente es `argentinadatos`, decidido en ADR-0004.
> 10. **Para XIRR usá bisección, no Newton** — con flujos irregulares Newton diverge.
> 11. **Un warning de `fly deploy` que dice "not listening on the expected address" puede ser falso positivo.** Antes de tocar código: `fly status`, `fly releases` y el health endpoint (`/_stcore/health`). El `grace_period` de 30s a veces no alcanza para el primer arranque.
>
> ## Cómo verificar de verdad
>
> Los dos últimos bugs de 3a **no los encontraron los tests: los encontré yo usando la app**. Los tests pasaban porque probaban el camino limpio. La lección: **reproducí mi secuencia real de uso**, incluyendo el orden equivocado (importar sin el Excel primero, reimportar después) y datos que ya existen en la base. Si un cálculo cambia, comparalo contra el número de mi Excel o contra un cálculo manual de una posición, y mostrame la tabla antes/después.
>
> ## Tarea de hoy: Fase 3b — Rendimientos finos
>
> En orden de importancia (está en `ESTADO.md`):
>
> 1. **Amortizaciones parciales de bonos vivos.** Es lo más importante y lo más delicado. Hoy el modelo es binario: `cant_amortizada` devuelve 0 si el instrumento está activo, o todo el remanente si está vencido (señal `Activo en cartera = NO` en la hoja `Config`). No existe el estado intermedio. Cuando el AE38 empiece a amortizar en cuotas, el flujo va a entrar como cobrado **sin reducir la tenencia** → el bono queda sobrevaluado y el rendimiento inflado (cobra la cuota y conserva las unidades enteras). Hay que modelar el cronograma de amortización. `byma` (cronogramas) y `mae` (flujos de fondos) están en `docs/HERRAMIENTAS-EVALUADAS.md`; evaluá si sirven antes de escribir algo propio.
> 2. **Resultado realizado por operación** (hoy el realizado es un agregado).
> 3. **Cauciones y dividendos como rendimientos**, con su propia tasa.
> 4. **Análisis por sector** (reusando el sector del snapshot de scoring) y **por tipo de renta**.
>
> La renta fija de `Renta fija ARG.xlsx` **no** va en la cartera: queda para una futura sección de análisis de mercado (está en `MEJORAS.md`).
>
> **Confirmame el plan antes de codear**, decime con cuál de los cuatro puntos arrancamos y avisame si al leer el código encontrás algo que no cierra. Si algo de lo que te pido choca con una decisión ya tomada en un ADR, decímelo en vez de improvisar.

---

_Actualizá este prompt cuando la Fase 3b cierre: la "tarea de hoy" pasa a ser la fase siguiente y las trampas nuevas se suman a la lista._
