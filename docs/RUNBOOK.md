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

Deja el archivo en `backups-remotos\superapp-AAAAMMDD-HHMMSS.db` y **verifica antes de darlo por bueno**: `integrity_check`, que haya transacciones y que haya movimientos de cartera. Si el archivo baja vacío o corrupto, **falla y avisa** en vez de dejarte una copia inútil.

Sale por error si hay **0 transacciones**: eso es lo irreemplazable, y una copia sin eso no sirve.

### Programarlo (hacelo una vez)

Programador de tareas de Windows → Crear tarea básica → diario, a una hora en que la PC esté prendida:

- **Programa:** `powershell.exe`
- **Argumentos:** `-ExecutionPolicy Bypass -File "C:\Users\Franco\OneDrive\Desktop\Finanzas Personales\Superapp de Finanzas\SuperAppFinanzas\scripts\backup_remoto.ps1"`

Como la carpeta está en OneDrive, la copia además se sincroniza a la nube sola.

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

El script, en orden: verifica la copia → **guarda el estado actual de producción** en `pre-restore-*.db` → para la app → sube la copia → borra los archivos `-wal` y `-shm` → levanta la app → chequea el health.

⚠️ **Lo de `-wal` y `-shm` no es opcional.** SQLite guarda las escrituras recientes en esos dos archivos aparte. Si se reemplaza el `.db` sin borrarlos, SQLite mezcla la base restaurada con el diario de la vieja y el resultado es una base corrupta.

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

## 🔑 Secrets

```powershell
fly secrets list -a superapp-finanzas
fly secrets set SIGNUP_CODE=... SESSION_SECRET=... -a superapp-finanzas
```

Ambos son opcionales (ver `.env.example`). Setearlos **reinicia la app**.

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
