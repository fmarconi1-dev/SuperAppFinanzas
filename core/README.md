# core/ — Núcleo compartido

**Estado:** ⬜ No iniciado · **Se implementa en:** Transversal (base de Fase 0/1)

Lógica compartida por todos los *lugares*. Vive una sola vez para evitar duplicación y refactors.

Subcarpetas:
- `auth/` — autenticación (bcrypt, rate-limit, sesión HMAC). Origen: Mis-Finanzas-App.
- `db/` — conexión SQLite, migraciones, backups. Origen: Mis-Finanzas-App.
- `config/` — configuración central: universos de tickers, umbrales, mapeos ARS↔USD.
- `market_data/` — proveedores de precios con capa de abstracción + caché + fallback manual. Implementación de referencia: skills de `gauss314/skills` (`bcra-macro`, `data912`, `byma`, `mae`, `yahoo-finance`). Ver `docs/DATOS-MERCADO-ARG.md`.
- `theme/` — tema visual unificado ('Cosmic Slate') y helpers de UI. **Aplicar la skill `ui-ux-web-moderno` acá.**

---
_Antes de tocar este módulo: leé `/GUIA-DE-TRABAJO.md` y `/ESTADO.md` en la raíz. Al terminar, actualizá `bitacora_de_trabajo.md` de esta carpeta._
