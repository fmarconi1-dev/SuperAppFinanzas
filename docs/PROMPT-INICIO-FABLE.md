# Prompt de inicio — chat con Fable 5

Copiá y pegá el bloque de abajo en un chat nuevo con Fable 5 para arrancar la ejecución del proyecto. Antes, dale acceso a la carpeta `SuperAppFinanzas/`.

---

> Soy Franco. Vamos a trabajar en mi proyecto **Superapp de Finanzas**, un monorepo que unifica mis finanzas personales y mis inversiones/mercado en una sola app web. El repo ya existe como esqueleto (sin código todavía) en la carpeta `SuperAppFinanzas/` dentro de mi carpeta de trabajo, y es un repo git (rama `main`, lo subo con GitHub Desktop). Dale acceso a esa carpeta antes de empezar.
>
> **Antes de proponer o hacer nada, leé en este orden y confirmame que entendiste:**
> 1. `ESTADO.md` — foto actual y próximo paso.
> 2. `GUIA-DE-TRABAJO.md` — protocolo para trabajar sin pisar a otro Claude.
> 3. `ROADMAP.md` — las fases.
> 4. `claude.md` — reglas duras.
> 5. `PLAN DE TRABAJO - Superapp Finanzas.md` — plan maestro.
> 6. `docs/HERRAMIENTAS-EVALUADAS.md` y `docs/DATOS-MERCADO-ARG.md` — herramientas y fuentes de datos ya evaluadas.
>
> **Explicame "en humano" seguido:** cada vez que completes un avance importante (y como mínimo una vez por sesión), actualizá `EN-HUMANO.md` y dame en el chat un resumen en lenguaje llano, sin tecnicismos: qué se hizo, para qué me sirve y qué sigue. Antes de pedirme que apruebe un paso grande, explicámelo primero en criollo.
>
> **Regla permanente (ya está en el régimen):** en **cada fase**, antes de codear, revisá `docs/HERRAMIENTAS-EVALUADAS.md` y los repos listados, y reutilizá lo que aplique (gráficos con `lightweight-charts`, datos con `gauss314/skills`, cálculo, etc.) en vez de reinventar. Si aparece un repo/skill nuevo, evaluálo y anotálo ahí.
>
> **Datos de mercado:** usá las skills de `https://github.com/gauss314/skills` según haga falta (`bcra-macro`, `data912`, `byma`, `mae`, `indec` para Argentina; `option-pricing`, `backtesting` como herramientas; `yahoo-finance`, `sec-data` globales). Priorizá las oficiales (`bcra-macro`, `indec`) y tratá las comunitarias con caché + fallback manual.
>
> **Reglas que no se rompen:** nunca commitear datos (`data/`, `*.xlsx`, `*.db`, `.env`); una fase a la vez, cerrada y desplegable; el scoring se calcula en batch (GitHub Actions), no en el servidor web; usá la skill `ui-ux-web-moderno` en toda tarea de UI; el agente no ejecuta trades ni mueve dinero; documentación y commits en español; al cerrar cada sesión actualizás la bitácora del módulo, `EN-HUMANO.md` y `ESTADO.md`.
>
> **Tarea de hoy: completar la Fase 0 (Cimientos).** Falta: (1) primer commit del esqueleto y publicar el repo como privado; (2) instalar y **probar** el pre-commit hook intentando commitear un `.xlsx` (debe bloquearlo); (3) confirmar hosting (Fly.io para el MVP; opción de URL gratis con FreeDomain) y desplegar un "hola mundo" Streamlit sin lógica. Confirmame con cuál de los tres arrancamos antes de tocar nada. Todavía **no** migres el código de mis apps existentes (eso es Fase 1).

---

_Actualizá este prompt si cambia el estado del proyecto (por ejemplo, cuando la Fase 0 esté cerrada, la "tarea de hoy" pasa a ser la Fase 1)._
