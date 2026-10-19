# ADR-0009 — Conciliación desde el Secretario: la caja de ahorro manda y los contenedores se desarman

**Fecha:** 2026-10-18 · **Estado:** ✅ aceptada (diseño acordado con Franco el 18/10/2026; texto aprobado el 19/10/2026) · **Fase:** D
**Reemplaza:** ADR-0006 §1 (cuentas y perímetro, M16) y su plan de pasos. **Fusiona:** la Fase D de ADR-0008 (conciliación por lotes) + la Fase 5 (ADR-0006) + "varios gastos en un mensaje" (`MEJORAS.md`).
**Sigue vigente de ADR-0006:** el problema (§Contexto), el principio de degradar de forma segura (§2), las clases de duplicados (§5) y el reparto determinístico vs IA (§6: **la IA nunca decide plata**).

## Contexto

ADR-0006 (27/8/2026) resolvía la captura *source-first* con un modelo de **cuentas y perímetro**: una tabla `cuentas`, `cuenta_id` y `cuenta_contraparte_id` en cada transacción, y los traspasos como `Flujo Capital`. Quedó en pausa con ADR-0008, y entre tanto pasaron tres cosas:

1. **WhatsApp ya es el canal** (Fases A–C en producción). La conciliación tiene que vivir ahí, no en una pantalla.
2. **Franco estudió sus archivos reales** (18/10/2026): el extracto de la caja de Galicia (`.xlsx`) y 9 resúmenes AMEX/VISA (PDF con texto). **Los tres formatos se leen sin IA**, y el pago de cada tarjeta se puede desarmar al centavo en los 9 resúmenes.
3. **El saldo de la app ya es la suma de tres partes** (caja + FIMA + efectivo), y a Franco no le importa de qué cuenta salió un gasto: le importa que **quede registrado una sola vez**.

Con eso, el modelo de cuentas sobra. Agregar `cuenta_id` a `transacciones` es tocar la tabla más sensible del repo (la que reconstruyeron las migraciones del incidente del 17/7) para obtener saldos por cuenta que no se van a mirar. Lo que hace falta es otra cosa: **saber qué fila del banco corresponde a qué gasto**, y que nada se cargue dos veces.

## Decisión

### 1. Mi saldo real = caja de ahorro + FIMA + efectivo

- La app **no registra** los movimientos del FIMA ni las extracciones: son internos y no mueven el total. Está bien así y no cambia.
- No hay tabla de cuentas. **La M16, reservada para eso, queda liberada y no se usa** (para no confundir con lo que proponía ADR-0006). Las tablas nuevas de esta fase van de la M19 en adelante.
- El saldo de la caja lo da el extracto (exacto). El del FIMA y el del efectivo **los declara Franco**; la app calcula el esperado y, si no coincide, **prevalece lo de Franco** y se propone el ajuste (§5).

### 2. La caja de ahorro manda; algunas filas son contenedores que se desarman

Cada fila del extracto se clasifica **por regla** según la primera línea de "Movimiento":

| Fila del banco (primera línea) | Tratamiento |
|---|---|
| COMPRA DEBITO, PAGO DE SERVICIOS, DEB. AUTOM. DE SERV., PAGO CON TRANSFERENCIA, PAGO EN TRANSPORTE, comisiones, IVA, percepciones | Gasto; el comercio se mapea a una categoría (aprendida) |
| HONORARIOS…, TRANSFERENCIAS CASH SUELDOS, INTERES CAPITALIZADO | Ingreso |
| **PAGO TARJETA AMEX / VISA** (puede venir en dos filas el mismo día) | **Se reemplaza por el detalle del resumen que cubre** (§3) |
| Compra venta de dolares (trae `Cotizacion:`) | Compra Divisa, como hoy |
| SUSCRIPCION / RESCATE FIMA | Interno: no se carga; alimenta el FIMA esperado |
| EXTRACCION CAJERO | Interno: no se carga; alimenta el efectivo esperado |
| TRANSF. CTAS PROPIAS, TRANSFERENCIA DE CUENTA PROPIA, INGRESO DE DINERO A CUENTA PROPIA | Primero se empareja con un gasto ya cargado (§4); si no hay, **se pregunta** |
| TRANSFERENCIA DE TERCEROS, CREDITO TRANSFERENCIA… | Casi siempre una devolución de parte de un gasto: se empareja (§4) o **se pregunta** |
| COMP. TITULOS / VAL. | Inversiones, como hoy |
| Tipo desconocido | Se pregunta y **se recuerda la respuesta** |

Las reglas (tipo → tratamiento, comercio → categoría) son **datos**, no código: se aprenden de lo que Franco confirma y quedan en la base.

**Corte:** se concilia **desde los movimientos del 17/10/2026**. Las filas anteriores solo sirven para anclar la cadena de saldos. **Nada histórico se toca.** El ajuste inicial (+$82.758,25 en "Ajuste Reconciliación") ya lo cargó Franco el 18/10/2026.

