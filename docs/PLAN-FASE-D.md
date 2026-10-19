# Plan — Fase D: conciliación desde el Secretario (ADR-0009)

**Objetivo:** le mandás al Secretario el extracto de la caja (Excel), el resumen de una tarjeta (PDF) o una foto. Él lo compara con lo cargado y te dice qué coincide, qué falta, qué sobra y qué no coincide, y te pregunta cómo cargarlo. **No escribe nada hasta tu `ok`.** Después te pide FIMA y efectivo, y si no coinciden prevalece lo tuyo y propone el ajuste. **Cada gasto queda registrado una sola vez.**

**Lo que ya funciona no se toca:** cargar un gasto suelto por WhatsApp, `resumen`, `deshacer` de un gasto, la agenda, los briefings, el Inicio y las pestañas de Finanzas. `transacciones` no cambia de esquema. **Nada anterior al 17/10/2026 se modifica.**

**Fuera de alcance:** otros bancos o formatos (salvo por foto) · la previsión con "Cuotas a vencer" de VISA (después) · la previsión de "Ajuste Reconciliación" (la definís vos) · el panel de conciliación en la app y los endpoints `GET /api/transacciones` / `POST /api/conciliar` (paso 7, solo si los pedís) · el espacio compartido en el Secretario (`MEJORAS.md`, después de esta fase).

Diseño y porqués: `docs/decisiones/ADR-0009-conciliacion-desde-el-secretario.md`. Este plan es el cómo.

---

## Cómo se ve en WhatsApp

Los comercios y montos de estos ejemplos son inventados.

**Varios gastos en un mensaje (paso 2):**

```
Vos:  super 12.500
      nafta 30000
      cena 60000-15000*3

Sec.: Te cargo 3:
      1. Supermercado  $12.500     hoy
      2. Auto          $30.000     hoy
      3. Salidas       $15.000     hoy  (60000-15000*3)
      ¿Va? Contestá *ok*, o corregí: *2 transportes, ok*

Vos:  ok
Sec.: ✅ Cargados 3 ($57.500). *deshacer* borra los tres.
```

**El extracto (paso 4):**

```
Vos:  [galicia-caja-ahorro-...xlsx]

Sec.: 📄 Caja de ahorro, del 17/10 al 16/11 (48 movimientos).
      La cadena de saldos empalma con el extracto anterior ✔

      ✔ Coinciden 21 con lo que ya cargaste
         (1 con corrección: Auto $50.000,01 → $50.000)
      ↔ Internos 9 (FIMA y cajero): no se cargan

      Faltan (te propongo):
      1. 18/10 COMPRA DEBITO · SUPERMERCADO X  $41.200   → Supermercado
      2. 20/10 PAGO DE SERVICIOS · ELECTRICIDAD $18.900  → Servicios
      3. 22/10 COMPRA DEBITO · COMERCIO NUEVO  $9.800   → ¿categoría?
      4. 25/10 TRANSFERENCIA DE CUENTA PROPIA  $35.000   → ¿qué fue?
      5. 28/10 TRANSFERENCIA DE TERCEROS      +$12.000   → ¿devolución de qué?

      Sobran (los cargaste y no están en el banco):
      6. 19/10 Salidas $8.000  → efectivo
      (Compras $4.500 del 15/11 espera al próximo extracto)

      ⏳ Esperando el resumen: 11/11 PAGO TARJETA AMEX $612.340
         (se desarma cuando me mandes el resumen)

      Contestá *ok* o corregí: *3 regalos, 4 auto, ok*

Vos:  3 compras, 4 auto, 5 salidas, ok

Sec.: ✅ Lote aplicado: 4 movimientos nuevos, 1 corrección.
      Ahora decime cuánto tenés en el FIMA y en efectivo:
      *fima 512.300 efectivo 98.000*

Vos:  fima 512.300 efectivo 98.000

Sec.: FIMA: esperaba $509.880 → +$2.420 de Rendimiento FIMA.
      Efectivo: esperaba $101.500 → faltan $3.500 (Ajuste Reconciliación).
      ¿Los cargo? *ok*
```

**El resumen de tarjeta (paso 5):**

