# integraciones/google-apps-script/

Resumen: Puente Google ↔ SuperApp en Apps Script: reenvía el briefing de Gmail a la API (con links acortados) y atiende el webhook que crea/lista eventos de Calendar y tareas de Tasks.

## Buscar acá si

- el briefing matutino no llegó o llegó dos veces → `reenviarBriefingAWhatsApp` (etiqueta `WA-Enviado`, solo si la API devolvió `ok: true`)
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

## Proximo paso

Instalarlo siguiendo el `README.md` cuando arranque la Fase B (briefing + Calendar/Tasks), y correr `probarLecturas` / `probarAcortador` desde el editor.
