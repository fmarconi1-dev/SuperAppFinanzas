# RUNBOOK — operación

Qué hacer cuando algo pasa. Escrito para leerse **el día del problema**, no antes.

---

## 🔴 Lo primero: qué se puede perder y qué no

| Dato | ¿Se puede reconstruir? | De dónde |
|---|---|---|
| **Transacciones de Finanzas Personales** | ❌ **NO** | No existen en ningún otro lado |
| Presupuestos y categorías | ❌ NO | Ídem |
| Movimientos de cartera | ✔ Sí | `Inversiones.xlsx` + los exports de inviu |
| Tenencia del broker | ✔ Sí | Volver a bajar el export |
| Precios y sectores cacheados | ✔ Sí | Se vuelven a resolver solos |
| Cantidad de BTC y otras tenencias manuales | ⚠️ A mano | Están en `EN-HUMANO.md` (0,00316847) |

**Todo el diseño del respaldo gira alrededor de la primera fila.** Si algún día hay que elegir qué salvar, es eso.

---

## 🗄️ Cómo está armado el respaldo

Tres capas, y **las dos primeras no alcanzan solas**:

1. **Copias automáticas antes de cada escritura** → `data/backups/` dentro del volumen de Fly. Las disparan las escrituras de Finanzas Personales (transacciones, presupuestos, categorías) y, **desde la Fase 4**, también las de cartera: import de movimientos, import de tenencia, corrección de un movimiento y alta de tenencia manual. Retención: última copia de cada día de los últimos 30 días + las 10 más recientes.
   ⚠️ **Viven en el mismo volumen que la base.** Si se pierde el volumen, se pierden juntas. Protegen contra un error tuyo, no contra una pérdida de disco.

2. **Snapshots del volumen de Fly** — automáticos y diarios. Protegen contra la pérdida del volumen, pero son de Fly y no los controlás vos.

3. **Copia externa en tu PC** → `scripts\backup_remoto.ps1`. **Es la única que sobrevive a que Fly desaparezca.** Es la capa que hay que mantener viva.

---

## 💾 Backup: sacar una copia a la PC

```powershell
cd "C:\Users\Franco\OneDrive\Desktop\Finanzas Personales\Superapp de Finanzas\SuperAppFinanzas"
powershell -ExecutionPolicy Bypass -File scripts\backup_remoto.ps1
```

Deja el archivo en `backups-remotos\superapp-AAAAMMDD-HHMMSS.db` y **verifica antes de darlo por bueno**. Si el archivo baja vacío o corrupto, **falla y avisa** en vez de dejarte una copia inútil.

### ⚠️ `app has no started VMs`

El `fly.toml` usa `auto_stop_machines = true` con `min_machines_running = 0`: **la máquina se duerme sola**. Y `fly ssh sftp` necesita una máquina encendida.

**Esto no es un caso raro: es el caso normal.** La tarea programada corre de madrugada, cuando la app siempre está dormida. Por eso el script ya no confía en despertarla con un request HTTP —falló así el 4/8/2026— sino que **lista las máquinas, enciende la que esté apagada y espera al health** antes del `sftp`.

Si aun así ves el error, el diagnóstico es:

```powershell
fly status -a superapp-finanzas
```

- Hay una máquina en **`stopped`** → `fly machine start <id> -a superapp-finanzas`.
- **No hay ninguna máquina** → falta desplegar: `fly deploy -a superapp-finanzas`.

La verificación vive en `scripts\verificar_backup.py` y se puede correr sola sobre cualquier copia:

```powershell
python scripts\verificar_backup.py backups-remotos\superapp-20260804-105642.db
```

Imprime `integridad|transacciones|movimientos|usuarios` y devuelve código 0 solo si la copia sirve. **Sirve** = pasa `integrity_check`, tiene usuarios y **tiene al menos una transacción**: eso es lo irreemplazable. Una cartera vacía no invalida la copia (puede ser anterior al primer import).

### Programarlo (dos comandos, una sola vez)

