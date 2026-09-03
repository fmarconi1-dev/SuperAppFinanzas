# ADR-0006 — Finanzas Personales pasa de *transaction-first* a *source-first*

**Fecha:** 2026-08-27 · **Estado:** ✅ aceptada (alcance confirmado por Franco el 27/8) · **Fase:** 5 — reemplaza el punto 4 de la Fase 4 (M4)

## Contexto

### El problema, bien planteado

El modo de falla de toda app de finanzas personales es que el usuario deja de cargar y el costo de ponerse al día se vuelve prohibitivo. El diagnóstico habitual —"el usuario se olvida"— es incorrecto, y por eso las soluciones habituales (recordatorios, rachas, hitos) no funcionan: atacan la motivación cuando el problema es **arquitectónico**.

> **La exactitud de la app es función de la disciplina del usuario.** Todo sistema con esa propiedad se degrada.

La curva del atraso no es lineal, porque **la memoria se degrada antes que el volumen**:

| Atraso | Transacciones | De dónde salen |
|---|---:|---|
| 1 día | ~3 | memoria, exactas |
| 3 días | ~10 | memoria borrosa |
| 14 días | ~40 | **del resumen bancario** |

De ahí la observación que ordena todo el diseño:

> **Pasadas ~72 horas, "cargar los gastos" ya es reconstruir desde el resumen.** Si vas a terminar leyendo el resumen igual, el resumen tenía que haber sido la fuente desde el día uno.

### Ya resolvimos esto una vez, en Cartera

Trampa nº4 del proyecto, escrita durante la Fase 3a:

> *"El export de movimientos NO alcanza para reconstruir la cartera. Por eso hay dos fuentes: movimientos = histórico y costos; tenencia del broker = foto actual. **Su diferencia es la reconciliación**."*

La Cartera **nunca depende de que Franco recuerde cargar una operación**: la foto del broker es un ancla que no se olvida. Finanzas Personales no tiene ancla — su verdad es la suma de lo tipeado. Por eso una se degrada y la otra no. Este ADR porta el patrón al Lugar A.

### Los números reales de Franco (27/8/2026)

- **Débito: la mayor parte del gasto.** No tiene resumen mensual propio, pero **cada compra con débito está en los movimientos de la caja de ahorro**.
- **Crédito:** resumen mensual, un archivo, detalle por comercio.
- **Efectivo: 10-15%.** Única porción que ninguna fuente automática captura… salvo por su ancla: **las extracciones figuran en la caja de ahorro**.

Cobertura alcanzable: **~85-90% del gasto con cero actos de memoria**, y el resto con techo conocido.

### Alcance confirmado por Franco (27/8/2026)

- **Cuentas: cuatro.** Caja de ahorro (donde vive el débito), **dos tarjetas de crédito** y efectivo.
- **Formato de exportación: Excel.** Se reusa `parse_archivo_excel` y la maquinaria de parseo de la Cartera; `openpyxl` ya es dependencia.
- **Sin billeteras virtuales.** No usa Mercado Pago ni equivalente → **la clase 5 de duplicados (sub-conteo) no aplica hoy.** Queda como guarda documentada: el día que agregue una, el riesgo vuelve.
- **Sin backfill.** El corte es "de acá en adelante"; nada histórico se toca ni se reclasifica.

Carga mensual resultante: **3 descargas** (dos resúmenes + los movimientos de la cuenta) y revisar los comercios nuevos. Contra ~90 actos de memoria.

## Decisión

### 1. Cuentas y perímetro

Hoy `transacciones` no tiene noción de *dónde* está la plata. Se introduce el concepto de **cuenta** (caja de ahorro, tarjeta, efectivo, billetera virtual) y, con él, el de **perímetro**:

- **Gasto** — la plata sale del perímetro (va a un comercio).
- **Ingreso** — entra al perímetro.
- **Traspaso** — se mueve entre cuentas propias. **No es gasto.**

Es el método del patrimonio de la Cartera aplicado acá: *el gasto real es lo que sale del perímetro, no la suma de los movimientos* (trampas nº1 y nº2).

Modelo mínimo suficiente: una fila por movimiento, con `cuenta_id` y `cuenta_contraparte_id`. Un gasto tiene contraparte nula (afuera); un traspaso tiene las dos. Con eso se obtiene, gratis, el **saldo por cuenta** — que es lo que hace posible la reconciliación del efectivo.

### 2. "Pago tarjeta" NO se elimina: tiene fecha de corte

⚠️ **Esta es la decisión más delicada del ADR.**

Hoy `Pago tarjeta` está mapeado a `Gasto Fijo / Financiero` y **se cuenta como gasto**. Está bien: como los consumos individuales nunca se cargaron, el pago es el único rastro del consumo con crédito de cada mes.

En el momento en que se importe el resumen, contar las dos cosas sería doble conteo. Pero **eliminar el motivo o reclasificarlo hacia atrás destruiría el gasto histórico** de todos los meses ya cerrados y rompería Previsión vs Realidad.