```
Vos:  [RESUMEN_AMEX....pdf]

Sec.: 💳 AMEX, cierre 29/10, vence 11/11.
      Lo pagaste el 11/11 en la caja (2 filas: $6.000 + $756.340 = $762.340) ✔

      Se desarma en (todo con fecha 11/11):
      1–14. 14 consumos en pesos ................... $735.120
      15.   IIBB + IVA RG 4240 ...................... $3.910
      16.   USD 40,00 a $1.415 (compra-venta del 11/11)
            → Venta divisa $56.600 + Viajes $56.600
      17.   Percepción 30% (se devuelve) ............ $23.310
            Acumulado de percepciones: $23.310
      $735.120 + $3.910 + $23.310 = $762.340 ✔

      ¿Va? *ok*
```

**`deshacer`** después de un lote: *"↩️ Deshice el lote del 18/11 (4 movimientos nuevos, 1 corrección). Todo quedó como antes."*

### Cómo se contesta una propuesta

| Escribís | Qué hace |
|---|---|
| `ok` | Aplica el lote tal como está (backup antes, todo o nada) |
| `N categoría` | A la fila N le pone esa categoría (con "¿quisiste decir?" como hoy). Si es un comercio, **lo recuerda** para la próxima |
| `N no` | La fila N no se carga (queda anotada como descartada, no vuelve a aparecer) |
| `N efectivo` · `N tarjeta` | Para un gasto tuyo que no está en el banco: lo pagaste en efectivo, o lo trae el resumen de una tarjeta. Por defecto, `efectivo`. Los gastos de los últimos 5 días del extracto **no se preguntan**: pueden aparecer en el próximo, y esperan solos |
| `N categoría`, si N es un crédito | Lo carga como **devolución** en esa categoría (`pasivos` negativo, la convención de siempre), no como ingreso. Las devoluciones de un gasto con bruto las propone solo el Secretario |
| `cancelar` | Descarta la propuesta entera |

Se puede contestar en un solo mensaje, con varias correcciones separadas por coma y el `ok` al final. Sin `ok`, el Secretario muestra la propuesta corregida y espera.

**Mientras hay una propuesta pendiente:** un mensaje que empieza con un número de fila de la propuesta, o que es `ok` / `cancelar`, va a la propuesta. Cualquier otro mensaje (un gasto, `agenda`) se atiende normal y **no** descarta la propuesta (hoy un gasto pendiente se descarta con cualquier otro mensaje: para un lote de 40 filas eso no sirve). Si llega otro archivo, pregunta si descarta la propuesta anterior. La propuesta vence a las 48 h (pregunta 7).

---

## El caso de los $150.000 (pagados en efectivo) y la regla del corte

**Qué pasó (Franco, 19/10/2026):** el 16/10 cargaste *Compras $25.000* como `150000-25000*5`. Pagaste **$150.000 en efectivo** y cinco personas te transfirieron $25.000 cada una a la caja. Las transferencias entraron el 16/10 (lo vi en el extracto).

**Al punto de partida ya está todo adentro, y no hay nada que corregir:**

| Parte | Movimiento | ¿Dónde está? |
|---|---|---|
| Caja | +$125.000 (las cinco transferencias) | en el saldo del 16/10 ($153.263,01) |
| Efectivo | −$150.000 | en el efectivo que declaraste el 18/10 ($154.400) |
| App | −$25.000 (*Compras*) | cargado el 16/10 |
| **Total** | **−$25.000 real = −$25.000 en la app** ✔ | |

Las transferencias son anteriores al corte (17/10), así que la conciliación ni las mira.

**Lo que enseña para la próxima vez.** Si mañana cargás `cena 150000-25000*5` y lo pagaste en efectivo:

- la app carga **$25.000** de Salidas (lo que gastaste de verdad);
- en el extracto aparecen cinco créditos de $25.000: el Secretario los reconoce como **devoluciones de esa cena** y no los carga como ingresos;
- en el efectivo esperado se descuentan **$150.000** (el bruto, lo que salió de tu bolsillo), no $25.000;
- total: caja +$125.000, efectivo −$150.000 = −$25.000 = la app ✔.

Si en vez de efectivo fue con tarjeta, los $150.000 se emparejan con la línea del resumen (no se cargan de nuevo) y las devoluciones igual. Por eso, para un gasto tuyo que no aparece en el banco, la pregunta es una sola: **¿efectivo o tarjeta?**

### La regla del corte (sigue haciendo falta, para otros gastos)

