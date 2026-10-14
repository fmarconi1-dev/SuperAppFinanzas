# core/ — Núcleo compartido

**Estado:** ⬜ No iniciado · **Se implementa en:** Transversal (base de Fase 0/1)

Lógica compartida por todos los *lugares*. Vive una sola vez para evitar duplicación y refactors.

Subcarpetas:
- `auth/` — autenticación (bcrypt, rate-limit, sesión HMAC). Origen: Mis-Finanzas-App.
- `db/` — conexión SQLite, migraciones, backups. Origen: Mis-Finanzas-App.
- `config/` — configuración central: universos de tickers, umbrales, mapeos ARS↔USD.
- ~~`market_data/`~~ — retirado el 14/10/2026 junto con Inversiones (ADR-0007); está en el historial de git.
- `theme/` — tema visual unificado ('Cosmic Slate') y helpers de UI. **Aplicar la skill `ui-ux-web-moderno` acá.**

---
_Antes de tocar este módulo: leé `/GUIA-DE-TRABAJO.md` y `/ESTADO.md` en la raíz. Al terminar, actualizá `bitacora_de_trabajo.md` de esta carpeta._
