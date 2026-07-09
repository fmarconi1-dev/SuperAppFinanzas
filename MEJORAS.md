# MEJORAS — backlog e ideas a futuro

Todo lo que **no** entra en la fase actual vive acá. Es el "estacionamiento" de ideas: se anota, se prioriza, y se saca cuando le toca. Sirve para no meter alcance de más en la fase en curso (ver premortem: riesgo de alcance infinito).

Prioridad: 🔴 alta · 🟡 media · 🟢 baja / oportunista
Estado: 💡 idea · 📋 planeada · 🔵 en curso · ✅ hecha

---

## Skills y agentes a integrar en el flujo

Estas capacidades ya existen como skills/agentes y deben usarse en las fases indicadas.

### `ui-ux-web-moderno` — 🔴 obligatoria en toda tarea de UI
Inteligencia de diseño UX/UI web moderno (tokens de color, tipografía, spacing, dashboards financieros, micro-interacciones, dark mode, accesibilidad, y aplicación en Streamlit vía CSS injection).
- **Cuándo:** siempre que se trabaje el tema (`core/theme`), dashboards, formularios, o se toque "cómo se ve/siente" la app.
- **Fases:** transversal, con foco en Fase 1 (unificar estética "Cosmic Slate"), Fase 3 (dashboard de cartera) y Fase 5 (mercado en vivo).

### `agente-tesis-inversion` — 🟡 ayudante de ideas de inversión (a futuro)
Genera tesis de inversión institucional sobre un ticker (múltiplos + DCF, deuda, comparables, 5 escenarios, técnicos).
- **Idea:** conectar la salida del **scoring** con este agente. Cuando el scoring marque un ticker como "atractivo" o "consagrado", ofrecer un botón/flujo que dispare una tesis profunda sobre ese papel como ayuda a la decisión.
- **Fases:** después de Fase 2 (scoring embebido). No es parte del MVP.
- **Nota:** es apoyo al análisis, no recomendación automática de inversión.

### `actualizar-valuaciones-solidum` — 🟡 mantenimiento de datos de renta fija
Actualiza las valuaciones de los Excel de renta fija (soberanos, CER, LECAPs, duales, provinciales, ONs) a una fecha dada (tasas BCRA, cierres IAMC, MEP, flujos de fondos).
- **Cuándo:** para mantener frescos los Excel que la cartera lee en modo Excel-in-the-loop (Fase 3).

---

### `gauss314/skills` — 🔴 datos de mercado (resuelve el bloqueante de datos ARG)
Colección pública de skills (estándar SKILL.md, MIT) para consumir datos de mercado. **Su sección Argentina resuelve el riesgo #4 del premortem** (fuente de datos local). Instalación: `npx skills add gauss314/skills --skill <nombre>`.
- **Argentina (gratis):** `bcra-macro` (MEP/CCL/CER/UVA/tasas, oficial), `data912` (mercado en vivo ~20s: acciones/CEDEARs/bonos/opciones/MEP/CCL), `byma` (panel + bonos + cronograma de amortización), `mae` (renta fija + flujos de fondos para TIR), `cafci` (FCI), `indec` (inflación/macro, oficial).
- **Globales:** `yahoo-finance` (ya en uso), `sec-data`, `morningstar` (CEDEARs), `tradingview`, `google-finance`, `fred-macro`.
- **Herramientas:** `option-pricing` (BS/binomial/MC/griegas/IV → reemplaza `opciones argy.xlsx`), `backtesting` (ratios de riesgo, Altman Z, Piotroski, DuPont, Markowitz → enriquece el scoring).
- **Cuándo:** `bcra-macro`/`byma`/`mae` en Fase 3 (cartera); `data912` en Fase 5 (mercado en vivo); `option-pricing` al portar opciones (Fase 6); `sec-data`/`morningstar`/`backtesting` como apoyo del scoring y del agente de tesis.
- **Cómo:** diseñar `core/market_data/` con capa de abstracción por proveedor + caché + **fallback a carga manual**. Priorizar las fuentes oficiales (`bcra-macro`, `indec`); tratar las comunitarias (`data912`/`byma`/`mae`) con caché y monitoreo. Detalle y caveats en `docs/DATOS-MERCADO-ARG.md`.

## Mejoras de producto — Lugar A (Finanzas Personales)

> Heredar y revisar el `MEJORAS.md` del repo original `Mis-Finanzas-App` al llegar a la Fase 4. Pegar acá los ítems vigentes.

- 🟡 💡 Portar el backlog de UX pendiente del repo original.
- 🟢 💡 _(agregar a medida que surjan)_

---

## Mejoras de producto — Lugar B (Inversiones / Mercado)

### Cartera (B.1)
- 🔴 💡 Análisis enriquecido: exposición por sector e industria, TIR esperada de la parte de renta fija, duration/riesgo, correlación fija-vs-variable.
- 🟡 💡 Comparación de la cartera contra benchmarks (SPY, Merval) en distintos plazos.
- 🟡 💡 Alertas de vencimientos de bonos/ON (reusar la lógica de la hoja "VTO MES" del Excel).
- 🟢 💡 Simulador "qué pasa si" (agregar/quitar posiciones y ver impacto en estructura).

### Scoring (B.2)
- 🟡 💡 Escalar el universo de tickers (hoy ~20).
- 🟡 💡 Métricas de solvencia propias para bancos/financieras (Tier 1) — hoy se excluye el D/E.
- 🟢 💡 Histórico de scores por ticker (evolución en el tiempo).

### Mercado en vivo (B.3)
- 🔴 💡 **Resolver la fuente de datos de mercado ARG** (bloqueante de esta sección). Investigación en `docs/DATOS-MERCADO-ARG.md`.
- 🟡 💡 Watchlist configurable con cotizaciones y variaciones intradía.

---

## Plataforma / infra

- 🟡 💡 Migrar de Fly.io a DonWeb VPS si se prioriza pago en ARS e infra local (evaluar costo operativo — ver premortem).
- 🟢 💡 Multiusuario / SaaS (Fase 7): tenancy, planes, aislamiento de datos, billing.
- 🟢 💡 App móvil / PWA.
- 🟢 💡 Notificaciones (email/push) para alertas de cartera y vencimientos.

---

## Cómo usar este documento
1. Idea nueva fuera del alcance actual → se anota acá con prioridad y estado.
2. Al planificar una fase → se revisa este backlog y se suben los ítems que correspondan al ROADMAP.
3. Al completar un ítem → se marca ✅ (o se mueve a `BITACORA.md`).