⚠️ **Lo que pasó (27/9/2026):** el backup estuvo **un mes sin correr** y nada lo avisó. La tarea programada no existía en la PC —aunque `ESTADO.md` la daba por confirmada— y, aunque hubiera existido, habría fallado: usaba tu sesión de `fly auth login`, que **vence** (el 23/9 pidió login a mitad de la corrida). Una tarea de madrugada no tiene quién se loguee.

**1. Guardar un token de la app** (con tu sesión de fly activa; si venció, antes `fly auth login`):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\guardar_token_fly.ps1
```

Crea un *deploy token* **limitado a `superapp-finanzas`**, que vence en un año (no en 20, el default de fly), y lo guarda en `%LOCALAPPDATA%\SuperAppFinanzas\fly_token.txt`: **fuera del repo y fuera de OneDrive**, con permisos solo para tu usuario. Nunca se muestra en pantalla. Lo prueba en el momento. Para revocarlo: `fly tokens list -a superapp-finanzas` y `fly tokens revoke <id>`.

**2. Registrar la tarea** (si da "Acceso denegado", PowerShell como administrador):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\programar_backup.ps1
```

Queda diario a las 09:00 (`-Hora 09:30` para cambiarla, `-Quitar` para borrarla). El script deja puestas las tres opciones que se olvidan a mano y que hacen que la tarea **exista pero no corra**:

| Opción | Sin ella |
|---|---|
| `StartWhenAvailable` | el día que la PC estuvo apagada a esa hora, no hay backup |
| `AllowStartIfOnBatteries` | en notebook, el default de Windows es **no correr con batería** |
| `ExecutionTimeLimit` | una corrida colgada bloquea todas las siguientes |

Probala en el momento, sin esperar a mañana:

```powershell
Start-ScheduledTask -TaskName "Backup Superapp Finanzas"
```

Como la carpeta está en OneDrive, la copia además se sincroniza a la nube sola.

### ¿Viene funcionando? (un comando)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\estado_backup.ps1
```

Muestra **si la tarea programada existe y cómo le fue**, **si hay token y cuándo vence** (avisa 30 días antes), las últimas copias con su antigüedad y las últimas corridas de la bitácora (`backups-remotos\backup.log`), y **da un veredicto**: verde si la copia más nueva tiene 2 días o menos **y** no falta ninguna pieza.

**Y si falla, te enterás sin correr nada:** el backup deja `BACKUP SUPERAPP - FALLO.txt` en el Escritorio con el motivo y qué hacer; la próxima copia buena lo borra. Si no puede hablar con Fly corta en segundos con el motivo (antes seguía y moría en el `sftp` con un error que no explicaba nada), y nunca se queda esperando un login.

⚠️ **Por qué hace falta.** La tarea corre de madrugada y nadie mira la consola. **Un backup que dejó de funcionar y no avisa es peor que no tener backup**, porque da una sensación de protección que no existe. El log distingue *"no corrió"* de *"corrió y falló"*, que no es lo mismo. Corré esto cada tanto.

---

## ♻️ Restore: volver a una copia

**Antes de correr nada:** el restore pisa la base de producción. Si el problema es "borré una transacción sin querer", puede salir más barato volver a cargarla a mano.

```powershell
# 1. Simulacro: verifica la copia y te muestra qué tiene. NO toca producción.
powershell -ExecutionPolicy Bypass -File scripts\restaurar_backup.ps1 `
    -Archivo backups-remotos\superapp-20260730-2200.db

# 2. Si los números que muestra son los que esperás, recién ahí:
powershell -ExecutionPolicy Bypass -File scripts\restaurar_backup.ps1 `
    -Archivo backups-remotos\superapp-20260730-2200.db -Confirmar
