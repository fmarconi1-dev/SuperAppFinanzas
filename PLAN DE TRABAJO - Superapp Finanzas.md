# Plan de Trabajo — Superapp de Finanzas

> 📜 **Documento histórico (9/7/2026).** Es el plan con el que arrancó el proyecto y se conserva tal cual. La numeración de fases y el estado vigentes están en `ROADMAP.md` y `ESTADO.md` (p. ej., acá "Fase 5" es Mercado en vivo; hoy es la Fase 6).

> Documento maestro. Pensado para arrancar la ejecución en otro chat (Fable 5). Junto con `Premortem - Superapp Finanzas.html` forma la base del proyecto.
> **Fecha:** 9 de julio de 2026 · **Autor:** Franco (fmarconi1-dev)

---

## 1. Veredicto de prefactibilidad (honesto)

**Es factible, pero no como "una super-app nueva que se construye de cero".** Lo viable —y lo inteligente— es tratarlo como una **integración progresiva de activos que ya funcionan**, no como un producto nuevo.

Lo que juega a favor:
- Ya tenés **dos de los tres pilares en producción**: Mis-Finanzas-App corre en Fly.io (multiusuario, con auth, tests de reconciliación y backups) y Scoring-Inversiones se publica solo vía GitHub Actions + Pages. Eso es infraestructura y código maduros, no ideas.
- Ambos comparten stack (**Python + Streamlit/HTML**), así que la fusión es realista.
- La lógica de cartera y renta fija está **validada en tus Excel** y tenés la skill de Solidum para actualizarlos. Es capital reutilizable.

Lo que hay que mirar de frente (del premortem):
- El riesgo #1 no es técnico, es de **alcance**: querer "una sola app unificada de verdad" desde el arranque estanca el proyecto en refactor. La app unificada es la **meta**, no el punto de partida.
- El **dato de mercado argentino** (MEP, precios de bonos/CEDEARs/ONs) no tiene una fuente gratis y estable. La sección Cartera "en vivo" es la parte más frágil y la que hay que prometer con más cautela.
- **Hosting:** DonWeb *shared* no corre Streamlit. Hay que elegir infra apropiada antes de codear (ver §5).
- **Privacidad:** al sumar los Excel de patrimonio, el monorepo tiene que ser **privado** y con candados anti-leak.

**Conclusión:** verde para arrancar, con la condición de ejecutar por fases y congelar el alcance del MVP a "integrar lo que ya existe bajo un login". Escalar a multiusuario/SaaS queda explícitamente para después.

---

## 2. Visión objetivo (el "norte")

Una sola aplicación con **dos lugares**:

### 🏠 Lugar A — Finanzas Personales
Todo lo que hoy tiene `Mis-Finanzas-App` (dashboard, transacciones, libro diario, presupuesto mensual, configuración, auth multiusuario) **más** las mejoras del backlog `MEJORAS.md` del repo. Es el lugar más maduro: entra casi tal cual.

### 📈 Lugar B — Inversiones / Mercado
Estructura **triple**:

1. **Dashboard de cartera** — posiciones actuales, valor, variaciones, resultado realizado/no realizado, y **análisis enriquecido**: estructura por tipo de activo (acciones/bonos/CEDEARs/cripto), exposición por sector, TIR esperada de la renta fija, riesgo fija-vs-variable, benchmark vs. SPY/Merval. Es la web-ización de tu Excel `Inversiones.xlsx` + `Renta fija ARG.xlsx`.
2. **Análisis y Scoring** — lo que hoy publica `Scoring-Inversiones` en Pages (fundamental + técnico + "consagrada"), embebido como sección.
3. **Mercado en vivo** — cotizaciones/seguimiento en tiempo (casi) real. Es la sección más nueva y la que depende de resolver la fuente de datos de mercado (ver riesgo #4 del premortem).

> Todo esto es el estado **completo**. El MVP no lo construye entero: lo deja encuadrado y va llenando los lugares por fases (§7).

---

## 3. Decisiones tomadas (de este chat)

| Tema | Decisión |
|---|---|
| Arquitectura | Monorepo, aplicación unificada con "lugares" (núcleo compartido + secciones). |
| Hosting | Evaluar alternativas → recomendación en §5 (Fly.io para el MVP). |
| Prioridad MVP | **Integrar lo existente** bajo un login común primero; features nuevas después. |
| Renta fija / opciones | **Excel-in-the-loop** al inicio (la app lee los Excel); portar a Python después, con reconciliación fila-a-fila. |
| Multiusuario | Preparado en el diseño, **no** construido ahora. La app arranca "para uno". |
| Repo | **Privado** desde el commit 0. |

---

## 4. Arquitectura técnica y estructura del monorepo

Principio rector: **un `core/` compartido + un package por lugar**, para que la integración no exija reescribir cada app. Cada sección puede evolucionar sin romper a las otras.

```
superapp-finanzas/
├── README.md                    Puerta de entrada: qué es, cómo se corre, mapa del repo
├── BITACORA.md                  Changelog narrativo global (qué se hizo, cuándo, por qué)
├── MEJORAS.md                   Backlog priorizado global (hereda el de Mis-Finanzas)
├── ROADMAP.md                   Las fases de §7, con estado
├── claude.md                    Contexto para agentes IA (reglas del repo, convenciones)
├── .gitignore                   Estricto: data/, *.db, *.xlsx, .env, backups/, secrets
├── .pre-commit-config.yaml      Hook que BLOQUEA commitear *.xlsx, *.db, .env (anti-leak)
├── requirements.txt             Dependencias unificadas
├── pyproject.toml               Config del paquete / tooling (ruff, pytest)
│
├── app.py                       Entry point único: auth gate + navegación entre "lugares"
│
├── core/                        Núcleo compartido (lógica pura, testeable)
│   ├── auth/                    Auth de Mis-Finanzas (bcrypt, rate-limit, sesión HMAC)
│   ├── db/                      Conexión SQLite, migraciones, backups
│   ├── config/                  Config central (universos, umbrales, mapeos de tickers)
│   ├── market_data/             Proveedores de precios (yfinance + fuente ARG a definir)
│   └── theme/                   Tema visual unificado ("Cosmic Slate") + helpers UI
│
├── places/                      Un package por "lugar"
│   ├── finanzas/                LUGAR A — ex Mis-Finanzas-App
│   │   ├── core/                budget, categorias, diario, metrics, parsers, transactions
│   │   ├── views/               dashboard, transacciones, diario, mensual, configuracion
│   │   └── bitacora_de_trabajo.md
│   │
│   └── inversiones/             LUGAR B — estructura triple
│       ├── cartera/             (1) Dashboard de cartera: posiciones, TIR, sectores, riesgo
│       │   ├── ingest.py        Parser de movimientos del broker (ex Excel "Movimientos")
│       │   ├── renta_fija.py    Flujos de fondos / TIRs (ex "Renta fija ARG.xlsx")
│       │   ├── opciones.py      Black-Scholes (ex "opciones argy.xlsx")
│       │   └── bitacora_de_trabajo.md
│       ├── scoring/             (2) ex Scoring-Inversiones (fundamental + técnico)
│       │   ├── technicals.py    Indicadores
│       │   ├── scoring.py       Scores y clasificación
│       │   └── bitacora_de_trabajo.md
│       └── mercado_vivo/        (3) Cotizaciones / seguimiento en vivo
│           └── bitacora_de_trabajo.md
│
├── data/                        [NO se commitea] DB, Excel de trabajo, backups
│   ├── finanzas.db
│   ├── excels/                  Inversiones.xlsx, Renta fija ARG.xlsx, opciones argy.xlsx
│   └── backups/
│
├── jobs/                        Procesos batch (corren en GitHub Actions, no en la web)
│   └── build_snapshot.py        Batch EOD del scoring (hereda el de Scoring-Inversiones)
│
├── tests/                       El gate del proyecto
│   ├── test_reconciliacion.py   Caja app == Caja Excel (finanzas) — heredado
│   ├── test_kpis.py             KPIs cuadran — heredado
│   ├── test_parsers.py          Parsers — heredado
│   └── test_cartera_recon.py    NUEVO: cartera app == cartera Excel, fila por fila
│
├── docs/                        Documentación viva
│   ├── DEPLOY.md                Guía de despliegue (hosting elegido)
│   ├── RUNBOOK.md               Operación: backups, restore, monitoreo
│   ├── ARQUITECTURA.md          Decisiones de diseño (ADR livianos)
│   ├── DATOS-MERCADO-ARG.md     Investigación de fuentes de precios locales
│   └── premortems/              Este premortem + los futuros
│
└── .github/workflows/
    ├── batch-scoring.yml        Cron EOD (hereda el de Scoring), commitea snapshot
    ├── tests.yml                Corre pytest en cada push (gate)
    └── deploy.yml               Despliegue al hosting elegido
```

Notas de diseño:
- **`core/` es la clave anti-refactor.** Auth, tema y config viven una sola vez. Cada "lugar" los importa.
- **El scoring sigue siendo batch.** No se mete su cálculo dentro del servidor web: sigue corriendo en GitHub Actions (gratis, robusto) y la web solo lee el snapshot. Así no rompés lo que hoy funciona (mitiga riesgo del premortem sobre "unificar dos stacks distintos").
- **Los Excel viven en `data/` (ignorado por git).** La app los lee; no se suben nunca.

---

## 5. Hosting — comparativa y recomendación

DonWeb **shared** (el link que pasaste, `web-hosting`) es cPanel/PHP/MySQL: **no** corre apps Python de larga ejecución como Streamlit. Para esta stack las opciones reales son:

| Opción | Costo aprox. (jul-2026) | Pros | Contras |
|---|---|---|---|
| **Fly.io** (actual) | ~USD 2–5/mes (máquina shared 256–512 MB + volumen 1 GB + IPv4) | Ya lo conocés y Mis-Finanzas ya está ahí; Docker; volumen persistente; región São Paulo | Pago en USD; pay-as-you-go |
| **Render** | Free (750 h/mes, se duerme) o Hobby ~USD 7/mes | Free tier real; PostgreSQL gratis 90 días; simple | El free "duerme" (cold start); pago en USD |
| **Railway** | ~USD 5/mes (Hobby, sin free permanente) | Buen DX; usage-based | Sin free permanente; restricciones de deploy en free |
| **DonWeb Cloud Server / VPS** | desde ~$4.600 ARS/mes | Pago en ARS; control total; infra local | **Administrás vos** nginx/TLS/systemd/backups (carga operativa alta) |
| Streamlit Community Cloud | Gratis | Cero setup | Pensado para apps públicas; **no apto** para datos financieros privados |

**Recomendación:** **consolidar en Fly.io para el MVP.** Mis-Finanzas ya vive ahí, el patrón Docker + volumen ya lo tenés resuelto, y mover el scoring y la cartera al mismo deploy es incremental. DonWeb VPS solo tiene sentido si tu prioridad es pagar en pesos y tener todo en infra local —a costa de administrar el servidor vos mismo, que es justo el cuello de botella que el premortem marca como peligroso. Dejá esa migración para cuando la app sea estable y valga la pena.

---

## 6. Cómo se reutiliza lo existente

| Activo actual | Destino en el monorepo | Esfuerzo |
|---|---|---|
| `Mis-Finanzas-App` (app.py, core/, ui/) | `places/finanzas/` + su auth/db/theme suben a `core/` | Bajo — copiar y re-cablear imports |
| Tests de Mis-Finanzas (reconciliación, KPIs, parsers) | `tests/` — se mantienen como gate | Bajo — deben quedar verdes tras mover |
| `MEJORAS.md` de Mis-Finanzas | `MEJORAS.md` global + a ejecutar en Lugar A | — |
| `Scoring-Inversiones` (src/, data/build_snapshot.py) | `places/inversiones/scoring/` + `jobs/build_snapshot.py` | Bajo — ya es modular |
| GitHub Actions del scoring (cron EOD + Pages) | `.github/workflows/batch-scoring.yml` | Bajo — adaptar rutas |
| `Inversiones.xlsx` (cartera, parser movimientos, config tickers) | Fuente de `places/inversiones/cartera/ingest.py` (Excel-in-the-loop) | Medio |
| `Renta fija ARG.xlsx` (FF, TIRs, duales/CER) | `places/inversiones/cartera/renta_fija.py` (lee Excel; portar después) | Medio-alto |
| `opciones argy.xlsx` (Black-Scholes) | `places/inversiones/cartera/opciones.py` | Bajo |
| Skill `actualizar-valuaciones-solidum` | Mantiene los Excel de renta fija actualizados que la app lee | — |
| Estética "Cosmic Slate" | `core/theme/` — tema único de toda la superapp | Bajo |

---

## 7. Orden del proyecto — roadmap por fases

Cada fase termina con algo **usable y desplegado**. No se pasa a la siguiente sin cerrar la anterior (mitiga el riesgo de alcance infinito).

**Fase 0 — Cimientos (candados antes de codear).**
Crear el repo **privado**, `.gitignore` + pre-commit hook anti-`.xlsx/.db` (probado con un commit de prueba), estructura de carpetas vacía, README/BITACORA/ROADMAP iniciales, hosting elegido con un "hola mundo" Streamlit desplegado. *Salida: repo vivo y deploy vacío funcionando.*

**Fase 1 — Lugar A migrado (Finanzas Personales).**
Mover Mis-Finanzas-App a `places/finanzas/`, subir auth/db/theme a `core/`, dejar los tests verdes, desplegar. *Salida: tu app actual, igual pero dentro del monorepo, online.*

**Fase 2 — Shell unificado + Lugar B (Scoring embebido).**
Navegación con login único entre "lugares". Embeber el scoring (Lugar B.2) leyendo el snapshot que genera el batch en Actions. *Salida: un login que lleva a Finanzas y a Scoring.*

**Fase 3 — Cartera (Lugar B.1) en modo Excel-in-the-loop.**
La app lee `Inversiones.xlsx` y muestra el dashboard de cartera: posiciones, variaciones, resultado, estructura por activo/sector, riesgo fija-vs-variable. Renta fija y opciones se leen del Excel. **Test de reconciliación cartera app == Excel.** *Salida: tu cartera, online, con los mismos números que la planilla.*

**Fase 4 — Mejoras del Lugar A.**
Ejecutar el backlog `MEJORAS.md` sobre Finanzas Personales. *Salida: Lugar A pulido.*

**Fase 5 — Mercado en vivo (Lugar B.3) + fuente de datos ARG.**
Resolver la fuente de precios local (investigación en `docs/DATOS-MERCADO-ARG.md`), implementar cotizaciones en vivo, conectar la cartera a precios automáticos. *Salida: la sección más nueva; la más incierta.*

**Fase 6 (opcional, futuro) — Portar la matemática del Excel a Python.**
Módulo por módulo (FF de renta fija, TIRs, B&S), cada uno con reconciliación fila-a-fila contra el Excel antes de retirar la planilla. *Salida: independencia del Excel.*

**Fase 7 (opcional, futuro) — Multiusuario / escalar.**
Solo si querés abrirla a otros: revisar aislamiento de datos, planes, costos.

---

## 8. Régimen de README y bitácoras

Heredá el sistema que ya usás (es bueno):
- **README.md (raíz):** qué es, cómo se corre local, cómo se despliega, mapa del repo, tabla de docs. Se actualiza cuando cambia algo estructural.
- **BITACORA.md (raíz):** changelog **narrativo** global — qué se hizo, cuándo y **por qué**. Una entrada por sesión de trabajo relevante.
- **`bitacora_de_trabajo.md` por módulo** (como en Scoring-Inversiones): cada package tiene la suya, con el detalle fino de ese componente.
- **MEJORAS.md:** backlog priorizado. Lo que no entra en la fase actual va acá.
- **ROADMAP.md:** las fases de §7 con estado (☐ / ◐ / ☑).
- **docs/:** DEPLOY, RUNBOOK, ARQUITECTURA (decisiones), premortems.
- **claude.md:** reglas del repo para agentes IA (convenciones, "no commitear datos", "tests verdes antes de tocar UI", etc.).

Regla de oro: **ningún merge a `main` sin actualizar BITACORA y con los tests verdes.**

---

## 9. GitHub como centro de verdad

- **Repo privado** `superapp-finanzas`. El scoring puede quedar como repo público aparte si querés mantener el tablero abierto, pero el monorepo con cartera es privado.
- **Ramas:** `main` siempre desplegable; trabajo en ramas `fase-N/...` o `feat/...`; merge vía PR (aunque trabajes solo, el PR te obliga a revisar el diff → última defensa anti-leak).
- **CI como gate:** `tests.yml` corre pytest en cada push. Si rojea, no se mergea.
- **Batch en la nube:** el snapshot del scoring lo genera GitHub Actions (no tu PC), como ya hacés.
- **Datos nunca en git:** `.gitignore` + pre-commit hook. Antes de cada push, `git status` no debe mostrar `data/`, `*.xlsx` ni `*.db`.

---

## 10. Riesgos (del premortem) → mitigaciones ya incorporadas

| Riesgo | Dónde se mitiga en este plan |
|---|---|
| Refactor "una sola app" se come el proyecto | `core/` compartido + packages; Fase 1 mueve, no reescribe (§4, §7) |
| Fuga de datos al repo | Repo privado + `.gitignore` + pre-commit hook + PRs (§9, Fase 0) |
| Deploy como cuello de botella | Hosting decidido en Fase 0; recomendación Fly.io (§5) |
| Dato de mercado ARG poco fiable | Cartera arranca Excel-in-the-loop; "en vivo" se aísla en Fase 5 (§7) |
| Perder la lógica del Excel | Excel-in-the-loop + test de reconciliación antes de portar (Fase 3, 6) |
| Alcance infinito / burnout | Fases cerradas, cada una desplegable; alcance MVP congelado (§7) |
| Multiusuario prematuro | Explícitamente Fase 7, opcional y futura (§7) |

---

## 11. Cómo arrancar el próximo chat (Fable 5)

Prompt sugerido para abrir la ejecución:

> "Vamos a ejecutar la **Fase 0** del `PLAN DE TRABAJO - Superapp Finanzas.md`. Creá la estructura de carpetas del monorepo `superapp-finanzas` según §4, con README/BITACORA/ROADMAP/claude.md iniciales, `.gitignore` estricto y un `.pre-commit-config.yaml` que bloquee commitear `*.xlsx`, `*.db` y `.env`. Después preparamos el deploy 'hola mundo' en Fly.io. No toques todavía el código de las apps existentes."

Tené a mano: acceso a los repos `Mis-Finanzas-App` y `Scoring-Inversiones`, los cuatro Excel, y tus credenciales de Fly.io.

---

*Fin del plan. Complementa: `Premortem - Superapp Finanzas.html` (informe visual) y `Premortem - transcripcion.md`.*