El ajuste inicial comparó la caja **al 16/10** con la app **al momento de cargarlo, el 18/10**. Un gasto con débito o transferencia que ya estaba cargado en la app pero que el banco asienta **después** del 16/10 (una compra del viernes 16 que el banco pasa el lunes 19, o algo que mandaste el sábado 17 antes de cargar el ajuste) quedó **absorbido por el ajuste**: la app ya lo tenía, la caja todavía no. Cuando aparezca en el extracto:

| Si esa fila del banco… | Saldo de la app | Gastos del mes |
|---|---|---|
| …se empareja con tu gasto y no se carga nada | queda **por encima** de la realidad por ese monto | bien |
| …se carga como gasto nuevo | bien | el gasto cuenta **dos veces** |

**Propuesta:** cuando una fila del banco **posterior** al corte se empareja con un gasto **cargado antes que el ajuste** (se mira la hora de carga, no la fecha del gasto), el lote le resta esa parte al ajuste: *Ajuste Reconciliación* con `ingresos` negativos por el mismo monto, con la fecha de la fila del banco. Así el saldo baja con el banco y el gasto queda una sola vez. El Secretario lo muestra con nombre (*"Supermercado $40.000 del 16/10 ya estaba en el ajuste inicial: se descuenta del ajuste"*). Si lo que llega tarde es un crédito, la corrección va con el signo contrario.

La hora de carga de cada gasto y la del ajuste están en la base: no hace falta que te acuerdes de nada.

---

## Diseño técnico

### Dónde va cada cosa

| Archivo | Qué |
|---|---|
| `places/finanzas/core/lotes.py` (nuevo, puro) | Propuesta → aplicar (backup, `BEGIN IMMEDIATE`, todo o nada) → deshacer. Guarda cada operación con **cómo estaba antes**. Escribe con un insert propio sin `backup_db()` por fila (hoy `insert_transaction` hace un backup por cada fila y no corre en una transacción) |
| `places/finanzas/core/comandos.py` | Varios gastos en un mensaje, respuestas a una propuesta, `deshacer` de un lote, `fima … efectivo …`, guardar el bruto |
| `places/finanzas/core/extracto_galicia.py` (nuevo, puro) | Lee el `.xlsx` por posición de columna: tipo = primera línea, montos con `parse_currency_estricto`, cadena de saldos. Error claro si el formato cambia |
| `places/finanzas/core/resumen_tarjeta.py` (nuevo, puro) | Lee la lista de palabras con posición (`pdfplumber`) y separa pesos y dólares por la x de las columnas. Fechas de cierre/vencimiento, consumos por plástico, IIBB, IVA, percepción, "SU PAGO EN PESOS", total |
| `places/finanzas/core/emparejar.py` (nuevo, puro) | Clasificación por reglas, emparejamiento (±$1, −5/+2 días, uno a uno, empate → pregunta), devoluciones contra el bruto, regla del corte |
| `places/finanzas/core/conciliacion.py` (nuevo) | Arma la propuesta y el texto del mensaje; saldos esperados de FIMA y efectivo; desarmado del pago; dólar del día |
| `core/api/whatsapp_meta.py` | `extraer_eventos` reconoce `document` e `image` (id del archivo, tipo, nombre, texto al pie); `descargar_archivo` (Graph API: pedir la URL con el id y bajarla con el token) |
| `core/api/servidor.py` | El hilo trabajador baja el archivo **primero**, lo pasa a `procesar` y **lo borra al terminar** (`finally`) |
| `core/api/gemini.py` (nuevo, paso 6) | Cliente de Gemini que solo devuelve filas en JSON. Se inyecta desde `api.py`, como la agenda |
| `core/api/cotizaciones.py` (nuevo, paso 5) | Oficial vendedor de una fecha, de una fuente pública gratuita. "No contestó" ≠ "no existe": excepción propia |
| `places/finanzas/core/metrics.py` | `gasto_por_categoria` deja afuera `Flujo Capital` (la percepción). Antes se verifica que hoy no haya filas de ese grupo en producción |

`core/` sigue sin importar `places/`: la lógica llega inyectada en `procesar`, como hoy.

### Tablas nuevas (solo `CREATE TABLE IF NOT EXISTS`, todas con `workspace_id`)