```

El script, en orden: verifica la copia → **enciende la máquina** → **guarda el estado actual de producción** en `pre-restore-*.db` → sube la copia a un **temporal** → hace el swap y borra `-wal`/`-shm` en un solo comando → **reinicia la máquina** → chequea el health.

⚠️ **Lo de `-wal` y `-shm` no es opcional.** SQLite guarda las escrituras recientes en esos dos archivos aparte. Si se reemplaza el `.db` sin borrarlos, SQLite mezcla la base restaurada con el diario de la vieja y el resultado es una base corrupta.

⚠️ **No uses la app mientras corre el restore.** Como no se puede entrar por SSH a una máquina apagada, el swap se hace con la app viva: queda una ventana de ~1 segundo entre el reemplazo y el reinicio en la que una escritura tuya volvería a crear el `-wal`. Es una app de un solo usuario: la ventana es teórica si vos no estás tocándola.

### 🐛 Este script estaba roto y nadie lo sabía (reescrito el 4/8/2026)

La versión original **no podía funcionar**: hacía `fly scale count 0` para "parar" la app —que no la para, la **destruye**— y después intentaba entrar por `fly ssh` a una máquina inexistente. El restore se colgaba ahí, **con la app caída y la base sin reemplazar**: el peor estado posible. Y `scale count 1` tenía que crear una máquina nueva, cosa que puede fallar (`cpu_overcommit_exceeded` pasó de verdad ese mismo día en un deploy común), así que el camino de vuelta tampoco estaba garantizado.

**Nunca se detectó porque el ensayo end-to-end quedó siempre pendiente.** Es la demostración literal de la frase de acá abajo. Ahora usa `fly machine restart`, que preserva la máquina y su volumen, y `tests/test_scripts_backup.py` falla si alguien vuelve a poner `scale count`.

Si el restore sale mal, la base previa quedó en `pre-restore-*.db`: restaurá **esa** con el mismo script.

### Restaurar desde una copia interna (las de `data/backups/`)

```powershell
fly ssh sftp get /app/data/backups/finanzas-20260730-2200.db .\rescate.db -a superapp-finanzas
powershell -ExecutionPolicy Bypass -File scripts\restaurar_backup.ps1 -Archivo .\rescate.db -Confirmar
```

---

## 🧪 Ensayo de restore

**Un backup que nunca se restauró no es un backup: es un archivo.**

El ciclo completo (respaldar → perder → restaurar → verificar) está automatizado en `tests/test_backup_restore.py` y corre con la suite. Eso cubre el **mecanismo**.

Lo que el test no puede cubrir es tu entorno real: que `flyctl` esté logueado, que el sftp funcione, que la tarea programada corra. **Ensayalo de verdad una vez, y repetilo cada tanto:**

1. Corré `backup_remoto.ps1` y confirmá que el archivo aparece con números razonables.
2. Corré `restaurar_backup.ps1` **sin** `-Confirmar` sobre esa copia: tiene que mostrarte usuarios, transacciones y movimientos.
3. Abrí la app y comprobá que los números coinciden con lo que mostró el simulacro.

No hace falta pisar producción para ensayar: el paso 2 valida la copia y el procedimiento sin riesgo.

- [ ] **Pendiente de Franco:** primer ensayo end-to-end + tarea programada.

---

## 🚨 Si la app no responde

1. `fly status -a superapp-finanzas` — ¿la máquina está `started`?
2. `fly logs -a superapp-finanzas` — ¿hay traceback?
3. `curl.exe https://superapp-finanzas.fly.dev/_stcore/health` — tiene que decir `ok`.

⚠️ **Falso positivo conocido:** `fly deploy` a veces avisa *"The app is not listening on the expected address"* cuando la app está perfecta. Es una carrera con el `grace_period` de 30 s del arranque. Si `fly status` dice `started` y el health responde `ok`, **no toques nada**.

Volver a la versión anterior:

```powershell
fly releases -a superapp-finanzas
fly deploy --image <imagen-de-la-release-anterior> -a superapp-finanzas
```

---

## 🧱 El deploy falla por falta de recursos en el host

Dos mensajes, **una sola causa**:

```
insufficient CPUs available ... cpu_overcommit_exceeded
insufficient memory available to fulfill request on the current host
```