⚠️ **El agujero que tenía la versión con fecha de corte fija.** Un pago de tarjeta corresponde a consumos de ~un mes antes. Con corte el 1/10 y sin backfill, el pago del 10/10 —que cubre los consumos de septiembre— se marcaría traspaso, pero el resumen de septiembre nunca se importó: **el gasto de septiembre entero desaparecería.** Falla hacia abajo y no salta a la vista.

**Regla adoptada — el corte lo decide el dato, no el calendario:**

> Un pago de tarjeta es **traspaso si y solo si el resumen que lo cubre fue importado**. Si no hay resumen que lo respalde, **sigue siendo `Gasto Fijo / Financiero`, como hoy.**

Y el vínculo ya existe: es la reconciliación del Paso 3 (pago ≈ total del resumen, con residuo esperado por cuotas e intereses). **La reconciliación *es* el interruptor.**

Propiedades que la hacen preferible a una fecha fija:
- **Degrada de forma segura.** Si Franco se olvida de importar un resumen, no pierde el gasto: lo pierde el detalle. Nunca desaparece plata.
- **No hay aritmética de fechas a mano**, que es donde se rompen estas cosas.
- **Nada histórico se toca.** Es la trampa nº12 respetada por construcción: *un hecho posterior no puede cambiar un resultado anterior*.
- Se aplica **por tarjeta**, que con dos importa.

### 3. Las tres fuentes

| Fuente | Cubre | Frecuencia | Actos con memoria |
|---|---|---|---:|
| Movimientos de caja de ahorro | débito, transferencias, extracciones, cargas a billetera | 1 archivo | 0 |
| Resumen de tarjeta | crédito, por comercio | 1 archivo/mes | 0 |
| WhatsApp | **solo efectivo**, en el momento | suelto | 0 |

Las tres producen **propuestas**, nunca escrituras. Todo pasa por un preview antes de tocar la base.

### 4. El efectivo tiene ancla

Las extracciones de la caja de ahorro son **entradas** a la cuenta efectivo. Lo que se reporta por WhatsApp son **salidas**. La diferencia es efectivo sin asignar, y se muestra como tal.

Con efectivo al 10-15% del gasto y reportando la mitad, el hueco sin explicar queda en ~6% **y se conoce su magnitud exacta**. No es un dashboard que miente: es uno que declara su margen (trampa nº23).

### 5. Dedupe: las seis clases

Franco pidió explícitamente que el agente reconozca duplicados entre caja de ahorro y tarjeta. No son un problema, son seis, y **cada uno se resuelve distinto**:

| # | Clase | Cómo se resuelve |
|---|---|---|
| 1 | **Reimportar el mismo archivo** o rangos solapados | `hash_dedupe` determinístico + `UNIQUE`, igual que Cartera. Automático. |
| 2 | **Pago de tarjeta vs consumos del resumen** | No es fila-contra-fila: es agregado. Se resuelve por **clasificación** (traspaso), no por matching. |
| 3 | **WhatsApp vs archivo** | Fuzzy: mismo monto, fecha ±N días, descripción compatible. **Se propone, nunca se fusiona solo.** |
| 4 | **Débito que aparece en dos listados del mismo banco** | Verificar contra los archivos reales antes de asumir que no pasa. |
| 5 | **Billetera virtual: la carga y el gasto** | ✅ **No aplica**: Franco no usa billeteras. Queda como guarda si algún día agrega una. |
| 6 | **Cuotas de tarjeta** | Regla explícita: se cuenta la cuota del período, no la compra original. Verificar contra el resumen real. |

⚠️ **La clase 5 era el error espejo y el más peligroso** —falla hacia abajo, que es la dirección que no se nota— pero **no aplica**: Franco confirmó que no usa Mercado Pago ni otra billetera. Se deja escrita como guarda: si algún día agrega una, sus cargas deben seguir contándose como gasto (conservador) hasta que la billetera sea una cuenta importada. La regla general es la misma que la del pago de tarjeta: **un traspaso solo puede marcarse como tal cuando existe la fuente que cubre el otro lado.**

### 6. Reparto determinístico vs LLM

**El LLM nunca decide plata. Decide etiquetas y propuestas.**

| Determinístico (con tests unitarios) | LLM (con tests de archivo-oráculo) |
|---|---|
| hash de identidad y dedupe exacto | extraer estructura de un formato desconocido |
| matching por monto y fecha | mapear comercio nuevo → motivo |
| clasificación de traspasos por regla | emparejar semánticamente ("nafta" ↔ "SHELL AV CABILDO") |
| totales, saldos y reconciliaciones | resumir qué cambió en el preview |

El LLM **ordena candidatos que un filtro determinístico ya produjo**; no los inventa.

## Alternativas consideradas

- **Agregación bancaria directa (Belvo y similares).** Sería lo ideal y **no está disponible en Argentina hoy**: el Decreto 353/2025 creó el Sistema de Finanzas Abiertas con el BCRA como autoridad, pero el BCRA todavía no publicó los estándares técnicos ni cronograma. Belvo cubre Brasil, México y Colombia. **Se diseña como una fuente más, enchufable cuando exista.**
- **Registrar saldos periódicamente como ancla.** Descartado: aporta poco por sí solo y, sobre todo, **es redundante** — importar el resumen ya da el control total sin tarea nueva.
- **Rachas, hitos y gamificación.** Descartado por Franco el 4/8/2026 y confirmado acá con motivo: tratan el problema como de motivación cuando es de arquitectura.
- **Doble partida completa.** Sobra para el objetivo. Una fila con contraparte alcanza para excluir traspasos y obtener saldos por cuenta.

