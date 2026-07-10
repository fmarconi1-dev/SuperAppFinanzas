# Bitácora — core/ (núcleo compartido)

> Registro cronológico del trabajo de este módulo. **Una entrada por sesión.**
> Formato de cada entrada: `fecha · autor (Claude+modelo / Franco) · qué se hizo · por qué · estado`.
> Regla: no cerrar una sesión sin dejar la entrada acá y actualizar `/ESTADO.md` en la raíz.

<!-- ultima_actualizacion: — -->

## Estado del módulo
**Fase de implementación:** Fase 0/1
**Situación:** ⬜ No iniciado

## Registro

_(sin entradas todavía — este módulo aún no se implementó; ver `/ROADMAP.md`)_

## 2026-07-10 — Núcleo compartido poblado (Fase 1)
- **Autor:** Claude (Fable 5), con Franco.
- **Qué:** `core/auth/` (auth, session_tokens, current_user, login UI — ex Mis-Finanzas), `core/db.py` (módulo plano, no paquete: los tests monkeypatchean sus atributos, p. ej. BACKUP_DIR), `core/theme/` (_styles, _theme, _responsive, _logo — "Cosmic Slate").
- **Por qué:** el `core/` compartido es la clave anti-refactor: auth/db/theme viven una sola vez y cada lugar los importa.
- **Estado:** ✅ en producción. Nota: `core/db` DEBE seguir siendo módulo plano.
