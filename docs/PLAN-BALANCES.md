# Plan — Balances de la semana por WhatsApp

**Estado:** ✅ paso 1 aprobado (21/10/2026) · ✅ paso 2 en producción (21/10) · ✅ paso 3 en producción (21/10) · ✅ paso 4 desplegado (21/10; primera corrida real el 27/10).
**Lo decidido antes:** `MEJORAS.md`, entrada "Balances de la semana por WhatsApp" (universo, lista, formato, cuándo llega).
**Decisión de arquitectura:** ADR-0011. **Relacionado:** ADR-0008 (canal, costo cero), ADR-0010 (números de mercado por código), `docs/WHATSAPP-CANAL.md`.

## Decisiones de Franco (21/10/2026)

1. **División:** el Apps Script pone el reloj y el Calendar; la SuperApp hace todo lo demás (§1).
2. **Nasdaq** es la fuente del calendario, aunque sea la API interna de su página.
3. **Umbrales:** "neutra" si se movió menos de ±1%.
4. **La lista que llega tarde:** lo que ya pasó no se agenda.
5. **Sin ganancia ni ingresos por ahora:** el Secretario trae solo **la fecha del balance** (y si es antes de la apertura o después del cierre). **Confirmado por Franco el 21/10:** el resumen del día queda con **la reacción del precio** ("MSFT: posmercado positiva") y sin "contra lo esperado". Se cae la búsqueda de una fuente de ingresos (Finnhub) y la medición de a qué hora publica Nasdaq la ganancia del día.
6. **El resumen de la mañana tiene un disparador propio**, que no depende de que llegue el matutino de Gemini.

---

## 1. Dónde vive cada parte

**Lo que fija la respuesta:**
- **La SuperApp no tiene reloj.** `fly.toml` tiene `auto_stop_machines = true` y `min_machines_running = 0`: la máquina se duerme. Todo disparo es un disparador de tiempo del Apps Script que le hace un POST a la app, y el POST la despierta.
- **La elección y los mensajes** solo pueden vivir en la SuperApp (`encolar_saliente`, costo cero).
- **El Calendar** es nativo del Apps Script y es la fuente de verdad del resumen.
- **Solo el Python se testea** con la suite.

| Parte | Dónde |
|---|---|
| Reloj del domingo | Apps Script: `balancesPendientes_`, colgado del disparador de cada 10 minutos de `Reenvio.gs` (como el cierre). El domingo desde las 20:00, si la semana todavía no salió → `POST /api/balances` con `id` por semana |
| Calendario (Nasdaq) + lista del S&P 500 (Wikipedia) | SuperApp: `core/api/balances_fuentes.py` (red) y `places/finanzas/core/balances.py` (puro) |
| Elección (`1 3 7`, tickers, `todas`, `ninguna`) | SuperApp |
| Agendado y `deshacer` | La SuperApp decide; `Codigo.gs` escribe en el Calendar (acciones nuevas) |
| Resumen del día | Un disparador propio del Apps Script lee los 📊 del día en el Calendar y se los pasa a la SuperApp, que trae el precio de Yahoo y arma el mensaje |

---

## 2. Fuentes (verificadas el 20/10/2026, desde la PC de Franco)

| Qué | Fuente | Resultado |
|---|---|---|
| Calendario, con antes o después de la apertura | Nasdaq `api.nasdaq.com/api/calendar/earnings?date=AAAA-MM-DD`, sin clave, con User-Agent de navegador | ✅ Trae `time` (`time-pre-market` / `time-after-hours` / `time-not-supplied`), `marketCap`, nombre. 21/10: 91 empresas; 29/10: 331; 5/11: 569. **Una vez que la fecha pasa, pierde el antes/después**: por eso queda guardado en el evento |
| ¿La fecha es estimada? | Nasdaq `api/analyst/{TICKER}/earnings-date` | 🟡 Lo dice en prosa: "is **estimated** to report… derived from an **algorithm**" contra "is **expected\*** to report". Frágil. Se consulta **al agendar**, solo para las elegidas (nginx corta `/api/` a los 30 s: no da para consultarlas todas el domingo) |
| SPCX | Nasdaq | ✅ Space Exploration Technologies Corp. (Nasdaq-GS), no el ETF de SPACs |
| PAM | Nasdaq | ✅ Pampa Energía |
| Lista del S&P 500 | Wikipedia (`action=parse`) | ✅ 503 tickers. Se normaliza `BRK.B` / `BRK-B` / `BRK/B`. Se refresca una vez por mes y se guarda en la base |
| Posmercado y rueda | Yahoo `chart` con `includePrePost=true` | ✅ desde la PC, con `currentTradingPeriod` (`pre`, `regular`, `post`). ⏳ **Desde Fly, sin probar** (antes del paso 4) |
| Respaldo del calendario | Alpha Vantage `EARNINGS_CALENDAR` | ✅ con `demo`. No se usa por ahora: sin capitalización ni marca de estimada |

---

## 3. Pasos

### Paso 2 — La lista del domingo y la respuesta (sin agendar)

