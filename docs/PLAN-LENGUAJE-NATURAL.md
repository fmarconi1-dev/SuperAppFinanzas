# Plan — Fase E: lenguaje natural en el Secretario (ADR-0012)

> Estado: 🟡 **propuesto el 3/11/2026.** Franco tomó las tres decisiones (ADR-0012): renglones de la propuesta en el plan gratis, confirmar siempre, preguntas libres al final. Falta su OK para arrancar el paso 1.

Una fase a la vez: el alcance es "todo", pero sale en pasos, cada uno desplegable y probado por Franco antes del siguiente. El orden va por dolor: primero lo que le pasó el 2/11.

## Paso 1 — El traductor, con tests y sin red ✅ (3/11/2026, sin desplegar)

> Hecho como dice abajo, con dos ajustes: el disparador de "propuesta abierta" no es aparte (un mensaje que no contesta la propuesta cae en el parser, que falla y consulta con la propuesta en el contexto), y un gasto traducido tiene que traer coma (`5000, compras`), para que `9 salidas` nunca sea un gasto de $9. Varios renglones con categoría nueva no consultan: la propuesta ya los marca y espera el `ok`. Una traducción que armaría otra propuesta (varios gastos, saldos) con una abierta se rechaza: no tira la conciliación. **Viene apagado:** `api._traductor` lo prende solo con `LENGUAJE_NATURAL=1`; el paso 2 termina prendiéndolo en Fly.

- `core/api/gemini.py`: `ClienteGemini.traducir(mensaje, contexto) -> Traduccion`, con esquema JSON cerrado:
  `{"tipo": "orden" | "pregunta" | "respuesta" | "no_entiendo", "orden": str, "explicacion": str}`.
  `orden` está en la gramática de `ayuda`; `pregunta` es lo que el Secretario le repregunta a Franco; `respuesta` contesta una duda sobre la propuesta.
- `places/finanzas/core/lenguaje.py` (nuevo, puro): arma el contexto (fecha de hoy en Buenos Aires, la gramática, las categorías existentes, la propuesta abierta con sus renglones) y valida la traducción contra el parser antes de ofrecerla.
- `comandos.procesar(..., traductor=None)`: los tres disparadores de la ADR §3, y el `pendiente` de tipo `traduccion` («Entendí: … ¿Va?» → *sí* ejecuta la orden con el mismo `procesar`).
- Tests con un traductor falso: cada disparador; que nada se escriba sin el *sí*; que un `ok`/`deshacer` traducido pida confirmación; que una traducción absurda la rechace el parser; que `GeminiNoDisponible` llegue a Franco; sin traductor, todo igual que hoy.

## Paso 2 — Gastos y respuestas a propuestas, de verdad ✅ (4/11/2026: cero MAL en la cuarta corrida)

> `scripts/probar_lenguaje.py`: 46 frases (las reales del 2/11, *va*, los saldos con *caja*, jerga, listas, correcciones por nombre) por el mismo `procesar`, con Gemini de verdad, sobre una base temporal con las categorías de Franco y un extracto como el del 2/11. Nota por frase: BIEN / DUDOSA / MAL; la meta es **cero MAL**. El evaluador tiene tests (`tests/test_probar_lenguaje.py`). Límites verificados en AI Studio el 4/11: 15 RPM, 250K TPM, 500 RPD. *va* pasó a ser un *sí* en la gramática (sin IA).

> **Corrida en Fly del 4/11/2026** (con la clave nueva: la anterior era de un proyecto con facturación prepaga y crédito agotado, error 402): 34 BIEN · 6 DUDOSA · 5 MAL · 1 FALLA. Los MAL: 4 veces Gemini agregó un `ok` que Franco no dijo (con el *sí* se aplicaba la conciliación entera) → `lenguaje._sin_ok_no_pedido` lo saca salvo que el mensaje traiga una palabra de aceptación; y los saldos con *caja*, que el bot descartaba igual (era el evaluador). Las DUDOSA eran de categorías → `lenguaje.PISTAS` (Franco: lo del auto en Auto, farmacia en Compras, comisiones del banco en Impuestos). La FALLA fue un 402 suelto a mitad de la corrida: revisar que el proyecto de la clave nueva no tenga facturación. Falta la segunda corrida.

