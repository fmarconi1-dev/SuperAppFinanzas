# ADR-0012 — Lenguaje natural en el Secretario: Gemini traduce, el código decide

**Fecha:** 2026-11-03 · **Estado:** ✅ aceptada (Franco, 3/11/2026) · **Fase:** E (nueva)
**Modifica:** ADR-0009 §8 ("Gemini solo para fotos") y la línea de `CLAUDE.md` que dejaba la capa IA para la Fase 7+ con `ollama`.

## Contexto

El Secretario entiende una gramática fija: `5000 super`, `evento: viernes, 15, dentista`, `1 compras, ok`. Franco pidió el 3/11/2026 que entienda **todo** en lenguaje natural: los gastos, la agenda, las consultas y el ida y vuelta de las propuestas. En la conciliación, además, quiere poder discutir: que un gasto no lo convence, que lo edite, y que le proponga ajustes.

El mismo día pasó el caso que lo motivó: contestó la conciliación como lista (`1. Compras`), y el Secretario rechazó los 21 renglones. Eso se arregló en la gramática (`04cdfa7`), pero muestra el problema de fondo: Franco escribe como habla.

**Medición del 3/11** (`procesar` de hoy, frases típicas):

| Frase | Hoy |
|---|---|
| «ayer gasté 5 lucas en el chino», «pagué 12 mil de luz», «nafta 20k», «borrá lo último», «agendame dentista el viernes a las 15», «el 3 es salidas y el resto ok» | ❌ "No encontré monto y categoría" (falla limpio) |
| «5000 en el chino», «20000 nafta con la visa», «1500 cafe con ana» | ⚠️ propone crear la categoría «En el chino», «Nafta con la visa»… |
| «3 cafes 4500» | ⚠️ lee **$3**, categoría «Cafes 4500» |

O sea: además de lo que falla, hay frases que **parecen** entendidas y no lo están. Un respaldo que solo se active ante un error no las ve.

## Decisión

1. **Gemini traduce, nunca ejecuta.** El modelo recibe el mensaje y devuelve, con un esquema JSON fijo, **la orden en la gramática de siempre** (`ayer 5000 supermercado`, `1 compras, 3 salidas`) o una pregunta para Franco. Esa orden la valida y la ejecuta el **mismo código determinístico** de hoy. La IA no toca la base ni Google (sigue ADR-0006 §6: la IA nunca decide plata).
2. **Todo lo que viene de Gemini se confirma.** El Secretario contesta «Entendí: *ayer $5.000 Supermercado*. ¿Va?» y lo ejecuta solo con un *sí* (se guarda como `pendiente` de tipo `traduccion`, que vence a los 10 min como cualquier otra pregunta). Un `ok`, `cancelar` o `deshacer` traducido **nunca** corre directo. Las consultas que no escriben (`resumen`, `agenda`) corren sin preguntar.
3. **Cuándo entra Gemini** (el parser va primero; si entiende bien, no se llama a nadie):
   - el parser no entendió (hoy: "No encontré monto y categoría", renglones que no se leen);
   - el parser entendió una **categoría nueva** (la señal medida de que leyó mal: «En el chino»);
   - hay una propuesta abierta y el mensaje no es una respuesta que la gramática reconozca: se interpreta **con la propuesta como contexto**, antes de intentar leerlo como gastos (el error del 2/11 fue ese orden).
4. **Conversación sobre la conciliación.** Con la propuesta como contexto, Gemini puede:
   - traducir correcciones a las que ya existen (`N categoría`, `N no`, `N es 12`, `N efectivo`, `N tarjeta`): «el de Basualdo es un service del auto» → `4 auto`;
   - contestar preguntas sobre la propuesta («¿por qué el 9 coincide?») **solo con lo que dice la propuesta**, marcado como respuesta de la IA;
   - proponer un ajuste que hoy no tiene orden (partir una fila en dos categorías, corregir el monto de un gasto cargado). Esas órdenes nuevas se agregan **a la gramática y al código determinístico** primero, con tests; Gemini solo aprende a pedirlas.
5. **Si Gemini no contesta** (`GeminiNoDisponible`), se dice, y Franco recibe el mensaje de error de hoy. Sin clave (`GEMINI_API_KEY`), el Secretario funciona como hoy.
6. **El cliente se inyecta** en `procesar` como `lector_fotos` en `procesar_archivo`: la suite corre sin red, con un traductor falso.

## Lo que decidió Franco (3/11/2026)

1. **Qué se le manda a Google: los renglones de la propuesta, en el plan gratis.** Gemini recibe el mensaje, las categorías y, si hay una propuesta abierta, sus renglones (fecha, monto, tipo de movimiento y nombres de terceros). Es lo mismo que Franco ya aceptó para las fotos, y es lo que hace posible la charla sobre la conciliación. Descartados: mandar solo el mensaje y las categorías (sin charla sobre el extracto) y la API paga (rompe el costo cero).
2. **Confirmar siempre:** todo lo traducido que escriba se ejecuta solo con un *sí* (§2).
3. **Preguntas libres al final** (paso 4 del plan), después de gastos, propuestas y la conciliación.

**Ampliación (Franco, 6/11/2026, paso 3):**

4. **Gemini también ve lo cargado de los últimos 60 días** (fecha, monto, categoría, comentario y número), para poder corregir hablando («los haberes del cema ponelos el 2/11»).
5. **Modo Gemini on/off:** además de entrar solo cuando el parser no entiende, «hola gemini» lo prende para todos los mensajes (con memoria de la charla) hasta «chau gemini» o 30 minutos sin mensajes. Sigue valiendo §2: lo que escribe espera el *sí*.
6. **Corregir lo cargado:** órdenes deterministas `#N fecha DD/MM` y `partir #N monto + monto`, que se deshacen. La fecha contable de los Haberes UCEMA de fin de mes (primer día hábil del mes siguiente) es una regla automática de la conciliación, no de la IA.

## Alternativas descartadas

- **Modelo local (`ollama`, como preveía `docs/HERRAMIENTAS-EVALUADAS.md`):** la máquina de Fly tiene 1 GB (no entra ni un modelo chico con la app), la regla del repo prohíbe cómputo pesado en el servidor, y la PC de Franco no está siempre prendida.
- **Que el LLM llame a las funciones directo (tool use) y escriba:** más flexible, pero rompe "la IA nunca decide plata" y deja sin validar lo que hoy valida el parser.
- **Solo agrandar la gramática a mano:** sirve para los casos medidos, pero Franco pidió que entienda lo que escribe y no aprender más formatos.
- **Otros proveedores gratis:** mismo problema de privacidad que Gemini, y Gemini ya está integrado y aceptado para fotos.

## Consecuencias

- **Latencia:** un mensaje que pasa por Gemini tarda ~1–3 s más. Solo los que el parser no entiende.
- **Límites del plan gratis:** a verificar en la página oficial al implementar (paso 2 del plan), con la fecha, como se hizo para las fotos. Si se agotan, se dice y vale la gramática.
- **Inyección:** los renglones del banco traen texto de terceros (la descripción de una transferencia). Por eso la salida es un esquema cerrado, pasa por el parser y se confirma: lo peor que puede hacer un texto malicioso es proponer una orden que Franco ve antes.
- La memoria del proyecto "Gemini gratis solo para fotos" queda desactualizada al aceptarse esta ADR.
