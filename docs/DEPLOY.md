# DEPLOY

## Hosting confirmado (MVP): Fly.io
Ver comparativa y costos en `../PLAN DE TRABAJO - Superapp Finanzas.md` §5. Decisión: consolidar en Fly.io (Mis-Finanzas ya vive ahí).

## Fase 0 — hola mundo (archivos ya en el repo)
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

#
