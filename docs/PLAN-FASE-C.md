# Plan — Fase C: tablero "secretario" y rebranding (ADR-0008)

**Objetivo:** que al abrir la app lo primero sea **tu día**: cómo vas con la plata este mes, qué tenés esta semana y qué tenés pendiente. Y que la app deje de llamarse "Radar Financiero" / "Superapp de Finanzas", porque ya es tu secretario.

**Lo que ya funciona no se toca:** las cinco pestañas de Finanzas (Dashboard, Transacciones, Diario, Mensual, Configuración), el login, el WhatsApp y los briefings quedan iguales. Esta fase **agrega** una pantalla de inicio y **cambia la marca**.

**Fuera de alcance:** crear o editar eventos desde la app (eso ya se hace por WhatsApp con `evento:`) · conciliación (Fase D) · datos de mercado (son de Gemini, por mail) · app móvil nativa (Fase 8).

## Qué vas a ver

### Inicio (la pantalla nueva, la primera al entrar)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Buen día, Franco                                     vie 17/10/2026 │
├──────────────┬──────────────┬──────────────┬────────────────────────┤
│ Gastos oct.  │ Ingresos oct.│ Balance      │ Movimientos            │
│ $3.289.998   │ $4.865.500   │ +$1.575.502  │ 41                     │
│ ▲ 4% vs sep. │ ▼ 2% vs sep. │              │                        │
├──────────────┴──────────────┴─────┬────────┴────────────────────────┤
│ Esta semana                       │ Tareas pendientes               │
│ HOY · vie 17/10                   │ ☐ Pagar seguro   ⚠ vencida 14/10│
│   15:00  Dentista                 │ ☐ Llamar al contador            │
│ sáb 18/10                         │ ☐ Renovar DNI    vence 25/10    │
│   Todo el día  Cumple de Juan     │                                 │
│ lun 20/10                         │                                 │
│   09:00  Reunión                  │                                 │
├───────────────────────────────────┴─────────────────────────────────┤
│ Últimos movimientos                              Ver todo en Finanzas│
│ 14/10  Transportes            −$13.000                              │
│ 13/10  Compra Divisa          −$48.000                              │
├─────────────────────────────────────────────────────────────────────┤
│ Secretario: 1 mensaje esperando a que le escribas  ·  agenda al día │
└─────────────────────────────────────────────────────────────────────┘
```

En el celular se apila en este orden: fecha → KPIs (de a dos) → semana → tareas → movimientos.

- **KPIs del mes:** son **los mismos números** que te da `resumen` por WhatsApp (`comandos.totales_mes`), con la variación contra el mes anterior escrita y con flecha, no solo con color.
- **Esta semana:** de hoy a 7 días, agrupada por día y con hoy destacado. Sale del Apps Script (`resumen_semana`), igual que el comando `agenda`.
- **Tareas pendientes:** las vencidas arriba y marcadas (⚠ + texto, no solo rojo). **Tildar una la completa en Google Tasks** (acción `completar_tarea`, que el Apps Script ya tiene): se tacha recién cuando Google confirma.
- **Últimos movimientos:** los 5 últimos, con un link a Finanzas.
- **Estado del Secretario:** una línea que dice si hay briefings esperando por la ventana de 24 h (`whatsapp_salientes` sin enviar) y si la agenda está conectada. Así ves de un vistazo si algo quedó trabado.

### Estados (cada bloque los tiene resueltos)

| Bloque | Cargando | Vacío | Error |
|---|---|---|---|
| KPIs | — (es la base local, instantáneo) | "Todavía no hay movimientos este mes" + botón a Transacciones | el error real (no se tapa) |
| Semana / tareas | placeholder del mismo alto (Google tarda 1–3 s) | "Sin eventos de hoy a 7 días" / "Nada pendiente 🎉" | "No pude traer tu agenda: <motivo>" + botón **Reintentar**. Si la agenda no está configurada, lo dice y el resto de la pantalla anda igual |

La agenda se guarda **5 minutos** en caché (`st.cache_data(ttl=300)`) para no llamar a Google en cada click, con un botón **Actualizar**. Completar una tarea limpia la caché.

## Rebranding

| Qué | Hoy | Después |
|---|---|---|
| Nombre | "Radar Financiero" (título y login), "Superapp de Finanzas" (pestaña del navegador) | **el que elijas** (decisión 1) |
| Logo | `assets/logo.svg` (el de Radar) | nuevo SVG simple, en el color de acento |
| Navegación | una sola página, "Finanzas" | **Inicio** (default) · **Finanzas** |
| Íconos | emojis (📊 ➕ 📒 🎯 ⚙️) | **Material Symbols** (una sola familia, `:material/...:`); los emojis quedan solo en mensajes y toasts |
| Login | "Radar Financiero" | el nombre nuevo + una línea de qué es |
| Tema | Cosmic Slate (dark, violeta, Inter / Space Grotesk / JetBrains Mono) | **se extiende, no se pisa** (decisión 3): mismos tokens `--cs-*`, se suman los que falten |

**Lo que no cambia:** la URL (`superapp-finanzas.fly.dev`, Fly no deja renombrar apps; un nombre propio en la URL es por dominio, aparte), el nombre del bot de WhatsApp (se cambia en el panel de Meta si querés, gratis), y la base de datos.

## Criterios de diseño (skill `ui-ux-web-moderno`)

- **Sistema, no decisiones sueltas:** todo color por token semántico (`--cs-positive`, `--cs-negative`, `--cs-accent`…), cero hex sueltos en componentes. Los gráficos toman los mismos colores desde `core/theme/_theme.py`.
- **Jerarquía:** un solo número "rey" (el balance del mes, más grande); el resto subordinado. Etiqueta chica arriba, cifra 28–36 px peso 600 con **cifras tabulares**, contexto abajo.
- **Verde/rojo nunca solos:** siempre con signo (+/−) y flecha o texto.
- **Componentes propios con `st.html`** para la semana, las tareas y las KPI cards, estilados con **keyed containers** (`st.container(key=...)` → `.st-key-...`), sin clases `st-emotion-cache-*`. Los selectores `data-testid` quedan centralizados en `core/theme/_styles.py`.
- **Accesibilidad:** contraste ≥ 4.5:1 en el tema real, foco visible, objetivos táctiles ≥ 44 px (el tilde de las tareas), nada que dependa solo del color, `prefers-reduced-motion` respetado.
- **Sin animaciones de entrada:** con el modelo de rerun de Streamlit se repetirían en cada click.
- **Probado a 375 px** (celular) además de escritorio.

## Decisiones — ✅ tomadas por Franco el 17/10/2026

> **Nombre: Secretario.** Logo: lo diseña Claude. Paleta: **se mantiene Cosmic Slate**. **Inicio es la pantalla principal.** **Se completan tareas desde el tablero.** Lo de abajo queda como registro de las opciones.


1. **Nombre de la app.** Lo elegís vos. Ideas, por si sirven: "Secretario" (como el bot), "Mi Secretario", o un nombre propio. Va en el título, el login, la pestaña del navegador y el logo.
2. **Logo:** lo diseño yo (SVG simple, monograma o símbolo, en el color de acento), **o** traés uno.
3. **Paleta:** **mantener Cosmic Slate** (recomendado: ya es un sistema completo y probado), o cambiar solo el color de acento (violeta hoy) por otro.
4. **Inicio como pantalla principal** (recomendado), o dejarlo como una pestaña más dentro de Finanzas.
5. **Completar tareas desde el tablero** (recomendado: el Apps Script ya lo soporta), o solo mostrarlas.

## Diseño técnico

| Archivo | Qué |
|---|---|
| `places/inicio/` (lugar nuevo) | `home.py` (la pantalla) y `core/` puro: armar los datos de la vista (agrupar la semana por día, ordenar tareas con vencidas arriba, KPIs con variación contra el mes anterior). Usa `places/finanzas/core` (totales, últimos movimientos) y `core/api/google.py` (agenda), sin duplicar lógica |
| `core/api/google.py` | + `completar_tarea(lista_id, tarea_id)` |
| `core/theme/` | tokens que falten, componentes HTML (`kpi_card`, `semana`, `tareas`), logo nuevo |
| `app.py` | `st.navigation` con **Inicio** (default) y **Finanzas**; `page_title` / `page_icon` nuevos |
| `core/auth/login.py`, `places/finanzas/home.py` | nombre nuevo; íconos Material en las pestañas |
| `assets/` | logo nuevo (el viejo queda en el historial de git) |

Streamlit corre en el mismo contenedor que la API, así que lee las mismas variables (`GOOGLE_WORKSPACE_WEBHOOK_URL`, `GOOGLE_WORKSPACE_SECRET`): no hay secretos nuevos.

## Orden de trabajo (cada paso desplegable)

> **Progreso (17/10/2026):** ✅ 1 (marca "Secretario", logo nuevo, íconos Material en Finanzas, navegación Inicio/Finanzas) y ✅ 2 (Inicio con KPIs del mes contra el mismo período del anterior y últimos movimientos), sin desplegar. De paso se arregló un error de `resumen` en un mes sin movimientos (`KeyError: 'pasivos'`). Sigue el 3.
>
> **Progreso (17/10/2026, más tarde):** ✅ 3 (semana y tareas en el Inicio, caché de 5 min, Actualizar, estados), ✅ 4 (tilde para completar en Google Tasks, solo con `ok: true`) y ✅ 5 (estado del Secretario). Sin desplegar. **Falta el 6:** mirarlo en el navegador, en escritorio y a 375 px, y pulirlo con el checklist de la skill.

1. **Rebranding base:** nombre, títulos, logo, íconos Material, navegación Inicio/Finanzas (Inicio vacío con un "próximamente"). Chico, se ve enseguida.
2. **Inicio con finanzas:** KPIs del mes con variación, últimos movimientos, estados. Sin Google todavía.
3. **Inicio con agenda:** semana y tareas, caché de 5 min, Actualizar, estados de carga, vacío y error.
4. **Completar tareas** desde el tablero.
5. **Estado del Secretario** (cola de salida, agenda conectada).
6. **Pulido** contra el checklist de la skill y prueba a 375 px.

## Tests (gate: suite completa en verde, 0 skipped)

- Puros: agrupar eventos por día (incluido el de todo el día y el que cruza la medianoche), orden de tareas (vencidas, con fecha, sin fecha), variación contra el mes anterior (mes sin datos → sin variación, no "inf%").
- **KPIs del Inicio = `resumen`** sobre la misma base (un test que compare los dos).
- `AppTest` (como `test_smoke_pantallas.py`): Inicio abre con agenda falsa, sin agenda configurada y con la agenda caída; Finanzas sigue abriendo igual.
- Completar tarea: solo se tacha con `ok: true`; un rechazo muestra el error y no tacha.
- Marca: no queda "Radar Financiero" en la interfaz (test que lo busque en `app.py`, `places/` y `core/`).

## Cierre de la fase

Bitácoras selladas, `EN-HUMANO.md`, `ESTADO.md`, `ROADMAP.md`. Commit en `main`; push y deploy, Franco. Verificación a ojo en el navegador (escritorio y celular).
