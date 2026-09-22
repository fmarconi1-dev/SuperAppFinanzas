# Superapp de Finanzas

App web personal que unifica, en un solo lugar y bajo un login único:

- **🏠 Finanzas Personales** — ingresos, gastos, presupuesto, grupo familiar (ex `Mis-Finanzas-App`).
- **📈 Inversiones** — (1) **cartera** nativa: posiciones, rendimiento por el método del patrimonio, TIR, renta fija con cronogramas, benchmark contra el mercado; (2) **mercado en vivo** (placeholder, Fase 6). El scoring se retiró el 5/8/2026 (ADR-0002).

> **Estado global (22/9/2026):** en producción en Fly.io (`superapp-finanzas`). Fases 0–4 cerradas; la **Fase 5** (captura *source-first* del Lugar A, ADR-0006) está aprobada y sin arrancar. La foto al día está siempre en `ESTADO.md`; el plan original, en `PLAN DE TRABAJO - Superapp Finanzas.md` (histórico: la numeración de fases vigente es la de `ROADMAP.md`).

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
| `places/inversiones/` | Lugar B — cartera + mercado_vivo (placeholder). |
| `data/` | Datos locales **(nunca se commitea)**. |
| `jobs/` | Procesos batch. Vacío desde que se retiró el scoring (5/8/2026). |
| `tests/` | El gate: pytest en CI. |
| `docs/` | Documentación viva: arquitectura, deploy, runbook, decisiones (ADR), premortems. |
| `.github/workflows/` | CI/CD y batch. |

## Stack

Python 3.11 · Streamlit · SQLite · Plotly/pandas · pytest · Docker + Fly.io. Dependencias fijadas en `requirements.lock` (verificado en 3.11; leé su cabecera antes de regenerarlo).

## Cómo se corre

Siempre con el Python del venv (3.11), **no** con el `python` del sistema — en la máquina de Franco hay también 3.12 y 3.14, y la 3.14 no tiene dependencias:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py     # la app
.venv\Scripts\python.exe -m pytest -q                # la suite (local: 0 skipped)
```

Deploy y operación: `docs/DEPLOY.md` y `docs/RUNBOOK.md`.