- **Disparo:** `balancesPendientes_` en `Reenvio.gs`. El domingo desde las 20:00, si `ULTIMO_BALANCES` no es la semana que viene → `POST /api/balances` `{"accion": "semana", "lunes": "AAAA-MM-DD", "id": "balances-AAAA-MM-DD"}` con el mismo Bearer de los briefings. Si la SuperApp no lo toma, reintenta a los 10 minutos.
- **La SuperApp:** trae el calendario de lunes a viernes (5 pedidos) y la lista del S&P si tiene más de 30 días, arma la lista, la guarda y la encola (`tipo='balances'`, `id_origen` = el `id`). Un `id` repetido no rearma nada. Si Nasdaq no contesta: `503 calendario_no_disponible` y el Apps Script reintenta.
- **El mensaje:**
  ```
  📊 Balances de la semana (26/10 al 30/10)

  Tu lista:
  1. KO — mar 27/10, pre-apertura
  2. MSFT — mié 28/10, post-cierre
  …
  S&P 500, las más grandes:
  9. AMZN — jue 29/10, post-cierre
  …
  ¿Cuáles agendo? Contestá con los números (*1 3 7*), los tickers (*KO MSFT*), *todas* (las de este mensaje) o *ninguna*.
  *balances todas* muestra las otras 140 del S&P 500.
  ```
  - "Tu lista" es la de `MEJORAS.md` (las 23 + las 20 sumadas como termómetros), con las argentinas adentro.
  - "Las más grandes": las 15 del S&P 500 con más capitalización que presentan esa semana, fuera de las de tu lista.
  - `sin hora` cuando Nasdaq no dice antes o después.
- **`balances todas`:** las demás del S&P de esa semana, por capitalización, con la numeración que sigue. **`balances`** a secas rearma la semana actual (o la próxima, un sábado o domingo).
- **La respuesta:** un intérprete propio. `_leer_respuesta_lote` no sirve: lee `1 3 7` como "renglón 1, categoría «3 7»". Acepta:
  - números de la lista;
  - tickers de la lista;
  - `todas` y `ninguna`.
  Un número solo (`1500`) sigue siendo un gasto, porque un gasto necesita una categoría con letras. Se mira **antes** que la propuesta de un lote, y no la toca.
- **Estado propio** (tabla `balances_propuestas`, M23), no un lote: `lotes.proponer` descartaría en silencio un extracto pendiente. Una propuesta nueva reemplaza a la anterior de balances. Vence el viernes de esa semana.
- **Lo que ya pasó no se agenda:** si elegís algo de un día anterior a hoy, se avisa y no se toma.
- **Sin agendar todavía:** la respuesta dice qué quedó elegido y que el agendado llega en el paso 3.

### Paso 3 — Agendado en Google Calendar y `deshacer`

- **`Codigo.gs`, acciones nuevas:**
  - `agendar_balances`: eventos de día entero `📊 MSFT balance (post-cierre)`, con `estimada` en el título si corresponde, y **`setTag("balance", "MSFT:2026-10-28")`**. Antes de crear busca un evento de ese día con la misma etiqueta: si está, lo devuelve. Esa es la clave estable.
  - `borrar_balances`: recibe las claves.
  - `listar_balances`: recibe un rango y devuelve las claves y el momento.
- **La fecha estimada** se consulta a Nasdaq al agendar, solo para las elegidas (`fecha_anunciada`). La ficha también trae el momento cuando el calendario no lo dice (MCD, 21/10), y si dice otra fecha, gana la ficha.
- **Si Google no contesta, no se anota nada:** Franco manda lo mismo de nuevo y el Calendar no duplica.
- **`deshacer`:** cada tanda agendada queda en la base. `deshacer` compara la hora de lo último (un gasto, un lote o una tanda de balances) y deshace lo más nuevo.
- Franco pega `Codigo.gs` y publica una versión nueva de la implementación.

### Paso 4 — El resumen del día (solo la reacción)

- **Disparo propio** en el Apps Script (`relojDeBalances`, cada 10 minutos; también hace la lista del domingo, que sale de `Reenvio.gs`):
  - Desde las 18:30 de un día hábil: los 📊 de **hoy** marcados pre-apertura.
  - Desde las 9:30: los 📊 de **ayer** marcados post-cierre.
  - Lee el Calendar y manda `POST /api/balances` `{"accion": "resumen", "fecha", "empresas": [{"ticker", "momento"}], "id"}`.
- **La SuperApp** trae el precio de Yahoo y encola `📊 Balances` en un mensaje aparte:
  ```
  📊 Balances
  MSFT (post-cierre): posmercado positiva (+4,1%).
  KO (pre-apertura): rueda negativa (−2,3%).
  ```
  - **Rueda** (pre-apertura): el cierre de hoy contra el de ayer.
  - **Posmercado** (post-cierre): el último precio **dentro de la ventana `post` del día del balance** (16:00–20:00 de Nueva York), filtrado por la hora de cada barra, contra el cierre de ese día. A la mañana siguiente ya corre la pre-apertura del otro día.
  - **Neutra:** menos de ±1%.
  - Si Yahoo no contesta: `s/d`, con la excepción en el log.
- **Sin hora:** la rueda y el posmercado, a la mañana siguiente.
- La palabra se decide sobre el número redondeado que se muestra.
- **Confirmado por Franco (21/10):** el formato. **Yahoo desde Fly: sin probar**; la primera corrida real es la prueba (si falla, sale `s/d` con el motivo).

---

## 4. Reglas que se cumplen

- **Costo cero:** todo sale por `encolar_saliente`, solo `"type": "text"`. Los módulos nuevos van en `core/api/` y `places/finanzas/core/`: el test de costo cero los vigila solo.
- **Sin IA:** las fechas salen de Nasdaq y los precios de Yahoo. El texto es fijo.
- **Sin `except Exception: return <vacío>`:** `CalendarioNoDisponible`, `ListaNoDisponible` y similares, con su motivo.
- **Los tests no salen a internet:** Nasdaq, Wikipedia, Yahoo y el Apps Script, de mentira en un puerto local.
- **Sin claves nuevas:** Nasdaq, Wikipedia y Yahoo no piden clave.