> **Segunda corrida en Fly (4/11/2026):** 44 BIEN · 1 DUDOSA · 1 MAL · 0 FALLA. El MAL: «el profe es salidas, el mecánico auto y el resto como dijiste, dale» → Gemini les inventó categoría a los renglones que Franco no nombró. Arreglado en código: `lenguaje._solo_lo_nombrado` deja solo las correcciones a renglones que el mensaje nombra (por número, por una palabra del comercio o la persona, por el monto o por la fecha). La DUDOSA («nafta 20k» → repreguntó el monto) no carga nada mal. Falta la tercera corrida para prenderlo.

> **Tercera corrida en Fly (4/11/2026):** 43 BIEN · 2 DUDOSA · 1 MAL · 0 FALLA. La protección de los renglones no nombrados funcionó (Gemini volvió a inventar categorías y el bot mostró solo «3 Salidas, 4 Auto, ok»). El MAL nuevo: «compré dólares por 1.200.000» → «+1200000, Compra Divisa» (en la corrida anterior había salido bien: Gemini no contesta siempre igual). Arreglado en código: `lenguaje._signo_cruzado` descarta un ingreso en una categoría que no es de ingresos o un gasto en una que sí (salvo Inversiones). Falta la cuarta corrida.

> **Cuarta corrida en Fly (4/11/2026): 44 BIEN · 2 DUDOSA · 0 MAL · 0 FALLA. Meta cumplida.** Una de las DUDOSA era un error del control del signo (leía la corrección «5 Haberes UCEMA, …» como un gasto de $5 y la descartaba): arreglado, el control se aplica solo a gastos. La otra («nafta 20k» → repregunta el monto) no carga nada. Con este arreglo desplegado se prende `LENGUAJE_NATURAL=1` y Franco lo prueba desde el celular.

- La `GEMINI_API_KEY` ya está en Fly (Franco, 3/11/2026; la misma de las fotos).
- Verificar en la página oficial los límites del plan gratis de `gemini-3.5-flash-lite` para texto (anotar la fecha en `gemini.py`).
- Un set de ~50 frases reales de Franco (las del 2/11, jerga: "lucas", "k", "mil"; listas; correcciones) en `scripts/probar_lenguaje.py`, que corre contra Gemini **a mano**, no en la suite. Meta antes de desplegar: ninguna traducción que cargue algo distinto de lo que Franco quiso (las dudosas tienen que salir como pregunta).
- Deploy y prueba de Franco desde el celular.

## Paso 3 — La charla sobre la conciliación

- Con la propuesta como contexto: «el de Basualdo es un service», «¿por qué el 9 coincide?», «ese de nafta ya lo había cargado yo».
- Órdenes nuevas, primero en el código determinístico y con tests, después en el traductor:
  - `N mitad compras mitad salidas` / `N 30000 compras, resto salidas`: partir una fila en dos categorías;
  - corregir el monto o la fecha de un gasto ya cargado que el banco muestra distinto;
  - las que salgan de la prueba del paso 2.
- Memoria corta: los últimos mensajes del ida y vuelta van en el contexto (si `whatsapp_mensajes` no guarda la respuesta del Secretario, una migración la agrega).

## Paso 4 — Agenda, saldos, balances y el resto

- `evento:`/`tarea:` en lenguaje natural («agendame dentista el viernes a las 15»), `fima … efectivo …`, la lista de balances, `deshacer`.
- Preguntas libres (`¿cuánto gasté en súper?`): Franco las dejó para este paso (3/11).

## Fuera de alcance

- Que la IA escriba en la base o en Google sin pasar por el parser y el *sí*.
- Un modelo local (ADR-0012, alternativas).
- Mensajes de voz.
