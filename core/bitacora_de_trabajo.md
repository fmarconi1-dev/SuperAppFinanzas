# Bitácora — core/ (núcleo compartido)

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: 2026-10-19 -->

## Estado del módulo
**Fase de implementación:** en producción desde Fase 1
**Situación:** ✅ en producción

## Registro

## 2026-07-10 — Núcleo compartido poblado (Fase 1)
- **Autor:** Claude (Fable 5), con Franco.
- **Qué:** `core/auth/` (auth, session_tokens, current_user, login UI — ex Mis-Finanzas), `core/db.py` (módulo plano, no paquete: los tests monkeypatchean sus atributos, p. ej. BACKUP_DIR), `core/theme/` (_styles, _theme, _responsive, _logo — "Cosmic Slate").
- **Por qué:** el `core/` compartido es la clave anti-refactor: auth/db/theme viven una sola vez y cada lugar los importa.
- **Estado:** ✅ en producción. Nota: `core/db` DEBE seguir siendo módulo plano.

## 2026-09-22 — Reparaciones únicas, tolerancia acotada y fin de las fachadas
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `db.py`: M3, M7 y M8.5 pasan a correr **una sola vez** (`_NIVEL_REPARACIONES` en `PRAGMA user_version`, dentro de la transacción de `_migrate`); M5 recibe el guard post-D2; nuevo `es_tabla_faltante()`; docstrings al día; imports muertos fuera. `market_data/`: `_errores.py` (`FuenteNoDisponible`, `ERRORES_DE_RED`), caché negativa solo con respuesta válida en Docta y Yahoo, `except` acotados en precios/mep/indices. `auth/`: fachadas `current_user.py`/`current_workspace.py` borradas. `theme/`: `inline_logo`/`try_set_logo` borradas.
- **Por qué:** auditoría del 22/9 — las reparaciones pisaban decisiones del usuario en cada reinicio de Fly; la caché negativa convertía "Docta/Yahoo no contestó" en "no existe" para siempre; los `except Exception` escondían bugs (trampas 16, 19, 36).
- **Estado:** ✅ suite 865 passed, 0 skipped; huella de números de producción idéntica antes/después.

## 2026-10-15 — API HTTP y M17 (Fase A, ADR-0008)
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `core/api/` nuevo: `servidor.py` (ThreadingHTTPServer en 127.0.0.1:8000, firma HMAC de Meta, dedupe por wamid, cola con un solo hilo trabajador, 503 sin configuración) y `whatsapp_meta.py` (único módulo que habla con Meta: verificación, eventos, envío de texto partido en 4096, números canónicos sin el 9). `db.py`: M17 (`whatsapp_mensajes`, `whatsapp_estado`), aditiva.
- **Por qué:** cargar gastos desde el celular con costo cero (sin plantillas, sin tarjeta).
- **Estado:** ✅ tests en verde y smoke test del proceso real; sin desplegar.

## 2026-10-19 — M19 y M20 (Fase D, paso 2)
- **Autor:** Claude (Opus 5.5), con Franco.
- **Qué:** `db.py` suma **M19** (`lotes`, `lote_operaciones`) y **M20** (`gasto_cuentas`), las dos aditivas (`CREATE TABLE IF NOT EXISTS`). La M16 queda liberada (ADR-0009 reemplazó las cuentas de ADR-0006).
- **Por qué:** los lotes de la conciliación y el bruto de los gastos con cuenta (`docs/PLAN-FASE-D.md`).
- **Estado:** ✅ suite 677 passed, 0 skipped. Sin desplegar.