| Migración (paso) | Tablas | Para qué |
|---|---|---|
| M19 (2) | `lotes`, `lote_operaciones` | La propuesta, su estado (propuesta → aplicado → deshecho) y cada operación con su "antes", para deshacer el lote entero |
| M20 (2) | `gasto_cuentas` | `transaccion_id` (FK, `ON DELETE CASCADE`), la cuenta tal como la escribiste y el bruto |
| M21 (4) | `banco_filas`, `emparejamientos`, `reglas_tipo`, `reglas_comercio` | Filas de la caja (`UNIQUE` fecha + monto + saldo), con qué gasto se emparejó cada una (uno a uno; una devolución puede ir a un gasto que ya tiene pareja), y lo aprendido |
| M22 (4) | `saldos_declarados` | Último FIMA y efectivo que declaraste, con fecha |
| M23 (5) | `resumenes`, `resumen_lineas` | Resúmenes (`UNIQUE` tarjeta + cierre) y sus líneas (`UNIQUE` resumen + comprobante + monto) |

- Toda FK a `transacciones(id)` lleva `ON DELETE` (con `foreign_keys = ON`, sin eso borrar un gasto desde la app fallaría).
- **La M16 queda sin usar** (ADR-0009). Ninguna de estas migraciones hace `UPDATE` ni `DELETE` de filas; si alguna lo necesitara, va detrás de `_NIVEL_REPARACIONES`.
- En `banco_filas` y `resumen_lineas` se guarda el tipo de movimiento y el comercio, **nunca** CBU, CVU, CUIT, números de cuenta ni nombres de terceros.
- Las categorías nuevas ("Percepción 30% (se devuelve)" → Flujo Capital, "Rendimiento FIMA" → Ingreso) se crean **con su grupo** al usarlas, por espacio. No van en una migración de datos, y no pasan por `_asegurar_motivo`, que las crearía como "Sin categorizar".

### El bruto de un gasto con cuenta

| Escribís | Se carga (neto) | Bruto (lo que muestra el banco o la tarjeta) |
|---|---|---|
| `150000-25000*5` | $25.000 | $150.000 |
| `100-50` | $50 | $100 |
| `12.000/3` | $4.000 | $12.000 |
| `3x2.500` | $7.500 | $7.500 (sin devoluciones) |
| `2500+1500` | $4.000 | $4.000 |

Regla propuesta: el bruto es **el primer término de la cuenta** (lo que está antes del primer −), y si ese término es una división, su dividendo (pregunta 3). Un gasto en efectivo descuenta su **bruto** del efectivo esperado. **Los gastos cargados antes del paso 2** (como el de los $150.000 del 16/10) no tienen el bruto guardado, pero el texto del mensaje sí está en `whatsapp_mensajes`: al emparejar, el bruto se recupera **leyendo de nuevo ese texto**, sin migración que reescriba filas. Ojo: si el gasto pasó por "¿quisiste decir?", la transacción queda colgada del mensaje del "sí", y el texto con la cuenta está en el mensaje anterior. Se verifica en el paso 4; si no se puede recuperar, el Secretario pregunta.

Si el bruto es mayor que el neto, el gasto **espera devoluciones** por la diferencia: créditos de terceros de hasta 30 días después que sumen como mucho esa diferencia.

### Puntos de partida

- **Caja:** el primer extracto ancla la cadena con el saldo del 16/10 ($153.263,01, verificado en el archivo). Las filas hasta el 16/10 solo sirven para eso.
- **FIMA y efectivo:** los declarás vos por WhatsApp (`fima 485.428,94 efectivo 154.400`, con fecha 18/10) la primera vez, o el Secretario te los pide en la primera conciliación. **No van escritos en una migración ni en el código.**
- **Acumulado de percepciones:** pregunta 5.

---

## Orden de trabajo (un paso a la vez, desplegable, suite en verde)

1. ✅ **ADR-0009 y este plan** (18/10/2026), aprobados por Franco el 19/10/2026.
2. **Varios gastos en un mensaje = el sistema de lotes.** Varios renglones → propuesta numerada → `ok` / correcciones → aplica todo o nada → `deshacer` del lote. Guarda el bruto de todo gasto con cuenta, suelto o en lote. `deshacer` deshace **lo último**: el lote entero si lo último fue un lote, el gasto si fue un gasto.
   *Listo cuando:* mandás tres gastos en un mensaje, los confirmás, `resumen` los muestra, y `deshacer` borra los tres.
3. **Recibir documentos e imágenes.** Bajar el archivo apenas llega, chequear tipo (por el contenido, no solo por el nombre) y tamaño (hasta 10 MB), y borrarlo después de leerlo. En este paso todavía no los lee: contesta *"Recibí el extracto (xlsx). Todavía no sé leerlo"*.
   *Listo cuando:* mandás un `.xlsx`, un PDF y una foto, y los tres se reconocen, se bajan y no queda nada en disco.
