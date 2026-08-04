# Prompt de inicio — Fase 4 (Mejoras del Lugar A: Finanzas Personales)

Copiá y pegá el bloque de abajo en un chat nuevo. Antes, dale acceso a la carpeta `SuperAppFinanzas/`.

Estado al escribirlo: **Fase 3b completa** (puntos 2, 3 y 4; el punto 1 —amortizaciones parciales— quedó en `MEJORAS.md` con motivo). Suite: 342 passed, 3 skipped.

---

> Soy Franco. Trabajamos en mi **Superapp de Finanzas**: un monorepo Streamlit que unifica mis finanzas personales y mis inversiones en una app web. Está en producción en Fly.io (`superapp-finanzas`), es un repo git privado en `main` y lo subo yo con GitHub Desktop. Dale acceso a la carpeta `SuperAppFinanzas/` antes de empezar.
>
> **Las Fases 3a y 3b están cerradas.** La cartera ya me dice cuánto tengo, cuánto gané, en cuánto tiempo, en qué acerté operación por operación, cuánto me rindió la plata quieta y dónde está parada. **Hoy arrancamos la Fase 4: mejoras del Lugar A (Finanzas Personales).**
>
> ## Antes de proponer o tocar nada, leé en este orden y confirmame que entendiste
>
> 1. `ESTADO.md` — foto actual y el plan. **El más importante.**
> 2. `GUIA-DE-TRABAJO.md` + `claude.md` — protocolo y reglas duras.
> 3. `docs/decisiones/` — los cinco ADR. Son decisiones tomadas: no se reabren sin motivo.
> 4. La `bitacora_de_trabajo.md` del módulo que vayas a tocar.
> 5. `MEJORAS.md` y `docs/HERRAMIENTAS-EVALUADAS.md` — el backlog y las herramientas ya evaluadas (**reutilizá en vez de reinventar**).
>
> ## Reglas que no se rompen
>
> * **Nunca commitear datos:** `data/`, `*.xlsx`, `*.db`, `.env`. Hay un pre-commit hook que lo bloquea; no lo puentees.
> * **Una fase a la vez**, cerrada y desplegable.
> * **Portar lógica de mi Excel exige test de reconciliación fila a fila.** El Excel es el oráculo.
> * Usá la skill **`ui-ux-web-moderno`** en toda tarea de UI.
> * El agente **no ejecuta trades ni mueve dinero**. Nunca.
> * Documentación y commits **en español**.
> * Al cerrar: actualizás la bitácora del módulo, `EN-HUMANO.md` y `ESTADO.md`.
> * **Los push y los deploy los hago yo.** Vos dejás el commit listo y me avisás.
> * **Entorno local:** la suite se corre desde `.venv` con **Python 3.11** (la del `Dockerfile`). Tengo también 3.12 y 3.14; con 3.14 y sin dependencias la suite ni siquiera colecta. `py -3.11 -m venv .venv` → `.venv\Scripts\activate.bat` → `pip install -r requirements.txt`. **No hay CI**: si no la corro yo, no la corre nadie.
> * **Ojo con git + OneDrive:** `rm` falla con "Operation not permitted", solo `mv` funciona. Los `.git/*.lock` y `tmp_obj_*` que queden se mueven a `Borrar/` (carpeta que yo borro antes de cada push). Está en la nota operativa de `ESTADO.md`.
>
> ## Explicame "en humano"
>
> Cada vez que completes un avance importante (mínimo una vez por sesión) actualizá `EN-HUMANO.md` y dame en el chat un resumen en lenguaje llano: **qué se hizo, para qué me sirve y qué sigue**. Antes de que yo apruebe un paso grande, explicámelo en criollo primero.
>
> ## Lo que ya está construido (no lo rehagas)
>
> **Lugar B.1 — Cartera** (`places/inversiones/cartera/`, ~4.400 líneas) + `core/market_data/`:
>
> * `parser.py` — los dos formatos del export de inviu, moneda inferida, espejos de dividendo, pagarés (`#TICKER`). Expone `clave_dedupe`/`hash_dedupe`: **la regla de identidad de un movimiento vive en un solo lugar**.
> * `ingest.py` — import con dedupe por `UNIQUE(user_id, hash_dedupe)`, TC MEP congelado por operación, autodetección del archivo subido, `remapear_tickers_base()` y `corregir_movimiento()` (corrige un movimiento mal informado por el broker **recalculando el hash**).
> * `posiciones.py` — costo promedio ponderado, costo USD a TC histórico, capital aportado, TIR por bisección.
> * `ledger.py` — **motor cronológico**: recorre los movimientos por fecha con PPC móvil y emite una operación cerrada por venta (ADR-0005).
> * `kpis.py` — valuación y KPIs en dos planos: tenencia viva y rendimiento total (método del patrimonio).
> * `rendimientos.py` — cauciones apareadas con su TNA ponderada, dividendos netos de retención, cuenta remunerada.
> * `analisis.py` — composición por tipo de renta, sector e industria.
> * `core/market_data/sectores.py` — sector e industria automáticos (override → scoring → Yahoo), con caché en DB, caché negativa y `fetch` inyectable.
> * `tenencias.py`, `view.py`, `export.py` — foto del custodio + tenencias manuales, la pestaña Cartera, export a Excel.
>
> **342 tests, 3 skipped.** El gate `tests/test_cartera_recon.py` reconcilia contra mi Excel y se saltea solo si no está `CARTERA_XLSX`. **Corré la suite antes y después de tocar cualquier cosa.**
>
> ## Trampas del dominio que ya nos costaron caro — no las repitas
>
> Cada punto fue un error real que costó horas.
>
> 1. **Nunca sumes resultado instrumento por instrumento para obtener el total de la cartera.** En una cartera bimonetaria, pasar importes en USD a pesos con el TC de cada fecha hace que la devaluación infle el resultado. Verificado: $9,92M por componentes contra $2,27M por patrimonio. El método correcto es **patrimonio**: `resultado = (tenencia + efectivo) − (depósitos − retiros)`. **Todo agregado nuevo se contrasta contra una identidad contable independiente antes de mostrarse.**
> 2. **El capital invertido no es la suma de las compras.** Eso es capital *rotado*. Es depósitos menos retiros.
> 3. **La amortización devuelve capital + interés.** Sin restarle el costo del capital de esas unidades, las letras dan rendimientos de 100%+.
> 4. **El export de movimientos NO alcanza para reconstruir la cartera.** Los pagarés no traen cantidad y los ajustes de ratio de CEDEAR no generan movimiento. Por eso hay dos fuentes: movimientos = histórico y costos; tenencia del broker = foto actual. Su diferencia **es** la reconciliación.
> 5. **No guardes valores derivados en el momento del import.** `ticker_base` se guardaba al importar; si el import corría sin el mapa de instrumentos, las variantes en dólares quedaban sueltas — y el dedupe impedía que se autocorrigiera. O derivás al leer, o hay una reparación explícita.
> 6. **Cuando un número no cierra, sospechá de la cantidad antes que del precio.** El BTC mostraba US$192 en vez de US$203: la cantidad venía del saldo inicial (0,003) y la real era 0,00316847.
> 7. **Los precios del broker vencen** (hoy 3 días). Sin expiración la cartera queda congelada en la fecha del snapshot.
> 8. **data912 sirve los bonos multiplicados por 100** (AE38: 127.360 contra 1.262,6 del broker).
> 9. **El BCRA no publica MEP** (su serie es el mayorista A3500). La fuente es `argentinadatos`, ADR-0004.
> 10. **Para XIRR usá bisección, no Newton** — con flujos irregulares Newton diverge.
> 11. **Un warning de `fly deploy` que dice "not listening on the expected address" puede ser falso positivo.** Antes de tocar código: `fly status`, `fly releases` y `/_stcore/health`.
> 12. **Un hecho posterior no puede cambiar un resultado anterior.** El realizado se mide con el **PPC vigente al momento de la venta** (ADR-0005), no con el promedio de toda la historia: el ajuste de ratio del SPY —70 unidades gratis fechadas tres meses **después** de una venta— le abarataba el costo a esa venta hacia atrás.
> 13. **El realizado y el costo del remanente van juntos.** Medir uno con el PPC del día y el otro con el promedio global rompe la identidad `costo liberado + costo remanente = total comprado`.
> 14. **Corregir un movimiento ya importado exige recalcular el `hash_dedupe`.** Si solo se arregla el Excel, la fila corregida entra como movimiento nuevo y quedan las dos. Hay tests de las dos rutas.
> 15. **Las tasas se ponderan por capital y tiempo, no se promedian.** Promediar las TNA de 101 cauciones le da el mismo peso a una de $20.000 por un día que a una de $2,7M por cinco.
> 16. **"No tengo el dato" y "no existe el dato" son cosas distintas.** A un bono no le *falta* el sector: no tiene. Filtrá antes de agrupar, o el "Sin dato" se come el 75% del cuadro y no dice nada.
> 17. **Antes de elegir un endpoint, probalo.** El "natural" para traer sectores (`quoteSummary` de Yahoo) exige un *crumb* con cookie y devuelve `Unauthorized`; `v1/finance/search` da sector **e industria** sin autenticación. Y siempre exigí **coincidencia exacta de símbolo**: buscando `URA` (ETF de uranio) Yahoo devuelve también `UROY` (una minera).
> 18. **Toda consulta externa necesita caché negativa.** Si solo se cachea lo que resuelve, un ticker desconocido dispara una búsqueda en cada carga de la pantalla, para siempre.
> 19. **El broker se equivoca.** La compra de ASML del 16/5/2025 vino con **dos ceros de menos** ($60,10 en vez de $6.010). La guarda `Realizacion.sospechosa` (>1.000%) lo detectó sola. Cuando un rendimiento es absurdo, es un dato malo, no un trade.
>
> ## Cómo verificar de verdad
>
> Los bugs que importaron **no los encontraron los tests**: los encontré yo usando la app, o aparecieron al mirar los números reales. Los tests pasaban porque probaban el camino limpio. **Reproducí mi secuencia real de uso**, incluyendo el orden equivocado y datos que ya existen en la base. Si un cálculo cambia, comparalo contra el número de mi Excel o contra un cálculo manual, y **mostrame la tabla antes/después**.
>
> ## Tarea de hoy: Fase 4 — Mejoras del Lugar A (Finanzas Personales)
>
> Ejecutar el backlog de `MEJORAS.md` sobre Finanzas Personales, **incluido lo heredado del `MEJORAS.md` del repo original `Mis-Finanzas-App`** (hay que traerlo y pegarlo en la sección del Lugar A, que hoy está casi vacía).
>
> **Antes de arrancar, proponeme un orden.** Quiero que primero releves qué hay en ese backlog y me lo presentes priorizado, no que empieces a codear el primer ítem de la lista.
>
> **Pendientes sueltos que quedaron anotados:**
>
> * Preguntarle al broker por la fila del **TTM26** del 4/2/2026 (17.395 nominales por $17,78 — el resto de ese día se compró a $1,458). Si el precio correcto fuera ~1,40, ese bono rindió 9,1% y no 13,3%. **No lo toques sin que yo confirme.**
> * **Workflow de CI** que corra la suite en cada push (`.github/workflows/` hoy solo tiene un README).
> * **Amortizaciones parciales** de bonos vivos: quedó fuera de la 3b con motivo. Primera fecha real: **9/7/2027** (AE38). Detalle en `MEJORAS.md`.
> * Retirar `radar-financiero` (`fly apps destroy radar-financiero`).
> * `requirements.lock` para builds reproducibles.
> * Dominio propio (FreeDomain). Es estético, va último.
>
> Confirmame el plan antes de codear y avisame si al leer el código encontrás algo que no cierra. Si algo de lo que te pido choca con una decisión ya tomada en un ADR, decímelo en vez de improvisar.
>
> **Actualizá este prompt cuando la Fase 4 cierre:** la "tarea de hoy" pasa a ser la fase siguiente y las trampas nuevas se suman a la lista.
