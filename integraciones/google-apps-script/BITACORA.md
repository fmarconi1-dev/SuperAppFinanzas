# integraciones/google-apps-script/

Resumen: Puente Google ↔ SuperApp en Apps Script: reenvía el briefing de Gmail a la API (con links acortados) y atiende el webhook que crea/lista eventos de Calendar y tareas de Tasks.

## Buscar acá si

- el briefing matutino no llegó o llegó dos veces → `reenviarBriefingAWhatsApp` (etiqueta `WA-Enviado`, solo si la API devolvió `ok: true`)
- números de mercado mal o viejos, `s/d` en el tablero, el cierre de las 18:30 no salió → `Mercado.gs` (`probarMercado`, `cierrePendiente_`, propiedad `ULTIMO_CIERRE`; ADR-0010)
- links del briefing sin acortar → `acortarUrls` (TinyURL vía `fetchAll`; si falla, deja el original)
- el contrato SuperApp → Google (acciones, campos, errores) → `README.md` de esta carpeta
- eventos con la hora corrida → zona horaria en `appsscript.json`
- un evento o tarea duplicado por reintento → `id_solicitud` + `CacheService` (6 h)

## Trampas

- **No corre en Fly ni en el contenedor**: se pega a mano en script.google.com. Cambiar el código acá no cambia nada hasta pegarlo y publicar una **versión nueva** de la implementación (la URL `/exec` sirve la versión fijada).
- Apps Script **no expone los headers** del request: el secreto del webhook viaja en el cuerpo (`secreto`). Y siempre responde HTTP 200: el resultado es `ok`.
- El POST a la web app vuelve con un 302 a `script.googleusercontent.com` que hay que seguir con GET.
- `new Date(a, m, d, h, mi)` usa la zona del proyecto: si `appsscript.json` no dice Buenos Aires, los eventos se corren de hora.
- `getAllDayEndDate()` es exclusivo; la respuesta devuelve `fin` inclusive.
- Tasks API descarta la hora de `due`, y `Tasks.Tasks.list` devuelve renglones sin título al final de la lista (se filtran).

## Estado

- **14/10/2026:** reescrito desde el borrador de Franco. Cambios: secretos en Propiedades del script (nada en el código), token en header, secreto en `doPost`, validación de fechas y horas, idempotencia con lock (`id_solicitud` + `CacheService` + `LockService`), confirmación solo con `ok: true`, y acciones de lectura (`listar_calendarios`, `listar_eventos`, `listar_tareas`, `resumen_semana`) + `completar_tarea` para el dashboard. **Sin probar en Google todavía** (no hay runtime JS local; tampoco se verificó la sintaxis con node).
- **Fuera del MAPA:** `indexar.py` no reconoce `.gs`, así que esta carpeta no se indexa y `--sellar` responde "Carpeta no indexada". Si molesta, agregar `".gs": "javascript"` a `LENGUAJES` en `scripts/indexar.py`.

- **16/10/2026:** `reenviarBriefingAWhatsApp` pasa a ser el **reemplazo del reenvío por CallMeBot** (mismo nombre de función, misma etiqueta `WA-Enviado`, mismo filtro): procesa todos los mails pendientes en orden, manda `tipo` (cierre si el asunto dice "Cierre de Mercado"), sin `$`→`ARS` ni bloques de 650, con lock. Se instala **después** de desplegar `/api/briefing`. Sin probar en Google.

- **16/10/2026:** separado en **`Reenvio.gs`** (reenvío de briefings; reemplaza al script de CallMeBot y funciona solo) y **`Codigo.gs`** (agenda, se suma al mismo proyecto después). El reenvío manda también `id` (id del mail en Gmail) para que un reintento no duplique.

- **16/10/2026:** ✅ `Reenvio.gs` **instalado y andando**: reemplazó al script de CallMeBot y el cierre de mercado del 16/10 llegó por el Secretario. `Codigo.gs` (agenda) todavía sin instalar.

