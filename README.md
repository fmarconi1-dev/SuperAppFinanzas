# Superapp de Finanzas

App web personal que unifica, en un solo lugar y bajo un login único, tres cosas que hoy viven separadas:

- **🏠 Finanzas Personales** — seguimiento de ingresos, gastos, presupuesto (ex `Mis-Finanzas-App`).
- **📈 Inversiones / Mercado** — con estructura triple: (1) dashboard de cartera, (2) análisis y scoring, (3) mercado en vivo.

> **Estado global:** ⬜ Fase 0 (cimientos). Este repo arranca como **esqueleto**: estructura, documentación y reglas de trabajo. Todavía no hay código de aplicación. El plan completo está en `PLAN DE TRABAJO - Superapp Finanzas.md`.

---

## ⚠️ Antes de tocar nada (obligatorio para cualquier Claude o persona)

Este proyecto está pensado para ser continuado por **varias conversaciones/Claudes distintos, de a uno por vez**. Para que no se pisen, hay un protocolo. Leé en este orden:

1. **`ESTADO.md`** — la foto de dónde está el proyecto AHORA y qué sigue. Es lo primero que se lee y lo último que se actualiza.
2. **`MAPA.md`** — el índice del código: qué carpeta resuelve qué, sin releer el repo. Generado por `scripts/indexar.py`; consultas puntuales con `python .mapa/buscar.py "<término>"`.
3. **`GUIA-DE-TRABAJO.md`** — el protocolo de trabajo: cómo tomar una tarea, cómo dejar el handoff, qué no hacer.
4. **`ROADMAP.md`** — las fases del proyecto y su estado.
5. **`claude.md`** — reglas duras para agentes IA (resumen operativo).

---

## Mapa del repositorio

| Ruta | Qué es |
|---|---|
| `PLAN DE TRABAJO - Superapp Finanzas.md` | Documento maestro: prefactibilidad, arquitectura, hosting, fases. |
| `Premortem - Superapp Finanzas.html` | Análisis de riesgos (informe visual). |
| `README.md` | Este archivo. |
| `ESTADO.md` | **Foto actual + handoff.** Se actualiza cada sesión. |
| `EN-HUMANO.md` | Diario **en lenguaje llano**, sin tecnicismos, de qué se fue haciendo. Para leer sin ser técnico. |
| `GUIA-DE-TRABAJO.md` | Protocolo para trabajar sin pisarse. |
| `ROADMAP.md` | Fases y estado. |
| `BITACORA.md` | Changelog narrativo global. |
| `MAPA.md` + `.mapa/` | Índice vivo del código (generado; cada carpeta tiene su `BITACORA.md` router). |
| `MEJORAS.md` | Backlog + ideas a futuro (incluye uso de skills/agentes). |
| `claude.md` | Reglas para agentes IA. |
| `core/` | Núcleo compartido: auth, db, config, market_data, theme. |
| `places/finanzas/` | Lugar A — Finanzas Personales. |
| `places/inversiones/` | Lugar B — cartera + scoring + mercado_vivo. |
| `data/` | Datos locales **(nunca se commitea)**. |
| `jobs/` | Procesos batch (GitHub Actions). |
| `tests/` | El gate: pytest en CI. |
| `docs/` | Documentación viva: arquitectura, deploy, runbook, decisiones (ADR), premortems. |
| `.github/workflows/` | CI/CD y batch. |

## Stack previsto

Python 3.11 · Streamlit · SQLite · Plotly/pandas · yfinance · pytest · Docker + Fly.io (hosting recomendado para el MVP). Detalle y alternativas de hosting en `PLAN DE TRABAJO - Superapp Finanzas.md` §5.

## Cómo se corre

_(Se completará en Fase 1, cuando exista `app.py`. Por ahora el repo es solo estructura.)_
