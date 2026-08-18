# core/

<!-- huella: 846a2e4ea7fa -->

Resumen: Núcleo compartido: SQLite (schema + migraciones M1–M15 + backups), workspaces del grupo familiar (D2) y su UI. Auth y theme viven en subcarpetas propias.

## Buscar acá si

- la base de datos: schema, una migración nueva (SIEMPRE aditiva), "database is locked", backups y retención (`BACKUP_RETENTION`, `DB_PATH`)
- grupo familiar / espacios compartidos: crear, unirse, código de invitación, resolver el workspace activo
- el badge Personal/Familiar o el switcher del sidebar se comportan raro
- un import circular entre core y core/auth

## Qué hay acá

- `db.py` — conexión, schema completo, las 15 migraciones y el backup automático con retención. El hub del repo: lo usan 35 archivos.
- `workspaces.py` — lógica del grupo familiar D2 (crear/unirse/salir, código hasheado SHA-256, multi-owner, resolver el activo).
- `workspaces_ui.py` — badge de modo, switcher del sidebar, activación desde la sesión.

## Trampas

- `db.py` DEBE seguir siendo **módulo plano** (no paquete): los tests monkeypatchean sus atributos (p. ej. `BACKUP_DIR`).
- `init_db()` corre **una sola vez por proceso** (`st.cache_resource` en `app.py`). Correrla en cada rerun causó el crash `database is locked` del 4/8/2026 en producción.
- Los guards de migración importan: M4 re-disparada post-M8 desvinculó workspaces en producción (incidente del 17/7, reparado con M8.5).
- Hay dos imports **diferidos** hacia `core.workspaces` dentro de `db.py` para no cerrar el ciclo con `core/auth`.

## Estado

- **Funciona:** todo en producción (Fly.io).

## Proximo paso

Evaluar mover los contextvars a un `core/context.py` neutral para eliminar el ciclo core↔core/auth (propuesta 4, a confirmar con Franco).

La crónica del módulo vive en `bitacora_de_trabajo.md`.
