# core/

<!-- huella: 3324e77c0c7a -->

Resumen: Núcleo compartido: SQLite (schema + migraciones M1–M22 + reparaciones únicas + backups), workspaces del grupo familiar (D2) y su UI. Auth, theme y la API HTTP (`api/`, Fase A) viven en subcarpetas propias.

## Buscar acá si

- la base de datos: schema, una migración nueva (SIEMPRE aditiva), "database is locked", backups y retención (`BACKUP_RETENTION`, `DB_PATH`)
- el webhook de WhatsApp, la API HTTP o nginx → **`core/api/`** (y `api.py`, `deploy/nginx.conf` en la raíz)
- grupo familiar / espacios compartidos: crear, unirse, código de invitación, resolver el workspace activo
- el badge Personal/Familiar o el switcher del sidebar se comportan raro
- un import circular entre core y core/auth → **cortado** el 27/8/2026 con `context.py`
- quién es el usuario o el workspace activo, desde lógica sin Streamlit → `context.py`
- "reinicié la app y se deshizo lo que cambié" (una categoría reclasificada, una subcategoría vaciada) → reparaciones únicas de `db.py` (`_NIVEL_REPARACIONES`, `PRAGMA user_version`)
- tolerar una base sin cierta migración → `es_tabla_faltante()` en `db.py` (y nada más ancho)

## Qué hay acá

- `db.py` — conexión, schema completo, las migraciones (M1–M15 y M17–M22; la M16 quedó liberada por ADR-0009), las reparaciones únicas (M3, M7, M8.5), `es_tabla_faltante()` y el backup automático con retención. El hub del repo.
- `workspaces.py` — lógica del grupo familiar D2 (crear/unirse/salir, código hasheado SHA-256, multi-owner, resolver el activo).
- `workspaces_ui.py` — badge de modo, switcher del sidebar, activación desde la sesión.
- `context.py` — los contextvars de usuario y workspace activos. **No importa nada del proyecto**, y esa es su razón de ser.
- `api/` — servidor HTTP stdlib y canal de Meta (Fase A, ADR-0008). Bitácora propia.

## Trampas

- `db.py` DEBE seguir siendo **módulo plano** (no paquete): los tests monkeypatchean sus atributos (p. ej. `BACKUP_DIR`).
- `init_db()` corre **una sola vez por proceso** (`st.cache_resource` en `app.py`). Correrla en cada rerun causó el crash `database is locked` del 4/8/2026 en producción.
- Los guards de migración importan: M4 re-disparada post-M8 desvinculó workspaces en producción (incidente del 17/7, reparado con M8.5).
- Hay dos imports **diferidos** hacia `core.workspaces` dentro de `db.py` para no cerrar el ciclo con `core/auth`.
- `context.py` **no puede importar nada de `core/`**. Si lo hace, vuelve el ciclo que vino a cortar. Hay un test que lo verifica (`tests/test_context.py`).
- `context.py` es la **única** fuente de los contextvars. Las fachadas `core/auth/current_user.py` y `current_workspace.py` se borraron el 22/9/2026 (nadie las usaba en producción); `tests/test_context.py` falla si aparece otro `ContextVar` en `core/` o `places/`.
- ⚠️ **Una reparación de datos corre una vez, no en cada arranque** (22/9/2026). M3, M7 y M8.5 son `UPDATE`/`DELETE` de filas y corrían en cada deploy y cada vez que Fly despertaba la máquina: M3 volvía a pasar "Compra Divisa" a Inversión aunque el usuario la reclasificara, M7 rellenaba subcategorías vaciadas a propósito y M8.5 **borraba** la fila buena de un espacio si aparecía una huérfana. Ahora van detrás de `PRAGMA user_version` (`_NIVEL_REPARACIONES = 1`), marcado dentro de la misma transacción. **Toda migración nueva que toque filas va detrás de esa marca** (subí el nivel). Tests: `tests/test_db_reparaciones_unicas.py`.
- M5 tenía el mismo guard incompleto que M4 el 17/7: su rebuild no conoce `workspace_id`. Desde el 22/9 exige además `not _es_post_d2(tabla)`.
- **`except Exception` está prohibido para "la base no tiene la migración"** (trampa 36): se usa `es_tabla_faltante(exc)` y todo lo demás se relanza. Antes, un error cualquiera sacaba los ajustes de la cartera sin avisar.

## Estado

- **Funciona:** todo en producción (Fly.io).
- **20/10/2026 (Fase D, paso 5, sin desplegar):** **M22**, aditiva: `resumenes` (detalle en JSON, estado, lo pagado). El índice único por gasto de `emparejamientos` (M21) suma el rol `resumen`. ⚠️ M21 y M22 todavía no se desplegaron: hasta entonces sus índices se pueden editar en el lugar; **después**, `IF NOT EXISTS` ignora cualquier cambio y un rol nuevo necesita una migración nueva.
- **19/10/2026 (Fase D, paso 4a, sin desplegar):** **M21**, aditiva: `banco_filas` (en centavos, `UNIQUE` fecha + monto + saldo), `emparejamientos` (FK con `ON DELETE CASCADE` y dos índices únicos parciales: uno a uno por gasto y por fila; el de gasto incluye el rol `anterior` de la guarda del corte), `reglas_comercio`, `reglas_tipo` y `saldos_declarados`.
- **19/10/2026 (Fase D, paso 2, desplegado):** **M19** `lotes` + `lote_operaciones` (propuesta → aplicado → deshecho; cada fila tocada con su antes y su después; `fila_id` sin FK a propósito, para no trabar el borrado de un gasto desde la app) y **M20** `gasto_cuentas` (cuenta y bruto, FK con `ON DELETE CASCADE`). Aditivas, no tocan filas: no suben `_NIVEL_REPARACIONES`. **M16 liberada** (ADR-0009).
- **16/10/2026 (Fase B):** **M18**, aditiva: `whatsapp_salientes` (cola de salida: tipo, texto, `id_origen` UNIQUE para el dedupe, `enviado_en`, `error`).
- **15/10/2026 (Fase A, sin desplegar):** **M17**, aditiva: `whatsapp_mensajes` (dedupe por wamid + rastro para `deshacer`) y `whatsapp_estado` (`ultimo_entrante`, `pendiente`). No toca filas existentes, así que no sube `_NIVEL_REPARACIONES`. La **M16 queda reservada** para las cuentas de la Fase 5 (ADR-0006).
- **14/10/2026:** `core/market_data/` se retiró junto con Inversiones (ADR-0007); solo lo usaba la cartera. Las tablas `cartera_*` y sus migraciones (M9–M15) **siguen en `db.py` a propósito**: producción tiene los datos. No borrarlas sin el OK de Franco.

## Proximo paso

Nada pendiente. La propuesta 4 (mover los contextvars a un `core/context.py` neutral) se **ejecutó el 27/8/2026**: el ciclo core↔core/auth está cortado y `core/db.py` y los seis módulos de lógica de Finanzas dejaron de arrastrar bcrypt.

La crónica del módulo vive en `bitacora_de_trabajo.md`.