**No es un problema de tu app ni del código.** Es el host de Fly en `gru`
diciendo que no le entra. La estrategia de deploy por defecto es *rolling*:
levanta la máquina nueva, la verifica, y **recién ahí** baja la vieja — o sea
que durante el cambio necesita **el doble de recursos** (2 GB de RAM en vez de
1). Y como tu máquina está atada al volumen `finanzas_data`, **no puede mudarse
a otro host**: donde está el volumen, ahí tiene que correr.

Con **una sola máquina**, ese solapamiento no compra nada: no hay alta
disponibilidad que proteger.

✅ **Desde el 4/8/2026 esto ya está resuelto por configuración:** el `fly.toml`
tiene `[deploy] strategy = "immediate"`, así que un `fly deploy` común ya usa el
reemplazo directo y no hay que acordarse del flag. `immediate` para la máquina
antes de actualizarla, así necesita 1 GB en vez de 2. **Qué cambia:** unos
segundos de caída — es una app personal, la pantalla se recarga y listo.

**Si `immediate` también falla**, liberá la memoria explícitamente antes:

```powershell
fly status -a superapp-finanzas          # anotá el id de la máquina
fly machine stop <id> -a superapp-finanzas
fly deploy --strategy immediate -a superapp-finanzas
```

Con la máquina apagada el host ya tiene el GB libre para reservar. Es la vía más
determinista.

Si aun así corta, el host está saturado de verdad: esperá un rato y reintentá.
**No bajes la memoria de la app** — 1 GB es lo que necesita pandas para las
valuaciones de la cartera — ni toques el `Dockerfile`.

---

## 🔑 Secrets

```powershell
fly secrets list -a superapp-finanzas
fly secrets set SIGNUP_CODE=... SESSION_SECRET=... -a superapp-finanzas
```

Ambos son opcionales (ver `.env.example`). Setearlos **reinicia la app**.

Los de WhatsApp (`WHATSAPP_*`, `SUPERAPP_DEFAULT_USER`) también: sin ellos el webhook responde 503 y la app anda igual. Detalle en `docs/DEPLOY.md` (Fase A).

---

## 📱 Si el bot de WhatsApp no contesta

1. `curl.exe https://superapp-finanzas.fly.dev/api/health` → tiene que dar `{"ok": true}`. Si no, la API no está corriendo: `fly logs` y buscar `[entrypoint] La API terminó`.
2. `fly logs -a superapp-finanzas` mientras le mandás `ayuda`. Qué buscar:
   - `Webhook deshabilitado: Faltan variables de entorno: …` → falta un secreto.
   - `firma inválida` → `WHATSAPP_APP_SECRET` no es la clave secreta de **esta** app de Meta.
   - `número no autorizado` → `WHATSAPP_NUMERO_AUTORIZADO` no coincide con el que escribe.
   - `No se pudo responder por WhatsApp (código 131047)` → pasaron más de 24 h desde tu último mensaje (no debería pasar: siempre le escribís vos primero).
   - `código 190` → el token venció o es el temporal: generá el permanente del usuario del sistema.
   - `código 131042` → Meta pide medio de pago. **No se carga tarjeta** (ADR-0008): plan B, Telegram.
   - nada de nada → Meta no está mandando el webhook: revisá la suscripción a `messages` en el panel, o pasá la app a modo Live (`docs/WHATSAPP-CANAL.md`, paso 13).
3. Qué pasó con cada mensaje queda en la tabla `whatsapp_mensajes` (`resultado`: cargado, pendiente, rechazado, deshecho, ignorado, error).

---

## 🧪 Los tests-oráculo (por qué CI muestra `skipped`)

Tres módulos no verifican lógica contra casos inventados: verifican los **números reales** contra una fuente de verdad externa. Son los más valiosos del repo —atajaron los errores de cálculo de la Fase 3a— pero necesitan archivos que **por regla dura nunca se versionan**:

| Test | Necesita | Variable de entorno |
|---|---|---|
| `test_kpis.py` | `Diario.csv` + `Mensual.csv` | `DIARIO_CSV`, `MENSUAL_CSV` |
| `test_reconciliacion.py` | ídem | ídem |
| `test_cartera_recon.py` | `Inversiones.xlsx` | `CARTERA_XLSX` |

