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

## Fase A — API de WhatsApp en el mismo contenedor (ADR-0008)

Desde la Fase A el contenedor corre **tres procesos**, y `fly.toml` no cambia:

| Proceso | Escucha en | Lo lanza |
|---|---|---|
| nginx | `0.0.0.0:8501` (el puerto de Fly) | `docker-entrypoint.sh` |
| API (`api.py`) | `127.0.0.1:8000` — nginx le pasa `/api/` | `docker-entrypoint.sh`, en un bucle que la relanza si se cae |
| Streamlit | `127.0.0.1:8502` — nginx le pasa `/` | `exec` al final del entrypoint |

El health check de Fly (`/_stcore/health`) pasa por nginx hacia Streamlit, así que prueba los dos juntos. La API tiene el suyo: `/api/health`.

**El contenedor nunca se construyó localmente** (no hay Docker en la PC de Franco): los tests lo revisan como texto (`tests/test_deploy_api.py`). El primer deploy es la prueba real. Después de `fly deploy`:

```powershell
curl.exe https://superapp-finanzas.fly.dev/_stcore/health     # ok  (Streamlit vía nginx)
curl.exe https://superapp-finanzas.fly.dev/api/health         # {"ok": true}
curl.exe https://superapp-finanzas.fly.dev/api/privacidad     # la página de privacidad
fly logs -a superapp-finanzas                                 # buscar "[api] INFO superapp.api: Escuchando"
```

Y abrir la app en el navegador: si carga y se puede navegar, el websocket pasa bien por nginx. **Si algo falla, volver a la release anterior** (`docs/RUNBOOK.md` → "Si la app no responde").

Secretos de WhatsApp (ver `.env.example` y `docs/WHATSAPP-CANAL.md`, Parte 3). Sin ellos, `/api/whatsapp` responde 503 y el resto anda igual:

```powershell
fly secrets set WHATSAPP_TOKEN=... WHATSAPP_PHONE_NUMBER_ID=... WHATSAPP_APP_SECRET=... WHATSAPP_VERIFY_TOKEN=... WHATSAPP_NUMERO_AUTORIZADO=549... SUPERAPP_DEFAULT_USER=<tu usuario> -a superapp-finanzas
```

### Fase B — briefings por WhatsApp

Un secreto más, para que el Apps Script pueda mandar los briefings a `POST /api/briefing`:

```powershell
fly secrets set SUPERAPP_API_TOKEN=<openssl rand -hex 32> -a superapp-finanzas
```

El mismo valor va en las Propiedades del script como `SUPERAPP_TOKEN`. Chequeo después del deploy (tiene que dar **401**, no 404 ni 503):

```powershell
curl.exe -s -X POST -H "Content-Type: application/json" -d "{}" https://superapp-finanzas.fly.dev/api/briefing
```

## Pendiente
- [ ] Dominio FreeDomain apuntando al deploy.
- [x] `requirements.lock` (pip freeze de build conocida-buena) para builds reproducibles. **Hecho el 27/8/2026.** El `Dockerfile` ya lo usaba si existía, así que no hubo que tocar el deploy. Ojo con una cosa al regenerarlo: ese día `pip` resolvía `pandas>=2.0.0` como **pandas 3.0.5**, un salto de major contra el que la suite nunca corrió, así que el lock se generó con los topes `pandas<3` / `numpy<2.3` y quedó en **pandas 2.3.3**. Verificado corriendo la suite completa en un venv de Python 3.11 con esos pines exactos: **679 passed**. Instrucciones de regeneración en la cabecera del propio archivo.

## Dominio
Opción gratis: **DigitalPlat FreeDomain** (`.dpdns.org`, `.us.kg`, etc.) apuntando al deploy vía Cloudflare DNS. Ej.: `superappfinanzas.dpdns.org`. Ver `docs/HERRAMIENTAS-EVALUADAS.md`. Para uso personal alcanza; si se vuelve comercial, migrar a dominio propio.
