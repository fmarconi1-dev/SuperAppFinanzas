# scripts/

<!-- huella: 92272af8c3af -->

Resumen: Operación y mantenimiento: backups remotos (PowerShell + verificación), reset de contraseñas y el indexador del mapa.

## Buscar acá si

- backup remoto diario, restaurar, "¿este backup sirve de verdad?" → `backup_remoto.ps1`, `restaurar_backup.ps1`, `verificar_backup.py`, `estado_backup.ps1`, `programar_backup.ps1`
- resetear la contraseña de un usuario → `setup_password.py`
- reindexar el mapa del repo → `indexar.py` (ver `/MAPA.md`)
- el ícono de la pestaña del navegador (el moño) → `generar_favicon.py` (dibuja `assets/favicon.png` con Pillow; correr si cambia `assets/logo.svg`)
- "¿Nasdaq, Wikipedia y Yahoo contestan desde Fly?" (balances, ADR-0011) → `probar_fuentes_balances.py`, corrido con `fly ssh console -a superapp-finanzas -C "python /app/scripts/probar_fuentes_balances.py"`: OK o FALLA por fuente, no escribe nada
- "¿Meta deja mandar texto sin tarjeta?" → `probar_whatsapp_texto.py` (prueba única de costo cero, ADR-0008; manda un texto libre y traduce el código de error de Meta)
- "el backup no corre solo", "la sesión de fly venció", token de Fly → `guardar_token_fly.ps1`, `_fly_comun.ps1` (`Use-TokenFly`)
- un archivo "BACKUP SUPERAPP - FALLO.txt" apareció en el Escritorio → lo deja `backup_remoto.ps1` al fallar; `estado_backup.ps1` dice por qué

## Trampas

- Los `.ps1` corren en la máquina de Franco (Windows), no en Fly.
- ⚠️ **La sesión de `fly auth login` vence** (27/9/2026): el backup estuvo un mes sin correr —la tarea programada ni existía y, sin token, habría fallado igual—. Ahora el backup usa un *deploy token* de la app guardado en `%LOCALAPPDATA%\SuperAppFinanzas\` (fuera del repo y de OneDrive; `guardar_token_fly.ps1`, vence al año, `estado_backup.ps1` avisa 30 días antes). Sin token cae a la sesión.
- **Toda consulta de prueba a fly va con `< NUL`** (`cmd /c "fly ... < NUL"`): sin consola que conteste, flyctl no puede quedarse esperando un login hasta el timeout de la tarea. Si no puede listar las máquinas, `Start-AppFly` **corta** con el motivo (antes decía "sigo igual" y moría en el `sftp`).
- **Un backup que falla deja un aviso en el Escritorio** y la próxima corrida buena lo borra. `estado_backup.ps1` además revisa que la tarea programada exista y que haya token: las copias solas no alcanzan para saber si mañana va a haber otra.
- Los `.ps1` se guardan **solo en ASCII** en el código: PowerShell 5.1 lee un archivo sin BOM como ANSI y un acento en un string se rompe.
- `restaurar_backup` deja `pre-restore-*.db` (gitignored) como red de seguridad.
- ⚠️ **`indexar.py` en Windows (22/9/2026):** las rutas llegan con `\` y los patrones del `.gitignore` usan `/`. Sin normalizar, `ignorado()` no reconocía ninguna carpeta ignorada: el `MAPA.md` commiteado listaba `Borrar/` y el indexador **leía los `.db-shm` de los backups de producción** buscando URLs. Normalizado, y `*.db-shm`/`*.db-wal`/`*.db-journal` ignorados por nombre. Test: `tests/test_indexar.py`.
- `git()` de `indexar.py` devuelve `""` si git no responde: cada llamador tiene que tolerarlo **con el tipo correcto** (el `{}` en vez de `Counter()` del 27/8 rompía el hook pre-commit).

## Estado

- **Funciona:** backup remoto programado y verificado.
- **21/10/2026:** `probar_fuentes_balances.py` nuevo: el diagnóstico de las fuentes de los balances desde la máquina de Fly (las fuentes pueden rechazar servidores aunque desde la PC anden). Test: `tests/test_balances_fuentes.py::test_el_diagnostico_dice_que_fuente_falla`.
- **14–15/10/2026:** `probar_whatsapp_texto.py` nuevo (stdlib). Solo arma `"type": "text"`, lee el token del portapapeles (pegar en `getpass` no anda en la consola de Windows: Ctrl+V llega como basura y Meta contesta 190) y muestra el `wa_id` al que Meta resolvió el número. Manda **sin el 9** a los celulares argentinos. **Dos formatos, cada uno en su lugar (comprobado en producción el 15/10/2026):** en la **lista del panel** el celular argentino va **con el 9** (`549…`; sin el 9, Meta acepta los envíos y no los entrega); los mensajes entrantes traen el `from` **con el 9**; y para **mandar**, Meta lo quiere **sin el 9** (`54…`): a `549…` responde 131030 aunque la lista esté bien. Resultado real: **el texto llegó sin tarjeta**.
- **14/10/2026:** `verificar_docta.py` se retiró junto con Inversiones (ADR-0007). `verificar_backup.py` sigue contando `cartera_movimientos`: la tabla quedó en la base.

## Proximo paso

—
