# jobs/ — Procesos batch

**Estado:** ⬜ No iniciado · **Se implementa en:** Fase 2

Procesos que corren en **GitHub Actions** (no en la web ni en tu PC).
- `build_snapshot.py` — batch EOD del scoring (hereda el de Scoring-Inversiones); recorre el universo, calcula scores y escribe el snapshot que lee la web.

---
_Antes de tocar este módulo: leé `/GUIA-DE-TRABAJO.md` y `/ESTADO.md` en la raíz. Al terminar, actualizá `bitacora_de_trabajo.md` de esta carpeta._
