# Prompt de inicio — Fase D (conciliación desde el Secretario)

Copiá el bloque de abajo en una sesión nueva, con acceso a la carpeta `SuperAppFinanzas/`.

Estado al escribirlo (18/10/2026): **Fases A, B y C cerradas en producción** (gastos, briefings, agenda y el Inicio de Secretario). La Fase D original (conciliación por lotes) y la Fase 5 (ADR-0006, captura desde las fuentes) **se fusionan** en esta, junto con "varios gastos en un mensaje". El diseño se discutió con Franco y quedó **saldado el 18/10/2026**: las decisiones de abajo no se reabren. Suite: 618 passed, 0 skipped.

---

> Soy Franco. Trabajamos en mi **Secretario** (ADR-0008): Streamlit + SQLite en Fly.io (`superapp-finanzas`), con una API stdlib detrás de nginx que atiende mi WhatsApp (Meta Cloud API, **costo cero sí o sí**). **Trabajamos siempre en la rama `main`**; el push y el deploy los hago yo.
>
> ## Antes de tocar nada, leé en este orden y confirmame que entendiste
>
> 1. `ESTADO.md` — foto actual.
> 2. **Este prompt entero**: es el diseño acordado. Todavía no hay plan escrito.
> 3. `docs/decisiones/ADR-0006-captura-source-first.md` — la idea original. **Ojo:** su §1 (cuentas y perímetro, M16) **queda reemplazado** por el modelo de abajo; siguen valiendo §5 (clases de duplicados) y §6 (la IA nunca decide plata).
> 4. `docs/decisiones/ADR-0008-enfoque-secretario.md` y `docs/WHATSAPP-CANAL.md` — por qué el costo es cero (solo `"type": "text"`, ventana de 24 h, cola de salida).
> 5. `MAPA.md`, y las `BITACORA.md` de `core/api/`, `places/finanzas/core/` y `places/inicio/` (trampas: el 9 de los números argentinos, el hilo trabajador, `totales_mes`).
> 6. `claude.md` y `GUIA-DE-TRABAJO.md` — reglas duras.
>
> ## El objetivo
>
> Le mando al Secretario por WhatsApp el **extracto de la caja de ahorro** (Excel) o el **resumen de una tarjeta** (PDF), o una **foto**. Él lo lee, lo compara con lo cargado, me dice qué falta, qué sobra y qué no coincide, y me pregunta cómo cargarlo. **No escribe nada hasta que confirmo.** Después me pide cuánto tengo en FIMA y en efectivo, y si no coincide **prevalece lo mío** y propone el ajuste. Lo que me importa es que **cada gasto quede registrado una sola vez**, no de qué cuenta salió.
>
> ## Mis archivos (ya estudiados el 18/10/2026)
>
> Están en `data/extractos/` (gitignored, **nunca se commitean**): el extracto de Galicia del 16/6 al 16/10/2026 y 9 resúmenes (AMEX 28/5, 30/7, 27/8 y 1/10; VISA 28/5, 2/7, 30/7, 27/8 y 1/10). **Los tres formatos se leen sin IA.**
>
> - **Extracto Galicia (`.xlsx`, una hoja "Cuentas"):** 5 filas de encabezado; desde la fila 6, columnas Fecha · Movimiento · Débito · Crédito · Saldo Parcial · Comentarios.
>   - Leer **por posición de columna**: los títulos vienen con los acentos rotos.
>   - Montos como texto: `'-200.000,00'` con puntos de miles, pero el saldo viene sin ellos (`'153263,01'`).
>   - **Orden: lo más nuevo primero, también dentro del día.** El saldo de cada fila es el de la fila de abajo más su monto. Verificado en las 406 filas: la cadena no se rompe nunca.
>   - Ese **saldo parcial** sirve para tres cosas: identidad de la fila contra reimportaciones (fecha + monto + saldo), detectar un hueco entre dos archivos (la cadena tiene que empalmar) y saber el saldo del banco en cualquier fecha.
>   - **El tipo de movimiento es la primera línea** de "Movimiento". Las siguientes traen comercio, CUIT, CBU/CVU, etc.
>   - Pedí desde el 18/4 y vino desde el 16/6: **parece que Galicia limita cuánto deja bajar.** Importar todos los meses.
> - **Resúmenes AMEX y VISA de Galicia (PDF con texto, no escaneados):**
>   - Página 1: SALDO ANTERIOR, "SU PAGO EN PESOS/USD", "DEV.IMP. RG 5617", y "DETALLE DEL CONSUMO" con FECHA · REFERENCIA · CUOTA (`03/12`) · COMPROBANTE · PESOS · DÓLARES. Los consumos van agrupados por plástico ("TARJETA nnnn Total Consumos de …"), después IIBB, IVA RG 4240 y "DB.RG 5617 30%". Cierra con "TOTAL A PAGAR".
>   - Cuándo un número es pesos o dólares se decide **por su posición x en la página** (`pdfplumber`). Con el texto solo no alcanza: `AIRBNB … USD 344,00 791072 344,00`.
>   - Las fechas de cierre y vencimiento (anterior, actual y próximo) vienen en una línea, por ejemplo `27-Ago-26 04-Sep-26 01-Oct-26 09-Oct-26 29-Oct-26 11-Nov-26`. Las cuotas vienen con la del mes: se carga lo que trae el resumen.
>   - VISA trae además "Cuotas a vencer" (sirve más adelante para la previsión).
>
> ## Modelo acordado
>
> **Mi saldo real = caja de ahorro + FIMA + efectivo.** Hoy la app no registra los movimientos del FIMA ni las extracciones, y está bien: son movimientos internos. El saldo de la app ya es la suma de las tres partes.
>
> **La caja de ahorro manda.** Algunas filas del banco son **contenedores que se desarman** en sus gastos reales:
>
> | Fila del banco (primera línea) | Tratamiento |
> |---|---|
> | COMPRA DEBITO, PAGO DE SERVICIOS, DEB. AUTOM. DE SERV., PAGO CON TRANSFERENCIA, PAGO EN TRANSPORTE, comisiones, IVA, percepciones | Gasto; el comercio se mapea a mi categoría |
> | HONORARIOS…, TRANSFERENCIAS CASH SUELDOS, INTERES CAPITALIZADO | Ingreso |
> | **PAGO TARJETA AMEX / VISA** (puede venir en **dos filas** el mismo día: pago manual + "D.A. AL VTO") | **Se reemplaza por el detalle del resumen que cubre** |
> | **Compra venta de dolares** (trae `Cotizacion:` en el texto) | Compra Divisa, como hoy. Los consumos en USD de las tarjetas se cargan como **"Venta divisa" + el gasto, al mismo precio**, el día del pago (así lo hago yo) |
> | SUSCRIPCION / RESCATE FIMA | Interno: no se carga. Sirve para calcular el FIMA esperado |
> | EXTRACCION CAJERO | Interno: pasa al efectivo. Sirve para calcular el efectivo esperado |
> | TRANSF. CTAS PROPIAS, TRANSFERENCIA DE CUENTA PROPIA, INGRESO DE DINERO A CUENTA PROPIA | Primero se intenta emparejar con un gasto ya cargado (ver abajo). Si no hay ninguno, **preguntarme qué fue** (a veces es la app de YPF para la nafta). Mercado Pago está vacío: lo que entra ahí lo paso a Galicia |
> | TRANSFERENCIA DE TERCEROS, CREDITO TRANSFERENCIA… | Casi siempre es **una devolución de parte de un gasto**: preguntarme |
> | COMP. TITULOS / VAL. | Inversiones, como hoy |
> | Tipo desconocido | Preguntarme y recordar la respuesta |
>
> **Desarmar un pago de tarjeta (regla verificada en los 9 resúmenes, todos los pagos coinciden al centavo):**
>
> - **Gastos reales del resumen** = consumos en pesos + IIBB + IVA RG 4240 (+ intereses o comisiones si aparecen).
> - **Diferencia** = lo pagado en la caja − los gastos reales. Es la **percepción RG 5617 del 30%** que pagó el débito automático (positiva) o que el banco devolvió (negativa).
>   - Va a una **línea neutra "Percepción 30% (se devuelve)"**, que no es gasto.
>   - El acumulado tiene que volver a cero (VISA da exactamente 0). Si no vuelve a cero, avisarme.
> - **Ejemplos:**
>   - VISA, 13/07: $222.656,32 pagado = $222.656,32 de consumos.
>   - AMEX, 07/08: $6.878,15 (manual) + $233.852,65 (débito automático); los gastos reales eran $6.878,15.
>   - AMEX, 09/10: $258.802,35 = $509.600,76 de gastos − $250.798,41 de percepción devuelta.
> - Cada pago aparece como "SU PAGO EN PESOS" en el resumen siguiente: sirve para confirmar el emparejamiento.
> - **Fecha de los gastos desarmados = fecha del pago en la caja.** Así cuadra el saldo y no cambian meses ya cerrados. Así lo hice siempre a mano. El 9/10/2026 ya están desarmados a mano.
>
> **Dólar del día** para los consumos en USD:
>
> 1. Si ese día hay una "Compra venta de dolares" en el extracto, usar **su cotización**.
> 2. Si no, buscarlo **solo** en una fuente pública gratuita: el oficial vendedor de esa fecha. Confirmar la fuente (DolarApi, ArgentinaDatos o similar) al implementarlo.
>
> Mostrar siempre qué cotización se usó, para que pueda corregirla.
>
> ## Emparejar sin duplicar (lo más importante)
>
> Antes de proponer algo nuevo por una fila del banco o del resumen, buscar un gasto mío ya cargado:
>
> - **Mismo monto, con hasta $1 de diferencia.** Manda el del banco y la corrección se muestra. Ejemplo real: cargué $25.000,01 y el banco dice $25.000.
> - **Fecha:** mi gasto puede ser de hasta 5 días antes de la fila del banco, o de 2 días después. Cubre fines de semana y feriados. Ejemplo real: cargué Auto $50.000 el sábado 10/10 y el banco lo asentó el martes 13/10 como transferencia a cuenta propia.
> - **Uno a uno:** cada gasto se empareja con una sola fila. Si hay varios candidatos, gana la fecha más cercana; si hay empate, preguntarme.
> - **El emparejamiento se guarda.** Reimportar el mismo archivo no duplica nada.
> - **También al revés:** si mando por WhatsApp algo que ya entró por una conciliación, avisarme ("Ya tengo Auto $50.000 del 13/10 que vino del banco, ¿es el mismo?").
> - Mis filas que **no tienen contraparte en el banco a propósito** no son "sobrantes": los pares Venta divisa + gasto, y los gastos en efectivo (lo que mando por WhatsApp y nunca aparece en el banco **es efectivo**).
> - **Gastos con devoluciones descontadas:** a veces mando el gasto ya neto. Ejemplo: Compras $25.000 del 16/10/2026 era `150000-25000*5`; pagué $150.000 y cinco personas me devolvieron $25.000 cada una.
>   - Hoy la cuenta **no se guarda** (`Gasto.cuenta` solo se usa en la respuesta): **hay que guardar el bruto**.
>   - Así, una fila de $150.000 en el banco o en un resumen se empareja con ese gasto, y las cinco transferencias de $25.000 se reconocen como sus devoluciones, no como ingresos.
>   - Ese pago de $150.000 no está en la caja, así que **probablemente aparezca en el próximo resumen de tarjeta**: es el primer caso real para probar.
> - Los gastos con tarjeta de crédito **no los mando por WhatsApp**: los trae el resumen.
>
> ## Saldos y ajuste
>
> - **Caja:** el saldo del extracto es exacto. Si no coincide, falta o sobra un movimiento, y se muestra cuál.
> - **FIMA:** esperado = último FIMA que declaré + suscripciones − rescates del extracto. La diferencia con lo que declaro = **Ingreso "Rendimiento FIMA"**.
> - **Efectivo:** esperado = último efectivo declarado + extracciones − mis gastos de WhatsApp que no aparecieron en el banco. La diferencia = **"Ajuste Reconciliación"**.
> - La categoría **"Ajuste Reconciliación"** es **Gasto Variable** y va a tener una previsión (la defino después).
>   - Un faltante se carga como gasto (`pasivos`).
>   - Un sobrante se carga en `ingresos`, en la misma categoría: mueve el saldo sin sumar como ingreso ni como gasto del mes.
> - Guardar el último FIMA y efectivo declarados (con fecha) para la conciliación siguiente.
> - **Punto de partida, ya parejo (18/10/2026):** caja $153.263,01 (extracto al 16/10), FIMA $485.428,94, efectivo $154.400,00. Total real $793.091,95; la app decía $710.333,70. Ajuste inicial **+$82.758,25** en "Ajuste Reconciliación" (lo cargué a mano). **Se concilia de acá en adelante**, desde los movimientos del banco del 17/10/2026. Nada histórico se toca.
>
> ## Cómo se ve en WhatsApp
>
> - Mando el archivo. El Secretario responde con lo que coincide (cantidad), lo que falta (numerado, con la categoría que propone), lo que sobra y lo que no coincide.
> - Contesto en un solo mensaje, por ejemplo `ok`, o `2 regalo, 3 efectivo, ok`. Los comercios nuevos los pregunta una vez y recuerda la categoría.
> - Recién con mi `ok` se aplica el lote: **backup antes, todo o nada**, y `deshacer` revierte el lote entero.
> - Al final me pide FIMA y efectivo, y propone el ajuste.
> - Mensajes de texto en la ventana de 24 h; **nunca plantillas**.
> - El archivo recibido se borra después de leerlo.
>
> ## Fotos: Gemini, versión gratuita
>
> - Solo para **fotos y capturas de pantalla**. Ya acepté que en el plan gratuito Google puede usar el contenido.
> - Gemini **solo extrae filas** (JSON). El emparejamiento, los saldos y los ajustes son siempre el mismo código determinístico (ADR-0006 §6: **la IA nunca decide plata**).
> - La clave va en `fly secrets`, sin valor por defecto. Si falta, el Secretario dice que no puede leer fotos y pide el archivo.
> - Confirmar el modelo gratuito vigente al implementarlo.
>
> ## Orden de trabajo (un paso a la vez, desplegable, suite en verde)
>
> 1. **ADR-0009** (reemplaza ADR-0006 §1 y fusiona D + 5) y **`docs/PLAN-FASE-D.md`** a partir de este prompt. **Mostrámelo antes de codear.**
> 2. **Varios gastos en un mensaje**, que es el sistema de lotes: propone → confirmo → aplica todo o nada → `deshacer` del lote. Incluye **guardar el bruto** de los gastos con cuenta (ver arriba).
> 3. **Recibir documentos e imágenes por WhatsApp.** `extraer_eventos` hoy solo maneja texto. Descargar el archivo con la Graph API **apenas llega**, porque la URL vence en minutos, y borrarlo después de leerlo.
> 4. **Lector del extracto de Galicia + clasificación por reglas + emparejamiento + saldos por partes**, de punta a punta por WhatsApp.
> 5. **Lector de resúmenes AMEX/VISA + desarmado del pago + percepción neutra + USD con dólar del día.**
> 6. **Fotos con Gemini.**
> 7. Opcional, solo si lo pido: un panel de conciliación en la app, o los endpoints `GET /api/transacciones` y `POST /api/conciliar` de la Fase D original.
>
> ## Reglas que no se rompen
>
> - Nunca commitear `data/`, `*.db`, `*.xlsx` ni `.env`. **Los tests no usan mis archivos**: arman Excel sintéticos con `openpyxl` en el momento, y el lector de PDF se prueba sobre la lista de palabras con posiciones. Si querés un test contra los archivos reales de `data/extractos/`, que se saltee cuando no estén.
> - No copiar a docs, tests ni commits mis datos personales de los archivos: dirección, CUIT, CBU/CVU, números de cuenta, nombres de terceros.
> - `pdfplumber` es una dependencia nueva. **Fijá una versión que no suba Pillow**: Streamlit 1.58 pide `pillow<13`.
> - **Costo cero:** solo `"type": "text"`; el test de plantillas cubre todo archivo nuevo del canal. Gemini en el plan gratuito.
> - `except Exception: return <vacío>` está prohibido. "No contestó" ≠ "no existe".
> - Las tablas `cartera_*` no se borran sin mi OK.
> - Suite con el Python del venv: `.venv\Scripts\python.exe -m pytest -q` (0 skipped en local).
> - Al cerrar cada paso: bitácoras selladas (`python scripts/indexar.py . --sellar <carpeta>`), `EN-HUMANO.md`, `ESTADO.md` y `ROADMAP.md`, commit en `main` y avisarme para el push y el deploy.