### 3. El pago de tarjeta se desarma en sus gastos reales

Regla verificada en los 9 resúmenes (todos los pagos coinciden al centavo):

- **Gastos reales** = consumos en pesos + IIBB + IVA RG 4240 (+ intereses o comisiones si aparecen).
- **Diferencia** = lo pagado en la caja − los gastos reales. Es la percepción RG 5617 del 30% que cobró el débito automático (positiva) o que el banco devolvió (negativa). Va a una **línea neutra, "Percepción 30% (se devuelve)"**, que no es gasto ni ingreso. Su acumulado (arranca en cero el 17/10) tiene que volver a cero; si no vuelve, el Secretario avisa.
- **Fecha de todo lo desarmado = fecha del pago en la caja.** Así cuadra el saldo y no cambian meses cerrados (trampa nº12).
- Un pago puede venir en dos filas el mismo día (manual + "D.A. AL VTO"): se suman. El "SU PAGO EN PESOS" del resumen siguiente **confirma** el emparejamiento.
- **Consumos en USD:** "Venta divisa" + el gasto, al mismo precio, el día del pago (como lo hace Franco). El precio es la cotización de una "Compra venta de dolares" de ese día en el extracto; si no hay, el **oficial vendedor** de esa fecha de una fuente pública gratuita (a confirmar al implementarlo; ArgentinaDatos ya es fuente del repo por ADR-0004). Siempre se muestra qué cotización se usó.
- Las cuotas se cargan como vienen en el resumen (la del mes).

**Degrada de forma segura (el principio de ADR-0006 §2, intacto):** un pago se desarma **solo si está el resumen que lo cubre**. Si llega el extracto con el pago y el resumen todavía no, la fila queda **"esperando el resumen"**: no se carga nada y la conciliación la muestra como diferencia conocida. Si llega el resumen antes que el pago, queda guardado hasta que el pago aparezca. Nunca desaparece plata y nunca se cuenta dos veces.

### 4. Emparejar sin duplicar

Antes de proponer algo nuevo por una fila del banco o del resumen, se busca un gasto ya cargado. **Es código determinístico, con tests:**

- **Monto:** hasta $1 de diferencia. Manda el del banco y la corrección se muestra ($25.000,01 → $25.000).
- **Fecha:** queda la de Franco (no mueve gastos de mes); el monto, el del banco. El gasto cargado puede ser de hasta **5 días antes** de la fila del banco o **2 días después**.
- **Uno a uno.** Si hay varios candidatos, gana la fecha más cercana; si hay empate, se pregunta.
- **El emparejamiento se guarda.** Reimportar el mismo archivo no duplica nada: la identidad de una fila de la caja es fecha + monto + saldo parcial, y la de un consumo del resumen, tarjeta + cierre + comprobante + monto.
- **También al revés:** si Franco manda por WhatsApp algo que ya entró por una conciliación, el Secretario pregunta si es el mismo.
- **Sin contraparte a propósito** (no son "sobrantes"): los pares Venta divisa + gasto, y los gastos en efectivo. Para un gasto cargado a mano que no aparece en el banco, Franco dice **efectivo o tarjeta** (por defecto, efectivo); los de los últimos 5 días del extracto esperan al siguiente sin preguntar.
- **Gastos con devoluciones descontadas:** de los gastos cargados con una cuenta (`150000-25000*5`) se guarda **el bruto** además del neto. Así la fila de $150.000 del banco o del resumen se empareja con ese gasto, y las transferencias de $25.000 se reconocen como sus devoluciones, no como ingresos.
- Los gastos con tarjeta de crédito no se mandan por WhatsApp: los trae el resumen.
- **Regla del corte (aprobada por Franco el 19/10/2026):** el ajuste inicial del 18/10 igualó la app con la realidad, y con eso absorbió los gastos cargados antes del corte cuya fila del banco o de la tarjeta todavía no había salido. Cuando una fila **posterior** al corte se empareja con un gasto **cargado antes que el ajuste** (por hora de carga, no por fecha: el ajuste se cargó el 18/10 contra la caja del 16/10, y el fin de semana del medio también quedó absorbido), el lote suma una reversión de esa parte del ajuste: *Ajuste Reconciliación* con `ingresos` del mismo signo que el movimiento del banco, con la fecha de la fila **de la caja** que movió la plata (nunca la del consumo). Así el saldo se mueve con el banco sin contar el gasto dos veces. Ejemplo y detalle en `docs/PLAN-FASE-D.md`.

### 5. Saldos y ajuste

