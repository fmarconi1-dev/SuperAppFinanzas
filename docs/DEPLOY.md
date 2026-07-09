# DEPLOY

> Placeholder. Se completa en Fase 0/1, cuando se confirme el hosting y exista `app.py`.

## Hosting recomendado (MVP): Fly.io
Ver comparativa y costos en `../PLAN DE TRABAJO - Superapp Finanzas.md` §5.

## Pasos (a documentar al ejecutar)
- [ ] Confirmar app/proyecto de Fly.io.
- [ ] Dockerfile + fly.toml (heredar de Mis-Finanzas-App).
- [ ] Volumen persistente para la DB.
- [ ] Secrets (`SIGNUP_CODE`, `SESSION_SECRET`).
- [ ] Deploy "hola mundo" (Fase 0) → deploy Lugar A (Fase 1).

## Dominio
Opción gratis: **DigitalPlat FreeDomain** (`.dpdns.org`, `.us.kg`, etc.) apuntando al deploy vía Cloudflare DNS. Ej.: `superappfinanzas.dpdns.org`. Ver `docs/HERRAMIENTAS-EVALUADAS.md`. Para uso personal alcanza; si se vuelve comercial, migrar a dominio propio.
