# DEPLOY

## Hosting confirmado (MVP): Fly.io
Ver comparativa y costos en `../PLAN DE TRABAJO - Superapp Finanzas.md` §5. Decisión: consolidar en Fly.io (Mis-Finanzas ya vive ahí como `radar-financiero`).

## Fase 0 — hola mundo (desplegado 2026-07-10) ✅
App `superapp-finanzas`, región `gru`. Validó el pipeline.

## Fase 1 — Lugar A (Finanzas) en el monorepo
Config heredada del deploy probado de `radar-financiero`: puerto 8501, health check `/_stcore/health`, volumen `finanzas_data` montado en `/app/data` (DB + backups), 1 GB de RAM.

### 1. Crear volumen y secrets (una sola vez)
```bash
cd SuperAppFinanzas
fly volumes create finanzas_data -r gru -s 1 -a superapp-finanzas
fly secrets set SIGNUP_CODE=<mismo-que-radar> SESSION_SECRET=<mismo-que-radar> -a superapp-finanzas
```
(Usar los mismos valores que `radar-financiero` mantiene válidas las sesiones "recordarme".)

### 2. Deploy
```bash
fly deploy
```

### 3. Migrar los datos de producción (desde radar-financiero)
Los datos actuales viven en el volumen de `radar-financiero`, NO en los archivos locales (que están viejos).

```bash
# a) Backup consistente de la DB de producción (dentro de la máquina vieja)
fly ssh console -a radar-financiero -C "python -c \"import sqlite3; s=sqlite3.connect('/app/data/finanzas.db'); d=sqlite3.connect('/tmp/mig.db'); s.backup(d); d.close()\""

# b) Descargarla a tu PC
fly ssh sftp get /tmp/mig.db ./finanzas-prod.db -a radar-financiero

# c) Subirla a la app nueva (la máquina debe estar corriendo: abrí la URL antes)
fly ssh sftp shell -a superapp-finanzas
>> put finanzas-prod.db /app/data/finanzas.db
>> exit

# d) Limpiar restos de WAL y reiniciar
fly ssh console -a superapp-finanzas -C "rm -f /app/data/finanzas.db-wal /app/data/finanzas.db-shm"
fly apps restart superapp-finanzas
```
Verificar: login con tu usuario de siempre y comparar el dashboard contra `radar-financiero`.

### 4. Retiro de radar-financiero (recién cuando la superapp esté validada)
No borrar la app vieja hasta usar la nueva unos días. Después: `fly apps destroy radar-financiero`.

## Pendiente
- [ ] Dominio FreeDomain apuntando al deploy.
- [x] `requirements.lock` (pip freeze de build conocida-buena) para builds reproducibles. **Hecho el 27/8/2026.** El `Dockerfile` ya lo usaba si existía, así que no hubo que tocar el deploy. Ojo con una cosa al regenerarlo: ese día `pip` resolvía `pandas>=2.0.0` como **pandas 3.0.5**, un salto de major contra el que la suite nunca corrió, así que el lock se generó con los topes `pandas<3` / `numpy<2.3` y quedó en **pandas 2.3.3**. Verificado corriendo la suite completa en un venv de Python 3.11 con esos pines exactos: **679 passed**. Instrucciones de regeneración en la cabecera del propio archivo.

## Dominio
Opción gratis: **DigitalPlat FreeDomain** (`.dpdns.org`, `.us.kg`, etc.) apuntando al deploy vía Cloudflare DNS. Ej.: `superappfinanzas.dpdns.org`. Ver `docs/HERRAMIENTAS-EVALUADAS.md`. Para uso personal alcanza; si se vuelve comercial, migrar a dominio propio.