- **Caja:** la cadena de saldos parciales tiene que empalmar con el último extracto importado. Si no empalma, hay un hueco entre archivos y se avisa. Galicia limita cuánto deja bajar, así que conviene importar todos los meses.
- **FIMA:** esperado = último FIMA declarado + suscripciones − rescates. La diferencia con lo declarado va a **Ingreso "Rendimiento FIMA"**.
- **Efectivo:** esperado = último efectivo declarado + extracciones − gastos en efectivo (por su **bruto**: si pagaste $150.000 y te devolvieron $125.000 por transferencia, del bolsillo salieron $150.000). La diferencia va a **"Ajuste Reconciliación"** (Gasto Variable, con previsión que define Franco): un faltante en `pasivos`; un sobrante en `ingresos`, que mueve el saldo sin contar como ingreso ni como gasto del mes (verificado contra `metrics.py` y `budget.py`).
- Se guardan el último FIMA y el último efectivo declarados, con fecha.
- **Total:** después del ajuste, saldo de la app = caja del extracto + FIMA + efectivo declarados (menos lo que esté "esperando el resumen", que se muestra aparte).

### 6. Todo pasa por un lote: propone → confirma → aplica todo o nada → `deshacer`

- Lo que llega de una fuente (extracto, resumen, foto, o un mensaje con varios gastos) arma una **propuesta**. **No se escribe nada hasta el `ok` de Franco.**
- Con el `ok`: **backup antes**, una sola transacción de SQLite, **todo o nada**.
- **`deshacer` revierte el lote entero**, incluidas las correcciones a gastos que ya existían y los emparejamientos. Para eso, cada operación del lote guarda **cómo estaba la fila antes**, no solo qué se insertó.
- Un gasto suelto por WhatsApp sigue escribiéndose directo, como hoy (ADR-0008: es Franco cargando). Lo que es propuesta es todo lo que viene de una fuente.

### 7. WhatsApp: costo cero, sin cambios

- Solo `"type": "text"`, dentro de la ventana de 24 h. **Nunca plantillas.** Recibir archivos y descargarlos de la Graph API es gratis.
- El archivo se descarga **apenas llega** (la URL de Meta vence en minutos) y **se borra después de leerlo**. En la base quedan solo las filas leídas, sin CBU, CVU, CUIT, números de cuenta ni nombres de terceros.

### 8. Fotos: Gemini gratis, solo para extraer filas

- Solo fotos y capturas. Franco aceptó que en el plan gratuito Google puede usar el contenido.
- Gemini devuelve **filas en JSON** y nada más. Emparejamiento, saldos y ajustes son el mismo código determinístico que con los archivos.
- La clave va en `fly secrets`, sin valor por defecto. Si falta, el Secretario dice que no puede leer fotos y pide el archivo. El modelo gratuito vigente se confirma al implementarlo.

## Alternativas consideradas

- **Cuentas y perímetro (ADR-0006 §1).** Descartado: toca `transacciones` para dar saldos por cuenta que no se usan, y el total de tres partes ya es el saldo de la app.
- **Los endpoints de la Fase D original** (`GET /api/transacciones`, `POST /api/conciliar`). Pasan a opcionales: la conciliación es una charla por WhatsApp, no una llamada de API. Se hacen solo si Franco los pide.
- **Un extractor con IA para todos los formatos** (el M4 de ADR-0006). Descartado para Excel y PDF, que se leen exactos por posición. La IA queda solo para fotos.
- **Desarmar con la fecha de cada consumo.** Descartado: mueve gasto a meses ya cerrados y descuadra el saldo de la caja ese mes.
- **Cargar el pago como "Pago tarjeta" mientras falta el resumen.** Descartado: al llegar el resumen habría que borrarlo, y es justo la reclasificación que ADR-0006 §2 evitaba. Queda "esperando el resumen", visible.

## Consecuencias

**A favor**
- Cada gasto queda una sola vez, venga de donde venga, y Franco ve y decide cada caso dudoso.
- `transacciones` **no cambia de esquema**: todo lo nuevo son tablas aparte, colgadas por `transaccion_id`. Exportar, importar y las migraciones viejas no se enteran.
- El saldo de la app pasa a tener un ancla real: el extracto del banco.

**En contra / riesgos**
- **"Venta divisa" cuenta como ingreso del mes** (Ingreso/Desahorro, regla de `categorizer.py` que no cambia). Cada consumo en USD de una tarjeta va a subir "ingresos" en `resumen` y en el Inicio, igual que hoy cuando Franco lo carga a mano.
- **La línea de la percepción es `Flujo Capital`.** `compute_kpis`, `ingresos_vs_gastos_mensual` y `budget.py` ya no la cuentan, pero `gasto_por_categoria` (el gráfico de categorías del Dashboard) sí: hay que excluir ese grupo ahí, verificando antes que hoy no haya filas `Flujo Capital` en producción.
- **Las categorías nuevas se crean con su grupo** ("Percepción 30% (se devuelve)" → Flujo Capital, "Rendimiento FIMA" → Ingreso), al usarlas y por espacio. Hoy `_asegurar_motivo` crea todo motivo nuevo como "Sin categorizar", y eso los haría aparecer como gasto sin categoría en `resumen`.
- **Dependencia del formato de Galicia.** Si cambia, el lector falla con un error claro (no adivina) y los tests sintéticos marcan qué columna se movió.
- **Un pago sin resumen deja el saldo de la app corrido** hasta que llega el resumen. Es a propósito y se muestra.
