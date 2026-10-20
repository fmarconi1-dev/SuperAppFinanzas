# ADR-0010 — Los números de mercado los arma código, no Gemini

**Fecha:** 2026-10-19 · **Estado:** ✅ aceptada (Franco, 19/10/2026) · **Fase:** B (corrección en producción)
**Modifica:** la decisión de la Fase B (`docs/PLAN-FASE-B.md`, "Decisiones", 15/10/2026) de que los dos briefings los genera Gemini y que "si un número no cierra, se ajusta el pedido, no el código".

## Contexto

Desde la Fase B, Gemini genera en una conversación recurrente, con acciones programadas, el briefing matutino y el cierre de las 18:30. Los manda por mail, y `Reenvio.gs` los lleva tal cual al Secretario. Gemini busca las cotizaciones en la web.

El 19/10/2026 los dos informes llegaron con números de otros días:

| Dato | Matutino 19/10 | Cierre 19/10 | Real 19/10 |
|---|---|---|---|
| S&P 500 | 7.744,06 (+0,33%), **cierre del jueves 15/10** | 7.659,44 (−1,09%), **cierre del viernes 16/10** | 7.690,73 (+0,41%) |
| UST 10Y | 4,08% (−1 pb), **no existe en la serie** | 5,08% (sin cambios) | 5,15% (+6 pb, Tesoro) |
| Merval | 2.859.051 (S&P Merval del 15/10) | 2.848.945 (S&P Merval del 16/10) | **MSCI MERVAL 98.214,66 (−1,79%)**: índice nuevo, base 100.000 desde el 19/10 |
| Mayorista | 1.512,50 | 1.439,00 (**inventado**) | 1.524,50 |
| Riesgo país | 622 (dato del 15/10) | 648 (dato del 16/10, sin fecha) | 648, último publicado (16/10) |

El pedido ya le exigía a Gemini "solo datos de hoy" y "nunca inventes". No alcanzó: una búsqueda web encuentra notas de días anteriores y el modelo las presenta como de hoy. **Ajustar el pedido no lo arregla.** Las acciones programadas de Gemini no dejan pasarle datos, así que no hay forma de darle los números para que solo redacte.

## Decisión

1. **Los números los arma `integraciones/google-apps-script/Mercado.gs`**, en el mismo proyecto de Apps Script que el reenvío. **La SuperApp no cambia** (pedido de Franco: no cargar la app). Sigue recibiendo texto en `POST /api/briefing`.
2. **Matutino:** Gemini lo sigue escribiendo, con agenda, tareas y noticias, y deja un renglón `[TABLERO]`. Antes de mandarlo, `Reenvio.gs` pone ahí el tablero de `Mercado.gs`. Si el renglón no está, reemplaza el bloque "TABLERO" de Gemini. A Gemini se le prohíben las cifras de mercado en la síntesis y en las noticias (`docs/PEDIDO-GEMINI.md`).
3. **Cierre:** se da de baja en Gemini. Lo arma entero `Mercado.gs`, con números y una frase por bloque hecha con reglas: subieron/bajaron, la pendiente 2–10 se empinó/aplanó. Sale desde las 18:30, de lunes a viernes, por el mismo disparador de 10 minutos, así que se reintenta solo si la SuperApp no contesta. Si Gemini manda un "Cierre de Mercado" igual, se descarta.
4. **Fuentes, gratis y sin clave:**

   | Dato | Fuente |
   |---|---|
   | S&P, Nasdaq, Dow, Brent, oro | Yahoo |
   | Tasas a 2, 10 y 30 años | Tesoro de EE.UU. (curva oficial). Para el 10 y el 30, Yahoo de respaldo si a esa hora el Tesoro no publicó |
   | MSCI MERVAL | BYMA |
   | Dólares | dolarapi para hoy, argentinadatos para el día hábil anterior |
   | Riesgo país | argentinadatos |
   | Bonos hard dollar, Lecap/Boncap/CER | data912 |

5. **Reglas de los datos:**
   - Cada dato muestra su fecha `[DD/MM]` si no es de hoy.
   - Una fuente que falla se ve como `s/d` y queda en el registro. **Nunca se muestra un número viejo como nuevo.**
   - Las frases describen solo los números mostrados.

## Alternativas descartadas

- **Ajustar el pedido a Gemini:** ya decía lo necesario y falló.
- **Generar los números en la SuperApp (Python):** se podría testear con la suite, pero suma código de mercado a la app. Franco prefirió no cargarla. Además, la Fase B ya había dejado fuera de alcance que la app trajera datos de mercado.
- **Corregir solo el tablero del cierre de Gemini:** sus párrafos estaban escritos sobre los números viejos ("fuerte retroceso, Nasdaq −2,15%"), así que el texto se contradecía.
- **Stooq como respaldo de Yahoo:** el 19/10 ya no respondía.

## Consecuencias

- **Sin tests automáticos:** el Apps Script no corre con la suite. Se probó el 19/10 con QuickJS, simulando `UrlFetchApp` y `Utilities`, contra las fuentes reales: todas contestaron y los números coincidieron con los de arriba. `probarMercado()` repite la prueba desde el editor de Google.
- **Riesgos conocidos:**
  - Yahoo puede rechazar pedidos desde servidores de Google (se vería como `s/d`). El plan B es una planilla con `GOOGLEFINANCE`, todavía no hecha.
  - El CSV del Tesoro tarda unos 20 s.
  - argentinadatos publica el riesgo país con un día de atraso, así que suele salir con `[fecha]`.
  - data912 no trae fecha: se le pone la de la rueda del BYMA.
  - Los feriados no se conocen. Ese día el dato sale con la fecha del último cierre, y el cierre avisa "hoy no hubo rueda".
- `docs/PEDIDO-GEMINI-CIERRE.md` queda retirado; el pedido vigente es `docs/PEDIDO-GEMINI.md`.