- **17/10/2026:** la SuperApp ya tiene el cliente de `Codigo.gs` (`core/api/google.py`) y los comandos `evento:` / `tarea:` / `agenda`. **Falta instalar `Codigo.gs`** en el mismo proyecto que `Reenvio.gs`, con el manifiesto `appsscript.json`, y publicarlo como aplicación web (README, pasos 1–7).

- **17/10/2026:** ✅ `Codigo.gs` **instalado y publicado** como aplicación web en el mismo proyecto que `Reenvio.gs`; `evento:` / `tarea:` / `agenda` funcionan punta a punta. Fase B cerrada.

- **19/10/2026 — ADR-0010:** el 19/10 Gemini mandó números de otros días: el matutino, el cierre del jueves; el cierre, el del viernes; un mayorista inventado. Ahora los arma **`Mercado.gs`**, con Yahoo, el Tesoro de EE.UU., BYMA, dolarapi, argentinadatos y data912.
  - `Reenvio.gs` pone el tablero en el matutino: en el renglón `[TABLERO]`, o en lugar del bloque "TABLERO" de Gemini.
  - `Reenvio.gs` descarta el "Cierre de Mercado" de Gemini y, desde las 18:30 de lunes a viernes, manda el cierre de `Mercado.gs` (`cierrePendiente_`, `id` `cierre-AAAA-MM-DD`).
  - El POST quedó en `mandarASuperApp_`.
  - **Probado fuera de Google** con QuickJS, simulando `UrlFetchApp` y `Utilities`, contra las fuentes reales: sin errores, números iguales a los del día, el reemplazo del tablero anda en los cuatro casos, y si cae una fuente, solo ella sale `s/d`.
  - **Sin probar en Google:** falta pegarlo y correr `probarMercado`. Riesgo: que Yahoo rechace a los servidores de Google.
  - Trampas:
    - El **MSCI MERVAL** arrancó el 19/10 en base 100.000 y reemplaza al S&P Merval. El `^MERV` de Yahoo quedó en el 16/10.
    - El CSV del Tesoro tarda unos 20 s.
    - El Python local rechaza la cadena de certificados nueva de Let's Encrypt de data912 (almacén viejo; con curl anda).

- **20/10/2026:** el matutino no llegó. El mail de Gemini llegó a Gmail a las 9:23, ya con `[TABLERO]` y sin cifras en las noticias, pero quedó sin la etiqueta `WA-Enviado`, y Fly no recibió ningún POST.
  - El código pegado en "Agente - Briefings" es idéntico al del repo.
  - Corrido acá con el mail real, arma bien el matutino en 13 s. **La falla es del lado de Google:** hay que verla en *Ejecuciones*.
  - En la misma prueba de la mañana aparecieron dos cosas, ya corregidas:
    - BYMA `index-price` viene **vacío antes de la apertura**. Ahora se guarda el último MSCI MERVAL (`ULTIMO_MERVAL`) y se usa con su fecha.
    - A la mañana el `^TNX` de Yahoo es la tasa en plena rueda, no un cierre. El respaldo de Yahoo para el 10 y el 30 años ahora es solo para el cierre (`paraCierre`); a la mañana manda el Tesoro de ayer.

- **21/10/2026 — `Balances.gs` (ADR-0011, paso 2):** el reloj de la lista de balances. `balancesPendientes_` (lo llama `reenviarBriefingAWhatsApp`) pide el domingo desde las 20:00 la semana que viene (`POST /api/balances`, `id` `balances-AAAA-MM-DD`, propiedad `ULTIMO_BALANCES`). Acá no se trae ningún dato. `pedirBalancesAhora` lo prueba a mano. Sintaxis y lógica del domingo probadas con QuickJS (19:59 no sale; un 503 reintenta; no se repite). **Sin pegar en Google todavía.**

## Proximo paso

Instalarlo siguiendo el `README.md` cuando arranque la Fase B (briefing + Calendar/Tasks), y correr `probarLecturas` / `probarAcortador` desde el editor.