En CI esos archivos no existen **y no deben existir**, así que los tests se saltean con un motivo explícito y el conteo de `skipped` deja el rastro. Si algún día ves 20 skips donde esperabas 3, algo cambió.

⚠️ **Esto implica que los oráculos solo corren en tu máquina.** Antes de un deploy, corré la suite local: ahí no se saltea ninguno y el conteo tiene que dar **0 skipped**.

**Lo que NO se hace:** alimentarlos con CSV falsos. `test_kpis.py` compara contra importes exactos ($15.014.431 de ingreso anual, entre otros); con datos inventados o falla, o hay que cambiar los valores esperados — y ahí el test deja de proteger. Tampoco `--ignore` en el workflow: desaparecen de la salida y nadie se entera de que existen.

---

## 📊 Snapshot del scoring

La app **solo lee** el snapshot que publica el batch de GitHub Actions del repo `Scoring-Inversiones` (ADR-0002). Si el scoring se ve viejo, el problema está allá, no acá. La cartera tiene fallback: sin snapshot, los sectores los resuelve Yahoo igual.

---

## 📋 Pendientes de operación

- [ ] Primer ensayo de restore end-to-end (arriba).
- [ ] Programar `backup_remoto.ps1` en el Programador de tareas.
- [ ] Monitor de uptime (UptimeRobot u otro) contra `/_stcore/health`.
- [ ] `requirements.lock` (`pip freeze > requirements.lock`) para builds reproducibles.
- [ ] Retirar `radar-financiero`: `fly apps destroy radar-financiero`.

---

## 🪟 Tests que borran archivos: Linux vs Windows

`tests/test_backup_restore.py` simula la pérdida de la base borrando el
archivo. **Linux permite borrar un archivo con handles abiertos; Windows no**
(`PermissionError [WinError 32]`). El test pasaba en CI (Linux) y fallaba en la
máquina de Franco.

**No era un problema del backup:** se verificó que después de `init_db()` y
`backup_db()` **no queda ninguna conexión sqlite abierta**. Los handles que
sobran son objetos ya cerrados esperando al recolector.

El helper `_perder_la_base()` fuerza `gc.collect()`, borra los compañeros
`-wal`/`-shm` y reintenta. **Regla general: cualquier test que borre o
reemplace archivos tiene que probarse en Windows, no solo en CI.**

---

## 🔒 `database is locked`

Pasó el 4/8/2026 al cargar un ajuste de tenencia: la app **murió entera**, con
el traceback apuntando a `init_db() → _migrate()`. **Cuatro defectos sumados**,
los cuatro arreglados:

1. **`init_db()` corría en cada rerun de Streamlit** — o sea en cada click: el
   schema entero y las 13 migraciones, pidiendo el lock de escritura para
   `ALTER TABLE` y `CREATE INDEX` que ya estaban hechos. Ahora va detrás de
   `@st.cache_resource`: **una vez por proceso**.
2. **`connect()` no configuraba `busy_timeout`** — ante un lock tomado, SQLite
   fallaba en vez de esperar. Ahora espera hasta 30 s.
3. ⚠️ **`_migrate` abría con `BEGIN` diferido.** Este es el sutil: con `BEGIN` a
   secas la transacción arranca en modo lectura y pide el lock de escritura
   recién en la primera escritura — y **ahí SQLite no aplica `busy_timeout`**,
   devuelve `SQLITE_BUSY` al instante, porque esperar con lecturas ya hechas
   podría terminar en deadlock. O sea que el punto 2 **no alcanzaba solo**.
   Ahora usa `BEGIN IMMEDIATE`: el lock se toma al abrir, que es donde el
   timeout sí cuenta.
4. **El backup se sacaba con la conexión de escritura ya abierta**, alargando la
   ventana de colisión. Ahora va antes.

**Si vuelve a aparecer:** mirá si alguna transacción nueva usa `BEGIN` a secas y
escribe después de leer. Cubierto por `tests/test_db_concurrencia.py`, que
levanta dos hilos de verdad y falla si se revierte cualquiera de los cuatro.