## Consecuencias

**A favor**
- Atrasarse deja de costar datos: los archivos siguen ahí, exactos, cuando se los baje. **El precipicio de ponerse al día desaparece.**
- El trabajo mensual converge a revisar los comercios nuevos (~10 líneas visibles), sin recordar nada.
- La app puede declarar cuánto no sabe, en vez de mentir en silencio.

**En contra / riesgos**
- **Migración sobre la tabla más sensible del repo.** Mitigación: aditiva, y con gate de que ningún número histórico se mueva un peso.
- **El corte de "Pago tarjeta" es semántico**, no técnico: si se aplica mal, se rompen meses cerrados.
- **Sub-conteo por billeteras** (clase 5): falla hacia abajo, que es la dirección que no se nota.
- **Dependencia de formatos de archivo** del banco. Mitigación: extractor por LLM en vez de un parser por entidad, y preview obligatorio.
- El efectivo sigue dependiendo de un acto voluntario. **No se resuelve; se acota y se declara.**

---

# Plan de trabajo propuesto (reemplaza a M4)

Cada paso cierra y es desplegable. **El orden es deliberado: primero el esqueleto con los archivos reales de Franco, y la generalización con LLM al final** — al revés de lo que planteaba M4, que arrancaba por el importador genérico.

### Paso 0 — Cuentas y perímetro (migración M16)
Tabla `cuentas` (caja de ahorro, Tarjeta 1, Tarjeta 2, efectivo); `cuenta_id` / `cuenta_contraparte_id` en `transacciones`; el traspaso reusa el grupo `Flujo Capital`, que **ya existe en el CHECK de la base y que `metrics.py` no cuenta como gasto** — no hay que tocar el motor de métricas. Todo lo existente cae en una cuenta "Histórico".
**Gate: ningún número histórico se mueve un peso.** Test que compara todos los agregados antes y después de migrar.
_~1 día._ Riesgo bajo: sin backfill, la migración es puramente aditiva.

### Paso 1 — Importador de movimientos de caja de ahorro (Excel)
La fuente más grande: débito, transferencias y extracciones. Se reusa el parseo de Excel de la Cartera (`parse_archivo_excel`, `openpyxl`). `hash_dedupe` + `UNIQUE` como en `cartera_movimientos`, y preview obligatorio. Todavía sin LLM.
_~2 días._

### Paso 2 — Clasificador de traspasos y mapa de comercios aprendido
Extracciones y pagos de tarjeta → traspaso, **con la regla de que solo se marcan como tal cuando existe la fuente del otro lado**. Tabla comercio → motivo que aprende de lo que Franco confirma; del mes 3 en adelante el trabajo manual es marginal.
_~1,5 días._ (Sin la guarda de billeteras, que no aplica.)

### Paso 3 — Resúmenes de tarjeta (×2) + la reconciliación que activa el corte
Importador del resumen y el chequeo pago ≈ total del resumen, con residuo esperado por cuotas e intereses. **Esa reconciliación es la que convierte el pago en traspaso**, por tarjeta. Regla explícita de cuotas: se cuenta la del período, no la compra original.
_~2 días._

### Paso 4 — Cuenta efectivo + captura por WhatsApp
Las extracciones fondean la cuenta efectivo; WhatsApp la descarga; el hueco queda explícito y cuantificado. Acá se ejecuta el **API sidecar (el viejo M5)**, que deja de ser un fin en sí mismo y pasa a ser la vía de captura del 10-15% que ninguna fuente automática ve.
_~1 semana (incluye la superficie de seguridad del endpoint público)._

### Paso 5 — Dedupe entre fuentes y panel de reconciliación
El fuzzy matching de la clase 3 (WhatsApp vs archivo), propuesto y nunca automático. Panel mensual: qué está cubierto, qué falta, y de cuánto es el hueco de efectivo sin asignar.
_~1,5 días._

### Paso 6 — Generalización con LLM
Recién acá el extractor genérico: otros bancos, otros formatos, PDF además de Excel. Es el M4 original, ahora como **último** paso y sobre una arquitectura que ya funciona con los archivos reales de Franco.
_~3 días._

**Total estimado: ~2,5 semanas de trabajo efectivo.**

## Preguntas abiertas — RESUELTAS (27/8/2026)

1. ~~¿Billeteras virtuales?~~ **No usa.** La clase 5 no aplica; queda como guarda documentada.
2. ~~¿Qué formatos exporta el home banking?~~ **Excel.** Se reusa el parseo de la Cartera.
3. ~~¿Backfill?~~ **No.** De acá en adelante; nada histórico se toca.
4. ~~¿Cuántas cuentas?~~ **Cuatro:** caja de ahorro, dos tarjetas de crédito, efectivo.
