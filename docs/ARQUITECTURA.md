# Arquitectura

## Idea en una línea
`core/` compartido (auth, db, config, market_data, theme) + un package por *lugar* en `places/`. La app unificada es la **meta**, no el arranque: primero se migra cada pieza, después se integra.

## Los dos lugares
- **Lugar A — Finanzas Personales** (`places/finanzas/`): ex Mis-Finanzas-App.
- **Lugar B — Inversiones/Mercado** (`places/inversiones/`), estructura triple:
  - `cartera/` — dashboard de posiciones + análisis (ex Excel).
  - `scoring/` — análisis fundamental + técnico (ex Scoring-Inversiones).
  - `mercado_vivo/` — cotizaciones en vivo.

## Principios de diseño
1. **`core/` evita el refactor infinito.** Auth, tema y config viven una sola vez; cada lugar los importa. (Mitiga el riesgo #1 del premortem.)
2. **El scoring es batch, no web.** Se calcula en GitHub Actions (`jobs/build_snapshot.py`) y la web solo lee el snapshot. No se rompe lo que hoy funciona gratis.
3. **Excel-in-the-loop antes de portar.** La cartera y la renta fija arrancan leyendo los Excel validados; portar a Python se hace después, con reconciliación fila-a-fila.
4. **Datos separados del código.** Todo dato personal vive en `data/` (gitignored). El repo es privado.
5. **Multiusuario preparado, no construido.** El diseño no impide escalar, pero no se paga ese costo hasta la Fase 7.

## Flujo de datos (previsto)
```
Broker (Excel) ─┐
                ├─> data/excels ─> places/inversiones/cartera ─┐
Excel renta fija┘                                              │
                                                               ├─> app.py (Streamlit, login único) ─> Fly.io
yfinance ─> jobs/build_snapshot.py (Actions) ─> snapshot ─> scoring ┘
SQLite (data/finanzas.db) ─> places/finanzas ─────────────────┘
```

## Referencias
- Plan maestro: `../PLAN DE TRABAJO - Superapp Finanzas.md`
- Riesgos: `../Premortem - Superapp Finanzas.html`
- Decisiones puntuales: `decisiones/`
