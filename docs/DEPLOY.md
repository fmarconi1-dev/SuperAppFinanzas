# DEPLOY

## Hosting confirmado (MVP): Fly.io
Ver comparativa y costos en `../PLAN DE TRABAJO - Superapp Finanzas.md` §5. Decisión: consolidar en Fly.io (Mis-Finanzas ya vive ahí).

## Fase 0 — hola mundo (desplegado 2026-07-10) ✅
- `app.py` — Streamlit mínimo, sin lógica.
- `requirements.txt` — solo `streamlit`.
- `Dockerfile` — python:3.12-slim, puerto 8080.
- `fly.toml` — app `superapp-finanzas`, región `gru`, auto-stop, 512 MB.
- `.dockerignore` — anti-leak: `data/`, `*.xlsx`, `*.db`, `.env` jamás entran a la imagen.

### Cómo deployar (en tu máquina, con flyctl logueado)
```bash
cd SuperAppFinanzas
fly apps create superapp-finanzas   # solo la primera vez; si el nombre está tomado, elegí otro y actualizá fly.toml
fly deploy
fly open
```
Nota: Fly **no permite renombrar** una app; si se quiere otro nombre, crear app nueva y redeployar (hacerlo antes de crear el volumen de la DB en Fase 1).

## Pendiente para Fase 1
- [ ] Volumen persistente para la DB (`[mounts]` en fly.toml).
- [ ] Secrets (`SIGNUP_CODE`, `SESSION_SECRET`) con `fly secrets set`.
- [ ] Migrar Lugar A y redeploy.

## Dominio
Opción gratis: **DigitalPlat FreeDomain** (`.dpdns.org`, `.us.kg`, etc.) apuntando al deploy vía Cloudflare DNS. Ej.: `superappfinanzas.dpdns.org`. Ver `docs/HERRAMIENTAS-EVALUADAS.md`. Para uso personal alcanza; si se vuelve comercial, migrar a dominio propio.