4. **Extracto de Galicia de punta a punta:** lector + clasificación por reglas + emparejamiento (incluida la regla del corte) + comercios aprendidos + saldos de FIMA y efectivo + ajuste. También al revés: un gasto por WhatsApp que ya vino del banco se pregunta.
   *Listo cuando:* con tu extracto real de noviembre, la propuesta tiene sentido, la aplicás, y el saldo de la app = caja + FIMA + efectivo (+ lo que espera resumen).
5. **Resúmenes AMEX/VISA:** lector + desarmado del pago (fecha del pago) + percepción neutra con su acumulado + USD con el dólar del día + `pdfplumber` fijado sin subir Pillow (hoy 12.3.0; Streamlit 1.58 pide `pillow<13`) + el gráfico de categorías sin `Flujo Capital`.
   *Listo cuando:* el próximo resumen desarma el pago al centavo.
6. **Fotos con Gemini** (modelo gratuito vigente, confirmado al implementarlo). Sin la clave, el Secretario pide el archivo.
7. *Opcional, solo si lo pedís:* panel de conciliación en la app o los endpoints de la Fase D original.

Al cerrar cada paso: bitácoras selladas, `EN-HUMANO.md`, `ESTADO.md`, `ROADMAP.md`, commit en `main`, y te aviso para el push y el deploy.

## Tests (gate: suite completa en verde, 0 skipped en local)

- **Nunca con tus archivos en el repo.** El extracto se prueba con Excel sintéticos armados con `openpyxl` en el momento (encabezados con acentos rotos, montos como texto, más nuevo primero también dentro del día). El resumen se prueba sobre **listas de palabras con posición** (el caso `AIRBNB … USD 344,00 791072 344,00`).
- **Contra tus archivos reales**, en `data/extractos/` y salteados si no están: la cadena de saldos no se rompe en las 406 filas; los 9 resúmenes se leen; los tres pagos de ejemplo cierran al centavo (VISA 13/07; AMEX 07/08 en dos filas; AMEX 09/10 con la percepción devuelta). Los tests no copian datos personales a sus mensajes.
- **Lotes:** todo o nada (una falla a mitad no deja nada escrito), un solo backup, `deshacer` restaura también las correcciones y los emparejamientos, reimportar no duplica.
- **Emparejamiento:** ±$1, ventana −5/+2 días, uno a uno, empate → pregunta, devoluciones contra el bruto, el efectivo esperado con el bruto (el caso de los $150.000, con montos sintéticos) y la regla del corte.
- **Números:** la percepción no aparece en `resumen` ni en el Inicio, en Previsión vs Realidad ni en el gráfico de categorías; un sobrante del ajuste no cuenta como ingreso ni como gasto; **ningún total anterior al 17/10 se mueve un peso** (huella antes/después).
- **Costo cero:** el test que prohíbe plantillas pasa a mirar **todos** los archivos de `core/api/` y los módulos nuevos (hoy recorre una lista fija).
- Sin `except Exception: return <vacío>`: un Gemini, una cotización o una descarga que falla se nombra con su excepción y te llega el motivo.

## Preguntas para vos

**Todas contestadas por Franco el 19/10/2026:**

1. ✅ **La fecha al emparejar:** queda **la tuya**; el monto, el del banco.
2. ✅ **Un gasto tuyo que no está en el banco** es `efectivo` o `tarjeta`, nada más. Lo que propuse como `todavía` pasa a ser automático: los gastos de los últimos 5 días del extracto no se preguntan y esperan al próximo.
5. ✅ **Acumulado de percepciones:** arranca en **cero** el 17/10.
7. ✅ **Una propuesta dura 48 h.**
- ✅ **Los $150.000 del 16/10 fueron en efectivo**, no con tarjeta: no hay nada que esperar ni corregir (ver arriba).

3. ✅ **El bruto:** la regla de la tabla de arriba.
4. ✅ **Los gastos cargados desde la app** cuentan igual que los de WhatsApp para el efectivo esperado.
6. ✅ **El FIMA y el efectivo del 18/10** ya incluyen lo que se movió en el banco el 17 y el 18: el esperado cuenta desde el día siguiente a cada declaración.
8. ✅ **La regla del corte**, de acuerdo.
