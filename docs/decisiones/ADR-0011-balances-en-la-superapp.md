# ADR-0011 — Los balances de la semana: el reloj y el Calendar en el Apps Script, todo lo demás en la SuperApp

**Fecha:** 2026-10-21 · **Estado:** ✅ aceptada (Franco, 21/10/2026) · **Plan:** `docs/PLAN-BALANCES.md`
**Modifica:** ADR-0010 solo para los balances. Allí, los números de mercado los arma `Mercado.gs` "para no cargar la app".

## Contexto

Franco quiere que el Secretario le mande el domingo las empresas que presentan balance esa semana, que le conteste cuáles agendar y que el día del balance le llegue cómo reaccionó el precio (`MEJORAS.md`). El 19/10 quedaron dos decisiones que tironean:
- `MEJORAS.md` dice que el resumen "lo arma la SuperApp".
- La ADR-0010 dice que los números de mercado los arma `Mercado.gs`, para no cargar la app.

Hay cuatro hechos que deciden:
1. **La SuperApp no tiene reloj.** La máquina de Fly se duerme (`auto_stop_machines = true`, `min_machines_running = 0`) y no puede disparar nada a una hora fija.
2. **La elección por WhatsApp solo puede vivir en la SuperApp:** es la que recibe los mensajes y la única que manda.
3. **El Calendar es nativo del Apps Script** y es la fuente de verdad de qué empresas se siguen.
4. **El Apps Script no tiene tests.** Cada cambio es un pegado a mano de Franco.

## Decisión

- **Apps Script:** los disparadores (la lista del domingo y el resumen del día) y la lectura y escritura del Calendar (`Codigo.gs`, con una etiqueta por ticker y fecha para no duplicar).
- **SuperApp:** traer el calendario de Nasdaq y la lista del S&P 500 de Wikipedia, armar la lista, interpretar la respuesta, pedir el agendado, `deshacer`, traer el precio de Yahoo y armar el resumen. Todo en Python, con tests contra fuentes de mentira locales.
- **Nasdaq** es la fuente del calendario (decisión de Franco, 21/10), aunque `api.nasdaq.com` sea la API interna de su página y no una publicada.
- **Por ahora, solo la fecha** (Franco, 21/10): nada de ganancia por acción ni ingresos contra lo esperado.

## Alternativas descartadas

- **Todo en un `Balances.gs`:** respeta la ADR-0010 al pie de la letra, pero no tiene tests. Además parte la lista (en `.gs`) y la respuesta (en Python) en dos lenguajes, y cada ajuste es un pegado de Franco.
- **Un reloj en la SuperApp:** exigiría una máquina siempre prendida (`min_machines_running = 1`), con costo de Fly.

## Consecuencias

- **La SuperApp suma código de mercado**, a pesar de la ADR-0010. El motivo de esa ADR era que Gemini inventaba números, y acá no hay IA: las fechas salen de Nasdaq y los precios de Yahoo, con `s/d` si una fuente no contesta.
- **Sin dependencias ni claves nuevas.**
- **Riesgo:** Nasdaq puede cambiar o cerrar su API interna sin aviso. El respaldo verificado es Alpha Vantage, con clave gratis, pero no trae capitalización.
