# BITÁCORA — changelog narrativo global

<!-- huella: c6d27008885c -->

Resumen: Raíz del monorepo: entry point (`app.py`: login único + navegación entre lugares), deploy (Dockerfile/fly.toml) y toda la gobernanza (ESTADO, ROADMAP, MEJORAS, guías).

## Buscar acá si

- el arranque de la app, la navegación entre lugares o la restauración de sesión → `app.py`
- deploy, Docker, Fly.io → `Dockerfile`, `fly.toml`, `docker-entrypoint.sh`, `docs/DEPLOY.md` y `docs/RUNBOOK.md`
- el arranque de la API de WhatsApp o nginx en el contenedor → `api.py`, `deploy/nginx.conf`, `docker-entrypoint.sh` (código en `core/api/`)
- cómo se trabaja en este repo → `GUIA-DE-TRABAJO.md`, `claude.md`, `/MAPA.md`
- qué se hizo y qué sigue → `ESTADO.md` (foto), este archivo (crónica), `EN-HUMANO.md` (en llano)
- un aviso de Streamlit en `fly logs` que parece error, o la config del servidor → `.streamlit/config.toml`

## Crónica

Qué se hizo, cuándo y **por qué**, a nivel proyecto. Una entrada por sesión relevante. Lo fino de cada módulo va en su `bitacora_de_trabajo.md`.

---

## 2026-10-18 — Diseño de la Fase D: conciliación desde el Secretario
**Autor:** Claude (Opus 5.5), con Franco.

- La Fase D original y la Fase 5 (ADR-0006) se fusionan. Se estudiaron los archivos reales de Franco: extracto de Galicia (Excel) y 9 resúmenes AMEX/VISA (PDF con texto). Se leen sin IA. Gemini gratis queda solo para fotos.
- **Por qué cambia ADR-0006 §1:** no hacen falta cuentas. La caja de ahorro manda, y algunas filas del banco son contenedores que se desarman: el pago de tarjeta en el detalle del resumen, la compra de dólares en los consumos en USD, la extracción en efectivo. Así se evita el doble conteo sin migrar la tabla más sensible.
- Verificado: los pagos de tarjeta del extracto coinciden al centavo con su resumen. La diferencia es la percepción RG 5617 del 30%, que se paga y se devuelve, y va a una línea neutra.
- Saldo real = caja + FIMA + efectivo. Ajuste inicial de +$82.758,25 (18/10/2026) para arrancar parejos.
- Todo el diseño está en `docs/PROMPT-INICIO-FASE-D.md`. Los archivos reales quedan en `data/extractos/` (ignorado por git).

## 2026-10-15 — Fase A: gastos por WhatsApp (ADR-0008)
**Autor:** Claude (Opus 5.5), con Franco.

- **Prueba previa, contra Meta de verdad:** con el número de prueba y **sin medio de pago**, el texto libre **llegó** al teléfono de Franco. Antes hubo un falso éxito: con el número cargado en el panel sin el 9, Meta *aceptó* el envío a `54…` (HTTP 200 + id) y no lo entregó nunca. **Aceptar no es entregar.**
- **Código nuevo:** `core/api/` (servidor stdlib + canal de Meta), `places/finanzas/core/comandos.py` (parser y comandos), `api.py`, `deploy/nginx.conf`, M17 en `core/db.py`. Contenedor: nginx reparte el 8501 (API en 8000, Streamlit en 8502); `fly.toml` intacto; el entrypoint conserva el seed y relanza la API si se cae.
- **Desvíos del plan, con motivo:** parser de montos propio (`parse_currency_estricto` borra todos los puntos: `1.5` → 15); formato de número argentino resuelto en producción (lista del panel con el 9, envío sin el 9, reintento con el 9 solo ante 131030); los estados `failed` de Meta se loguean en vez de ignorarse; `core/` no importa `places/` (la lógica llega inyectada desde `api.py`).
- **Puesta en producción (15/10):** deploy desde `main`; backup previo (flyctl estaba roto: `fly.exe` en 0 bytes, reinstalado); webhook verificado; hubo que suscribir la app a la cuenta de WhatsApp Business (`POST /{waba}/subscribed_apps`); el primer mensaje real llegó y la respuesta rebotó (131030) por mandar con el 9 → corregido.
- **Verificado:** suite completa en verde; `api.py` levantado como proceso real (health, verificación de Meta, POST firmado → mensaje registrado; el envío con token falso lo rechazó Meta con 190 y quedó en el log). **No verificado:** el contenedor (no hay Docker local): se prueba en el deploy.

## 2026-10-14 — Se retira el lugar Inversiones (ADR-0007)
**Autor:** Claude (Opus 5.5), a pedido de Franco: *"es algo que no se utiliza… creo que es momento de dejarlo ir"*.

- **Fuera:** `places/inversiones/` (cartera, paneles, placeholder de mercado en vivo), `core/market_data/` (solo lo usaba la cartera), `scripts/verificar_docta.py`, la página "Inversiones" de `app.py` y ~550 tests (`test_cartera_*`, `test_market_data*` y los tramos de cartera de smoke, backup/restore e importes ilegibles).
- **Adentro, a propósito:** las tablas `cartera_*` y sus migraciones en `core/db.py`. Producción tiene los movimientos reales; sacar el esquema abre una puerta a perder datos sin vuelta. Siguen viajando en los backups. Borrarlas es una decisión aparte.
- `test_db_concurrencia` ya no mira la vista de cartera: revisa todo `places/` (y exige encontrar al menos un `backup_db()`, trampa 41).
- ROADMAP: Fases 6 (Mercado en vivo) y 7 (portar la matemática del Excel de inversiones) descartadas. Fase 5 Paso 1 anotada: el parser de la Cartera que iba a reusar está en el historial de git.
- **Suite 359 passed, 0 skipped** (incluye el smoke que abre `app.py` completo). Sin commitear ni desplegar.

---

## 2026-09-27 — El backup llevaba un mes sin correr; y tres mejoras chicas
**Autor:** Claude (Opus 5.5), autónomo con el OK de Franco.

- 🔴 **Hallazgo:** la última copia externa de producción era del **26/8**. La tarea programada "Backup Superapp Finanzas" **no existía en la PC** (ESTADO.md la daba por confirmada desde el 27/8) y, aunque existiera, dependía de la sesión de `fly auth login`, que vence: el 23/9 pidió login a mitad de la corrida. **Nada avisaba.**
- **Arreglado:** copia sacada en el momento (406 transacciones, 693 movimientos, integridad ok). La misma copia confirmó que el deploy del 23/9 quedó bien: `user_version = 1`, sin filas huérfanas, "Compra Divisa" en Inversión. Los scripts pasan a usar un **deploy token** limitado a la app (`scripts/guardar_token_fly.ps1`; fuera del repo y de OneDrive, vence al año), consultan a fly **sin poder quedarse esperando un login** (`< NUL`), cortan con el motivo si no pueden hablar con Fly, y **dejan un aviso en el Escritorio** cuando fallan. `estado_backup.ps1` revisa además que la tarea exista y que haya token. Probado de verdad: con un token inválido falla en 2 s, deja el motivo en la bitácora y el aviso; una corrida buena lo borra.
- **Queda en manos de Franco** (credencial y configuración permanente de su PC): correr `guardar_token_fly.ps1` y `programar_backup.ps1`.
- **A — el aviso de `form_motivo` en `fly logs`:** no era un error. Streamlit avisa una vez por proceso cuando un widget tiene default y además se precarga por `session_state`, y acá las dos cosas son intencionales (chips de motivos frecuentes + motivo "pegajoso" después de agregar un gasto). Sacar el `index=` lo callaba pero rompía lo pegajoso: se apagó ese aviso en `.streamlit/config.toml`, con el porqué y un test.
- **B — tests de login y contraseñas** (`tests/test_auth.py`, 30 tests): hash, alta, cambio de clave, rate-limit y la pantalla con `AppTest`. Incluye que el usuario `local` de M1, sin contraseña, no pueda entrar. **Hallazgo abierto:** el login distingue mayúsculas y el celular capitaliza la primera letra; queda como propuesta, porque toca autenticación.
- **C — trampa 27:** el benchmark ya no mezcla en silencio una serie sin dividendos: prefiere la caché ajustada, y si no hay, avisa en pantalla y no la cachea. Con Yahoo real, SPY y Merval siguen saliendo ajustados: el caso normal no cambió.
- **Gate:** huella de números sobre una copia del backup de hoy, antes y después: idéntica. Suite **909 passed, 0 skipped**.

---

## 2026-09-22 — Auditoría + limpieza entre fases (sin features nuevas)
**Autor:** Claude (Opus 5.5), con Franco.

- **Contexto:** casi un mes sin sesiones. El estado real no coincidía del todo con el handoff: el trabajo del 27/8 estaba commiteado y pusheado (commits `aa`/`aaa` del 26/8 y 3/9) aunque `ESTADO.md` lo daba "pendiente de commit", y el deploy del 27/8 **sí salió** (confirmado por Franco). Baseline: **743 passed, 0 skipped**.
- **Auditoría primero, arreglos con el OK de Franco.** Siete bugs reales, ninguno disparado hoy en producción (verificado contra el backup del 26/8, en modo lectura):
  - **B1 🔴 — la pantalla de Cartera se caía con una tasa devengada.** `_resolver` leía `fecha_val` antes de que se asignara (variable de la función de afuera, que `test_nombres_definidos` no ve). Apretar "Aplicar" en *Instrumentos que devengan una tasa* la tiraba **para siempre**, porque no había cómo quitar la tasa. Latente desde M11 (29/7). Arreglado, más botón **Quitar**, y la precedencia pasó a **broker antes que devengado** (decisión de Franco).
  - **B2 🟠 — la caché negativa confundía "no contestó" con "no existe"** en Docta (cuota de 15/día) y Yahoo (rate-limit, y corre en cada carga): un bono o ticker quedaba "sin dato" para siempre y la pantalla decía que era esperable. Nuevo `core/market_data/_errores.py` (`FuenteNoDisponible`).
  - **B3 🟠 — el indexador del mapa ignoraba el `.gitignore` en Windows** (`\` vs `/`): el `MAPA.md` commiteado listaba `Borrar/` y leía los `.db-shm` de los backups de producción.
  - **B4 🟡 — M3, M7 y M8.5 corrían en cada arranque** y pisaban decisiones del usuario (M8.5 hasta podía borrar la fila buena de un espacio). Ahora son únicas, marcadas con `PRAGMA user_version`; M5 recibió el guard post-D2 que le faltaba.
  - **B5 🟡 — importes ilegibles entraban como $0 en silencio** (Finanzas y Cartera; en Cartera, además, `1,234.56` se leía como 1,23).
  - **B6 🟢 — la app decía "Mercado en vivo: llega en Fase 5"** (hoy es la 6).
  - **B7 🟠 (encontrado arreglando B5) — el CLI de reimportación de Finanzas estaba roto** por un `sys.path` heredado de Mis-Finanzas-App; la suite no lo veía.
- **Olores:** unos 12 `except Exception` achicados (red → `ERRORES_DE_RED`; base sin migración → `es_tabla_faltante()`; lo demás se ve); 38 imports muertos en `view.py` y 9 funciones sin uso borradas (una, `previsiones_anuales`, con un bug propio); fachadas `core/auth/current_user.py` y `current_workspace.py` borradas; un test (`test_db_concurrencia`) que desde el split pasaba en blanco.
- **Red nueva:** `test_smoke_pantallas.py` abre Finanzas, Cartera y el shell con `AppTest` (verificado: con B1 reintroducido, falla con el error exacto) · `test_closures_definidos.py` · `test_db_reparaciones_unicas.py` · `test_indexar.py` · `test_importes_ilegibles.py`. `coverage` instalado en el venv: **78%** total; lo más flojo, login/contraseñas (21–29%).
- **Gate de números:** huella de Cartera y Finanzas sobre una **copia** del backup de producción, antes y después de todos los cambios: **idéntica**, peso por peso (capital aportado US$ 11.534, realizado $5.432.244, 344 transacciones, etc.).
- **Limpieza:** `docs/PROMPT-INICIO-FASE-4.md` y `PROMPT-INICIO-FABLE.md` borrados; 4 ramas locales mergeadas borradas (las de `origin` las borra Franco); los dos `.tar.gz` del 18/8 a la Papelera. Documentos sincronizados (ESTADO, ROADMAP, MEJORAS, README, claude.md, índice de ADRs, prompt de Fase 5).
- **Trampas nuevas (37–42)** en las fichas de sus carpetas y en `docs/PROMPT-INICIO-FASE-5.md`.
- **Una corrección a mi propio informe:** reporté el `.gitignore` con caracteres rotos; no lo estaba — era PowerShell leyéndolo con la codificación equivocada.

**Estado al cierre:** suite **865 passed, 0 skipped**. Commit local listo; push y deploy, de Franco.

---

## 2026-08-27 (3ª sesión) — El diagnóstico que cambia el rumbo del Lugar A (ADR-0006)
**Autor:** Claude (Opus 5), con Franco.

- **La pregunta de Franco:** el mayor problema de las apps de finanzas personales es que el usuario deja de cargar y el costo de ponerse al día se vuelve prohibitivo. ¿Cómo se resuelve?
- **El diagnóstico habitual está mal planteado.** No es que el usuario se olvide —eso lleva a recordatorios, rachas e hitos, que atacan la motivación— sino que **la exactitud de la app es función de la disciplina del usuario**, y todo sistema con esa propiedad se degrada. La curva del atraso no es lineal porque la memoria se degrada antes que el volumen: **pasadas ~72 horas, "cargar los gastos" ya es reconstruir desde el resumen.** Y si vas a leer el resumen igual, el resumen tenía que ser la fuente desde el día uno.
- **Ya lo habíamos resuelto, en Cartera.** Trampa nº4: dos fuentes (movimientos = histórico, tenencia del broker = foto actual) y **su diferencia es la reconciliación**. La Cartera nunca depende de que Franco recuerde cargar una operación. Finanzas Personales no tiene ancla: su verdad es la suma de lo tipeado. **ADR-0006 porta ese patrón al Lugar A.**
- **Lo que se descartó en el camino, con motivo:** agregación bancaria directa (el Decreto 353/2025 creó el Sistema de Finanzas Abiertas pero el BCRA no publicó estándares; Belvo cubre BR/MX/CO, no Argentina) · registrar saldos como ancla (redundante: importar el resumen ya da el control total) · gamificación (ya descartada el 4/8; acá quedó el porqué).
- **Números reales de Franco:** débito la mayor parte (vive en la caja de ahorro), dos tarjetas de crédito con resumen mensual, efectivo 10-15%. **Y el efectivo también tiene ancla: las extracciones figuran en la caja de ahorro.** Cobertura alcanzable ~85-90% con cero actos de memoria, y el hueco restante con magnitud conocida.
- **El dedupe que pidió Franco no es uno, son seis clases** y cada una se resuelve distinto: reimportación (hash determinístico), pago-vs-resumen (clasificación, no matching), WhatsApp-vs-archivo (fuzzy, propuesto), doble listado del banco, billeteras (no aplica: no usa) y cuotas.
- ⚠️ **Dos correcciones que evitaron errores que fallan hacia abajo.** (1) Franco propuso **eliminar el motivo "Pago tarjeta"**: no se puede — hoy es el único rastro del consumo con crédito de todos los meses cerrados, y borrarlo derrumba el gasto histórico (trampa nº12). (2) Mi primera versión usaba una **fecha de corte fija**, y como un pago cubre consumos del mes anterior, sin backfill el primer mes desaparecía entero. **Regla adoptada: un pago es traspaso si y solo si el resumen que lo cubre fue importado** — la reconciliación *es* el interruptor, y degrada seguro (si falta el resumen, se pierde el detalle, nunca la plata).
- **Plan:** ROADMAP reescrito. La Fase 4 cierra en lo que hizo (respaldo + CI) y **M4 y M5 quedan absorbidos por una Fase 5 nueva** de 7 pasos (~2,5 semanas); las fases posteriores se renumeraron a 6, 7 y 8. M4 no se descarta: **se reordena de primer paso a último**, porque construir el extractor genérico antes de la arquitectura de cuentas era resolver el problema fácil primero.

- 🐛 **Bug latente encontrado y arreglado en `scripts/indexar.py`.** `co_cambios()` devolvía `{}, {}` cuando `git log` no respondía, pero el llamador hace `.most_common()`, que un dict no tiene → `AttributeError`. Y `git()` devuelve `""` **en silencio** si el comando falla o pasa su timeout de 20s, cosa que ocurre de verdad con el repo en OneDrive y el disco lento (esta misma sesión la suite pasó de 22s a 105s por eso). Como el indexador corre en el **hook pre-commit**, el efecto real era: *un git lento te deja sin poder commitear*. Fix de una línea (`Counter()` en vez de `{}`) más el porqué escrito al lado.

**Estado al cierre:** documentación, una decisión y un fix de una línea en un script. Suite 740 passed, 3 skipped. Commit pendiente de Franco.

---

## 2026-08-27 (2ª sesión) — Cuatro tareas chicas: vencimientos, benchmark, lock y el ciclo de imports
**Autor:** Claude (Opus 5), con Franco.

Franco pidió algo más corto que el importador con LLM (M4) y terminó tomando las cuatro opciones propuestas. Se hicieron **de a una, con la suite verde entre cada una**. Arranque: 664 passed. Cierre: **718 passed, 3 skipped**.

- **Vencimientos desde el cronograma de Docta.** `vencimientos.py` resolvía 1 de 3 de la renta fija viva porque parseaba la descripción del instrumento. El dato faltante **ya estaba en la base** desde M15 (el cronograma de pagos) y nadie lo miraba: la última fecha del cronograma es el vencimiento. Cascada nueva: override manual → cronograma → descripción, sin gastar cuota de API. Cuando las dos fuentes exactas discrepan, gana el cronograma pero **la fecha descartada queda visible** (`discrepancia`) y la vista avisa. Detalle en la bitácora de cartera.
- **Benchmark money-weighted contra SPY/Merval** (`core/market_data/indices.py` + `places/inversiones/cartera/benchmark.py`). *"Si hubieras puesto la misma plata en las mismas fechas en el índice, ¿cuánto tendrías hoy?"*. No compara acumulados —Franco aportó en 24 momentos y el índice no— y usa `adjclose` para no regalarle a la cartera los dividendos que el índice sí paga. Sin migración: cachea en `cartera_precios_cache`.
- **`requirements.lock`. ⚠️ Acá apareció el hallazgo de la sesión.** Ese día `pip` en Python 3.11 resolvía `pandas>=2.0.0` como **pandas 3.0.5** — un salto de major contra el que la suite nunca corrió. Un `pip freeze` a ciegas habría congelado eso y el próximo deploy habría sido la primera vez que alguien lo ejecuta. Se generó con topes (`pandas<3`, `numpy<2.3`) y quedó en **pandas 2.3.3**, y se **verificó de verdad**: venv de Python 3.11 con esos pines exactos + la suite entera → **679 passed, 0 failed**. El `Dockerfile` ya usaba el lock si existía, así que no hubo que tocar el deploy.
- **Ciclo core↔core/auth cortado** (propuesta 4 del estudio del 18/8). Los contextvars se mudaron a `core/context.py`, un módulo que **no importa nada del proyecto**; `core/auth/current_user.py` y `current_workspace.py` quedaron como fachadas que re-exportan **los mismos objetos** (si fueran copias, `set()` por una puerta y `get()` por la otra divergirían sin error visible). Beneficio medible: `core/db.py` y los seis módulos de lógica de Finanzas dejaron de arrastrar **bcrypt** solo para leer un entero. `tests/test_context.py` mide el grafo de imports en procesos limpios para que el ciclo no vuelva.

**Nota de método:** los procesos en segundo plano **no sobreviven** entre llamadas del sandbox (ni con `nohup` ni con `setsid`); las tareas largas hay que partirlas. Y la verificación del lock no se pudo hacer en el sandbox (Python 3.10: `rpds-py` del lock exige ≥3.11), así que se corrió empaquetando el repo y ejecutándolo en un entorno 3.11.

**Y una quinta, pedida sobre el cierre: el split de `view.py`** (propuesta 3 del 18/8). El archivo tenía **1.990 líneas** y lo tocaba el **28% de los commits del repo** (27 de 97; el segundo archivo de código más commiteado es `core/db.py` con 11). Quedó un orquestador de **760 líneas** y **diez paneles** en `cartera/paneles/`, el mayor de 231. Fue un `mv`: las costuras ya estaban porque cada panel era una función independiente, y `render()` no cambió una línea (los paneles se reimportan con el mismo nombre). **Verificado por AST contra `HEAD`: 23 funciones idénticas, 0 perdidas, 0 duplicadas.** Rompió 5 tests que escaneaban el fuente de `view.py` buscando funciones por nombre — se los apuntó a los dos lugares, para que afirmen *qué hace* la función y no dónde vive.

**Estado al cierre:** suite **740 passed, 3 skipped**. Commit pendiente de Franco. Sin cambios de esquema ni de datos.

---

## 2026-08-27 — Higiene de gobernanza: el "próximo paso" apuntaba a una tarea muerta
**Autor:** Claude (Opus 5), con Franco.
- **Qué se encontró.** Estudio completo de la app (102 archivos, ~23.700 LOC) para decidir la jornada. Los documentos de gobierno se habían **desincronizado entre sí** en tres puntos, y uno era caro: `ESTADO.md` —la única fuente de verdad según `GUIA-DE-TRABAJO.md`— tenía como **próximo paso concreto** la *"Fase 4, punto 3: voz consistente + hitos"*, que `MEJORAS.md` registra como **⛔ descartada por Franco el 4/8/2026** con la nota explícita *"anotado para que no se vuelva a proponer"*. O sea: durante 23 días el handoff apuntó a una tarea que ya se había decidido no hacer, y la Fase 4 quedó de hecho **sin próximo paso definido**.
- **Por qué importa más de lo que parece.** El protocolo del repo dice "gana `ESTADO.md`" cuando dos versiones de la realidad no coinciden. Acá la que estaba mal era `ESTADO.md`, así que la regla de desempate habría hecho que la sesión siguiente empezara a codear lo descartado. **Una decisión de NO hacer algo necesita propagarse a todos los documentos, no solo al backlog donde se anotó.**
- **Segunda desincronización:** `ROADMAP.md` seguía marcando **Fase 3 🔵 en curso** y **Fase 4 ⬜ pendiente**, cuando 3a/3b están cerradas desde el 30/7 y la Fase 4 arrancó ese mismo día; arrastraba además *"pendiente: desplegar los puntos 3 y 4 de 3b"* (salió con la tanda del 5/8) y la fecha vieja del AE38 (**9/7/2027**, corregida a **12/7/2027** el 5/8 porque el 9 es feriado). Reescrita la Fase 4 con sus cinco puntos y su estado real.
- **Tercera:** `MEJORAS.md` daba TIR esperada, duration y calendario de cobros como 🟡 pendientes y *"falta que Franco cree la cuenta de Docta"* — las tres se hicieron el 13-14/8 y las credenciales ya están en `.env`. Marcadas ✅.
- **Pregunta abierta que salió del cruce:** el último deploy **con registro** es el del 5/8. La tanda del 13-14/8 (Docta M15 + panel de renta fija, hasta `8f8ba73`) está en `main` pero **no hay constancia de que se haya desplegado**. Anotado en `ESTADO.md` como verificación de Franco.
- **`Borrar/` vaciada:** 355 archivos y 5,8 MB de `HEAD.lock`, `maintenance.lock` y `tmp_obj_*` acumulados desde el 4/8. Se conservaron a propósito el código del scoring retirado (referenciado desde `MAPA.md`) y los dos `.tar.gz` de respaldo del 18/8. **Novedad operativa:** el sandbox de Cowork ya puede borrar en el mount de OneDrive si se pide permiso explícito; la regla de "solo `mv`" dejó de ser la única salida. `git status` limpio y `git fsck` sin daños después.
- **Verificado:** los 102 módulos compilan (`compileall`, exit 0) y ningún `.md` vigente vuelve a apuntar a la tarea descartada como próximo paso.
**Estado al cierre:** solo documentación; cero cambios de comportamiento. **Próximo paso real de la Fase 4: M4, el importador de CSV con LLM** (a confirmar con Franco antes de codear). Pendiente: commit + push de Franco.

---

## 2026-08-18 — Mapa vivo del repo + ESTADO.md adelgazado (skill `mapa-de-proyectos`)
**Autor:** Claude (Fable 5), con Franco.
- **Por qué:** el repo llegó a ~23.500 LOC y ~100 archivos, y la memoria del proyecto (ESTADO 52 KB + EN-HUMANO 61 KB + bitácoras) obligaba a cada sesión nueva a releer historia para orientarse. Los tres documentos de gobierno eran, según el propio historial de git, los archivos que más co-cambiaban del repo.
- **Mapa:** `MAPA.md` (generado, ~184 líneas) + `.mapa/` (índice JSON + `buscar.py`) + `scripts/indexar.py`. Cada carpeta con código tiene ahora una **`BITACORA.md` router** (Resumen · "Buscar acá si" · Qué hay · **Trampas** · Estado), sellada con huella del código: complementa a la `bitacora_de_trabajo.md` (crónica), no la reemplaza. Las trampas caras del proyecto (orden de import Excel-primero, bonos /100, db.py módulo plano, identidad patrimonio−aportes, etc.) quedaron en la ficha de la carpeta donde muerden.
- **Hook pre-commit, ahora de TRES capas** y versionado en `scripts/hook-pre-commit` (antes vivía solo en `.git/hooks`): (1) candado anti-datos intacto; (2) reindexado del mapa — suma `MAPA.md`/`.mapa` al commit y avisa (sin bloquear) si una bitácora quedó vencida; (3) framework `pre-commit` si está. Tolerante a Windows (`python3`/`py -3`/`python`).
- **`ESTADO.md`: 285 → 58 líneas.** La narrativa de 3a/3b/arranque de F4 se movió **tal cual** a `docs/archivo/ESTADO-historial.md`; quedan la foto, el próximo paso, bloqueos y las notas operativas permanentes. Protocolo actualizado en `README.md`, `claude.md` y `GUIA-DE-TRABAJO.md`: leer `MAPA.md` al abrir, sellar bitácoras al cerrar.
- **Verificado:** suite **664 passed, 3 skipped** (sandbox con oráculos CSV; los 3 skipped son el gate de recon sin `CARTERA_XLSX`) + reindexado sin bitácoras vencidas.
- **Decisiones que quedaron abiertas (propuestas 3 y 4 del estudio):** split de `view.py` de cartera en paneles y corte del ciclo core↔core/auth vía `core/context.py`. A confirmar con Franco.
**Estado al cierre:** solo documentación e infraestructura de índice; cero cambios de comportamiento de la app. Pendiente: commit + push de Franco.

---

## 2026-08-04 — El primer CI rojo: los tests-oráculo necesitan datos que no se versionan
**Autor:** Claude (Opus 5), con Franco.
- El CI recién estrenado falló en `test_kpis.py` y `test_reconciliacion.py`: leen `Diario.csv`/`Mensual.csv` de la raíz, que **por regla dura nunca se versionan**. **El CI hizo exactamente lo que tenía que hacer** — mostró un supuesto que solo se sostenía en la PC de Franco.
- ⚠️ **Se descartaron dos de las tres soluciones sugeridas por una herramienta externa.** *CSV falsos en el workflow*: `test_kpis.py` compara contra **importes exactos**, así que con datos inventados o falla, o hay que reescribir los valores esperados y el test deja de proteger. *`--ignore` del módulo*: los borra de la salida y nadie se entera de que existen.
- **Se aplicó la convención que el repo ya tenía** desde el gate de reconciliación de la Fase 3a: `pytest.skip` con **motivo explícito**. Centralizado en **`tests/_oraculos.py`**, que respeta `DIARIO_CSV`/`MENSUAL_CSV` igual que `ingest.py`, así que los CSV pueden vivir fuera del repo.
- **Verificado en los dos escenarios:** sin los CSV → **23 skipped, cero errores**; con los CSV → **23 passed**.
**Por qué importa:** el conteo de `skipped` es la señal. Los tres oráculos (`test_kpis`, `test_reconciliacion`, `test_cartera_recon`) solo corren local; antes de cada deploy la suite tiene que dar **0 skipped** en la máquina de Franco.
**Estado al cierre:** 362 passed, 3 skipped (local, con datos). Commit listo para pushear.

---

## 2026-08-04 — Bug en producción: "Agregar gasto" reventaba desde el celular
**Autor:** Claude (Opus 5). Lo encontró Franco usándola.
- `UnboundLocalError: firma_val` al enviar el formulario en **modo rápido**. La app moría entera.
- **Causa:** el formulario se bifurca en modo rápido / detallado y las dos ramas caen al mismo guardado, pero `firma_val` se definía solo en la rama detallada. Desde el celular se usa el rápido.
- **Fix:** la variable se define **antes** de la bifurcación; en modo rápido se asume el miembro activo del espacio (no se pregunta: esa es la gracia del modo).
- **Test por AST** (`tests/test_transacciones_formulario.py`, 10): verifica que ninguna variable leída después de la bifurcación esté definida en una sola rama — atrapa la **clase** de error, no solo este caso. **Verificado reintroduciendo el bug:** fallan 3 tests; con el fix, pasan los 10.
**Por qué importa:** es el tercer bug que encuentra Franco usando la app y no los tests. El patrón se repite: los tests prueban el camino limpio, él usa el camino real.
**Estado al cierre:** 362 passed, 3 skipped.

---

## 2026-08-04 — CI: la suite corre sola en cada push
**Autor:** Claude (Opus 5), con Franco.
- **`.github/workflows/tests.yml`**: corre `pytest` en **Python 3.11** (la misma del `Dockerfile` — si CI pasara en otra versión no probaría lo que se despliega) en cada push y PR, **desde cero**. Eso último es lo que ningún test local puede dar: detecta lo que funciona en la PC de Franco "de casualidad".
- **Segundo job `sin-datos`**: busca `.xlsx`/`.db`/`.csv`/`.env` y claves privadas en el **árbol completo**, no solo en el diff. El pre-commit hook ya lo bloquea, pero vive en la PC de Franco y se puede saltear con `--no-verify`; esta es la red que no se puede puentear.
- **La suite no necesita red:** todos los módulos que salen a internet (`mep`, `precios`, `sectores`, `snapshot` del scoring) tienen `fetch` inyectable. El CI no depende de que Yahoo o GitHub Pages estén arriba.
- El gate de reconciliación aparece como **skipped** en CI y está bien: necesita el Excel de Franco, que nunca se versiona. Ese gate corre local.
**Por qué:** hasta hoy la suite corría solo si Franco escribía el comando. Ese hueco dejó pasar que su entorno local se quedara sin dependencias (Python 3.14 sin instalar nada, la suite ni colectaba) sin que nadie se enterara.
**Estado al cierre:** 352 passed, 3 skipped. Commit listo para que Franco pushee.

---

## 2026-07-30 — Fase 4 arranca por el respaldo: copia externa, restore y ensayo
**Autor:** Claude (Opus 5), con Franco.
- **Relevamiento del backlog del Lugar A** (traído de `Mis-Finanzas-App`): el ítem más grande (**D2 Grupo familiar**, 4-5 días) ya estaba hecho desde el 17/7, y la **Sección 9 (módulo de inversiones)** quedó superada por las Fases 3a/3b. ⚠️ Su decisión cerrada *"NO reemplazar el Excel de Inviu"* está **revertida por ADR-0003**.
- **Agujero real encontrado, no una mejora:** los backups automáticos viven **en el mismo volumen de Fly que la base**; solo los disparaba el Lugar A (importar cartera no dejaba copia); el `backup_remoto.ps1` de la app vieja **no existía acá**; el `RUNBOOK.md` eran cinco líneas de placeholder; y **nunca se ensayó un restore**. Lo irreemplazable son las transacciones personales: la cartera se reconstruye del Excel, los gastos no.
- **`scripts/backup_remoto.ps1`**: copia externa que **verifica antes de darla por buena** (`integrity_check` + que haya transacciones + movimientos) y falla si baja vacía. La purga conserva siempre las 3 más recientes aunque sean viejas.
- **`scripts/restaurar_backup.ps1`** (no existía en ningún lado): simulacro por defecto, respalda producción antes de pisarla, para la app, sube, **borra los archivos `-wal` y `-shm`** —sin eso SQLite mezcla la base restaurada con el diario de la vieja y queda corrupta— y verifica el health.
- **La cartera ahora deja punto de retorno** antes de importar, corregir un movimiento o guardar una tenencia.
- **`tests/test_backup_restore.py`**: el ciclo completo automatizado (respaldar → perder → restaurar → verificar), más que la purga nunca se lleve la última copia buena.
- **`docs/RUNBOOK.md`** de verdad: qué se puede reconstruir y qué no, las tres capas de respaldo, backup, restore, ensayo, caída, secrets y pendientes.
**Por qué primero esto:** de todo el backlog, es lo único cuyo costo de equivocarse es perder datos que no están en ningún otro lado.
**Estado al cierre:** 347 passed, 3 skipped. Commit listo para que Franco pushee.

---

## 2026-07-30 — Sector e industria automáticos (Yahoo, con caché y override)
**Autor:** Claude (Opus 5), con Franco.
- Pedido de Franco: que la app reconozca sola los sectores, TGNO4 clasificado, y los ETF con categoría propia.
- **`core/market_data/sectores.py` + M12** (`cartera_sectores`): cascada override → scoring → **Yahoo `v1/finance/search`** (sin autenticación; `quoteSummary` exige crumb y da `Unauthorized`). `fetch` inyectable, caché en DB, caché negativa para no reintentar en cada carga, y nunca lanza.
- **Coincidencia exacta de símbolo** (buscando `URA` aparece `UROY`, una minera), **sufijo `.BA`** para las argentinas, y los pagarés no se consultan.
- **Los ETF no tienen sector porque son una canasta**: se les arma la etiqueta desde el nombre del fondo → **"ETF · Oro"**, "ETF · Uranio", "ETF · Cobre", "ETF · S&P 500".
- **Decisión de Franco:** Yahoo clasifica TGNO4 como *Energy · Oil & Gas Midstream* y no como Utilities; eligió que **mande Yahoo** para quedar comparable contra el estándar GICS. El override queda disponible, con UI.
- **Cobertura 100% de la renta variable** (antes 65,7%), cero "Sin dato". Con el nivel de industria aparece que el 21,5% de Technology es **16% en semiconductores**.
**Por qué:** una lista de sectores cargada a mano se desactualiza con cada compra nueva; el dato tiene que resolverse solo.
**Estado al cierre:** 342 passed, 3 skipped. Commit listo para que Franco pushee.

---

## 2026-07-30 — FASE 3b COMPLETA: composición por tipo de renta y sector
**Autor:** Claude (Opus 5), con Franco. Skill `ui-ux-web-moderno` aplicada.
- **`analisis.py`**: `por_tipo_de_renta` (cobertura total, desde `categoria_activo`) y `por_sector` (desde el snapshot del scoring, 100 empresas). Snapshot caído → todo "Sin dato" y la cartera se muestra igual.
- **El porcentaje se mide contra el patrimonio con el efectivo adentro**, y se agrega **solo el resultado no realizado**: sumar el total por grupo repetiría la trampa de 3a.
- ⚠️ **Dos correcciones al mirar los números reales:** el **pagaré (34% de la cartera)** caía en "Sin dato" porque nunca estuvo en Config → se reconoce por el `#` y es renta fija; y el corte por sector se diluía a un "Sin dato" del 74,6% por meter bonos, pagaré, cripto y efectivo → ahora mira **solo la renta variable** y la cobertura pasó de 25% a **65,7%**.
- **Foto de la cartera:** renta fija **60,1%**, renta variable **38,3%**, cripto 1,3%, efectivo 0,3%. Dentro de la variable: Technology 21,5%, Financial Services 11,3%, Consumer Cyclical 10,7%, Communication Services 9,3%, Energy 7,6%.
**Por qué:** cierra la Fase 3b — la cartera ya dice cuánto tenés, cuánto ganaste, en cuánto tiempo, en qué acertaste, cuánto rindió la caja y dónde está parada.
**Estado al cierre:** 324 passed, 3 skipped. Commit listo para que Franco pushee.

---

## 2026-07-30 — Fase 3b punto 3: cauciones, dividendos y cuenta remunerada
**Autor:** Claude (Opus 5), con Franco. Skill `ui-ux-web-moderno` aplicada.
- **`rendimientos.py`**: aparea las cauciones (colocación y vencimiento **comparten la fecha de concertación**; el plazo sale de la diferencia entre las liquidaciones), calcula el interés y la **TNA ponderada por capital y tiempo** — promediar las TNA sueltas engaña. Dividendos **netos de retención** por instrumento y cuenta remunerada.
- **Identidad independiente verificada:** el interés apareado ($33.365,31) es idéntico al neto de **todos** los movimientos de caución, cálculo que no depende del apareo. En test y contra datos reales.
- **Vista "La plata quieta"**, con la aclaración explícita de que es **atribución, no plata nueva**: ya estaba dentro del patrimonio.
- **Números:** 101 cauciones · interés $33.365,31 · **TNA ponderada 25,60%** (2024: 24,48% · 2025: 29,31% · 2026: 21,38%) · dividendos 62 cobros, $89.086,78 brutos − $5.190,66 de retención · remunerada $3.300,98 · **total caja $120.562,41**.
- Las TNA más altas de la serie (hasta 105%) son todas de **octubre 2025**: el apretón pre-electoral quedó registrado en los propios movimientos.
**Por qué:** la plata que no está en una posición igual rinde, y hasta ahora era invisible: las cauciones no son instrumentos y no aparecían en ningún lado.
**Estado al cierre:** 295 passed, 3 skipped. Commit listo para que Franco pushee.

---

## 2026-07-30 — Corrección de movimientos del broker (ASML resuelto)
**Autor:** Claude (Opus 5), con Franco.
- Franco confirmó la causa del +22.754% de ASML: **el broker le sacó dos ceros** (compró a $6.010, el archivo decía $60,10). Corregido **en la app y en el Excel**; la venta pasa a +$69.803 (+128,5% ARS / +80,2% USD en 250 días) y es la mejor operación de la cartera.
- **`parser.clave_dedupe()`/`hash_dedupe()`** centralizan la regla de identidad de un movimiento; **`ingest.corregir_movimiento()`** corrige y **recalcula el hash**, para que reimportar el Excel corregido dedupee en vez de duplicar. Las dos rutas (con y sin corrección en la app) están congeladas en tests. Expander nuevo en la vista.
- Excel corregido con **edición quirúrgica sobre el XML**, no round-trip de openpyxl (le borra formato condicional y extensiones a un libro de 16 hojas). Respaldo previo guardado.
- **Barrido preventivo** de precios anómalos: 12 filas marcadas, 11 legítimas (compras en USD). Queda **TTM26** (17.395 nominales por $17,78) como candidato para que Franco chequee con el broker.
**Por qué:** un dato malo del custodio deforma el costo sin avisar; y arreglar solo el Excel duplicaba la operación.
**Estado al cierre:** 276 passed, 3 skipped. Commit listo para que Franco pushee.

---

## 2026-07-30 — Fase 3b paso 2: el resultado por operación (ADR-0005)
**Autor:** Claude (Opus 5), con Franco. Skill `ui-ux-web-moderno` aplicada.
- **ADR-0005**: el realizado se mide con el **PPC vigente al vender**, no con el promedio de toda la historia. Se mantiene costo promedio ponderado (FIFO sigue en MEJORAS); el gate de recon (cantidades + costos USD) no se toca.
- **El realizado y el costo del remanente van juntos**: enchufar solo uno rompía la identidad `costo liberado + costo remanente = total comprado`. Test de la identidad incluido.
- **Vista**: sección "Operaciones cerradas" — 45 ventas, 38 ganadoras, con PPC del día, resultado ARS/USD y días de tenencia. Mejor: AE38 +97,7% en 578 días.
- **Verificado end-to-end**: valor de cartera idéntico → **patrimonio, aportado, resultado total y TIR intactos**. No realizado $2,83M → $3,26M; rendimiento sobre costo 13,4% → 15,8%.
- 🔎 **Para Franco**: la compra de ASML del 16/5/2025 figura como 9 unidades a **$60,10** contra una venta a $13.840 (+22.754%). Ensucia el PPC actual (11.677 contra los 18.647 reales). Chequear con inviu. Se agregó la guarda `sospechosa` (>1.000%) para que un dato malo no se muestre como el mejor trade.
**Por qué:** el resultado agregado no dice en qué acertaste; y una compra posterior no puede cambiar lo que ganaste en una venta anterior.
**Estado al cierre:** 271 passed, 3 skipped. Commit listo para que Franco pushee.

---

## 2026-07-30 — Arranca la Fase 3b: la línea de tiempo de la cartera
**Autor:** Claude (Opus 5), con Franco.
- Se detectó que los **cuatro** puntos de la Fase 3b comparten una limitación estructural: `posiciones.py` **agrega sin orden temporal**, así que el resultado realizado de una venta se mide contra el PPC de toda la historia, incluidas las compras posteriores. Decisión de Franco: construir la línea de tiempo una sola vez y apoyar los cuatro puntos ahí.
- **`places/inversiones/cartera/ledger.py`**: motor cronológico puro con **PPC móvil**, una `Realizacion` por cierre (costo liberado al PPC vigente, resultado ARS/USD, días de tenencia) y las retenciones separadas de los dividendos. 17 tests. Aditivo: todavía no cambia nada de lo que ve el usuario.
- **Medido sobre el crudo real:** el realizado en pesos cambia en 8 tickers, $3.297.014 → $3.145.965 (−4,6%). Patrimonio, TIR y gate de recon inmunes.
- **Dato de dominio adoptado (Franco):** en Argentina la amortización va por **precio**, nunca por nominales.
- **Supuesto corregido con datos reales:** AE38 no amortizó el 9/7/2026 (fue solo cupón, misma tasa por nominal que los anteriores). Primera amortización: **9/7/2027**. AN29 es bullet. Ningún instrumento de la cartera amortiza parcialmente antes de julio 2027.
**Por qué:** sin cronología no hay resultado por operación honesto, y los otros tres puntos de la fase se apoyan en lo mismo.
**Estado al cierre:** commit listo para que Franco pushee. Falta ADR-0005 y cablear el motor a la vista.

---

## 2026-07-30 — FASE 3a COMPLETA: la cartera nativa reconcilia y está lista para deploy
**Autor:** Claude (Opus 4.8), con Franco.
- **Consolidación real:** dedupe verificado en producción (de 586 movimientos, 580 ya estaban, entraron 6). Tenencia al 29/7 importada.
- **El pagaré** (35% de la cartera) pasó a computar costo: `"Compra cheque"` → COMPRA, ticker extraído del formato `Boleto / … / #UMV060770008 / U$S`, `es_instrumento` para tickers con `#`, y PPC con la cantidad de la tenencia. **Franco corrigió mi interpretación de su valuación**: se compran a descuento (US$5.032 → VN US$5.500 = 9,3% ≈ 10% anual), así que el precio del broker es correcto y queda como default.
- **Paso 5 (gate final):** recon de **costos en USD** en modo MEP único (metodología del Excel) → **49 tickers reconcilian**. Divergencia de AE38/GGAL/BITCOIN (saldo inicial en USD que el Excel toma como ARS) **congelada en un test que falla si la planilla se corrige**.
- **Números al 30/7:** patrimonio $23.961.034 / US$15.741,21 · aportado $13.462.628 / US$11.534,26 → **+78,0% ARS / +36,5% USD acumulado · TIR 51,4% / 24,4% anual** (602 días).
**Estado:** suite **229 passed** + 3/3 del gate. **Fase 3a cerrada**, lista para merge a `main` + `fly deploy`.
**Próximo:** deploy y luego 3b (realized PnL por trade, cauciones/dividendos, sector/tipo de renta, amortizaciones parciales).

---

## 2026-07-23 (cierre del día) — Rendimiento completo ARS/USD + cierre de vencidos
**Autor:** Claude (Opus 4.8), a pedido de Franco (decisión suya de adelantar parte de 3b).
- **Franco detectó** que las amortizaciones son rendimiento y no se computaban: **$6.345.528** en flujos cobrados quedaban afuera, y 6 letras vencidas figuraban con cantidad residual. Pidió además medir el rendimiento **en dólares con el MEP del día de compra y de cobro**.
- **Cierre de vencidos sin heurísticas:** se usa `Config!L "Activo en cartera" = NO` del propio Excel. **Rendimiento completo** según el LEEME (realizado + no realizado + dividendos + amortizaciones), en ARS y USD al TC congelado de cada fecha.
- ⚠️ **Bug corregido:** la amortización devuelve capital + interés; contarla entera daba ~100-113% de rendimiento en las letras. Se agregó `costo_amortizado_*` (PPC × unidades vencidas). Post-fix, cada letra reproduce exactamente el cálculo manual independiente.
- **Números reales:** invertido $33,2M (US$25.219) → **+$10.398.493 (+31,3%) en pesos · +US$4.273 (+16,9%) en dólares**. Caso ilustrativo: S15G5 +3,8% en pesos pero **−3,6% en dólares**.
- Vista con bloque "Rendimiento total" + columna `Rend. US$ %` + toggle de posiciones cerradas. Recon **verde** (documentado que compara el plano bruto del Excel; el cierre de vencidos es capa propia). Suite **206 passed, 1 skipped**.
**Pendiente 3b:** amortizaciones parciales de bonos vivos (hoy suman como flujo sin reducir tenencia).

---

## 2026-07-23 (final) — Fase 3a paso 4: la Cartera ya vive en la app
**Autor:** Claude (Opus 4.8), con Franco. Skill `ui-ux-web-moderno` aplicada.
- **Vista de Cartera** cableada en la pestaña (reemplaza el cartel de "Fase 3"): KPI cards con tokens Cosmic Slate (tabular-nums; ganancia/pérdida con signo+flecha+color, nunca color solo), tabla es-AR, **upload del export del broker** con dedupe + congelado de TC en el mismo flujo, carga de instrumentos desde Config, caché de 5 min, estados empty/error. Scope por usuario (`CARTERA_USER_IDS`).
- **Lógica:** costo promedio ponderado + costo USD a TC histórico (`posiciones.py`), valuación y totales (`kpis.py`; el costo de lo que no tiene precio no entra a los totales). `tests/test_cartera_kpis.py` (12). Suite **200 passed, 1 skipped**.
- **Verificado end-to-end con datos reales:** $15.490.098 / US$10.101 · +19,8% · 23 posiciones valuadas; BTC vía yahoo.
- ⚠️ **Para 3b:** 6 letras/bonos en pesos vencidos quedan con cantidad residual (el vencimiento entra como AMORTIZACION y solo VENTA resta). El Excel arrastra lo mismo; no cotizan → no ensucian totales.
**Próximo:** paso 5 (recon USD modo "MEP actual") para cerrar 3a, luego merge a `main` + `fly deploy`.

---

## 2026-07-23 (cierre) — Fase 3a paso 3: `core/market_data` (MEP histórico + precios)
**Autor:** Claude (Opus 4.8), con Franco.
- **Hallazgo que corrigió una decisión cerrada:** el ADR-0003 asumía el MEP histórico "vía BCRA", pero **el BCRA no publica MEP** (sirve el mayorista A3500: 1.480,86 vs MEP 1.521,9 al 22/7). Se presentaron alternativas y Franco eligió **`argentinadatos`** → **ADR-0004**. Verificado antes de decidir: 419/419 días hábiles del historial cubiertos.
- **`core/market_data/`** (fetch inyectable, tests sin red): `mep.py` (serie, último hábil anterior, caché, fallback, override) + `precios.py` (data912 ARG, yahoo BTC, precedencia override→caché→proveedor, bonos /100) + `ingest.congelar_tc_mep` idempotente.
- **Humo real contra APIs vivas:** 585 movimientos del Excel importados con **TC congelado en las 585 filas, cero fechas sin dato**; 1.204 símbolos ARG; AE38 = 1.273,6 (broker: 1.262,6). `tests/test_market_data.py` (18). Suite **188 passed, 1 skipped**.
**Por qué:** sin TC histórico y precios automáticos, la cartera no puede valuarse ni superar al Excel (que usa un único MEP actual para todo).
**Próximo:** paso 4 — posiciones + KPIs + vista de Cartera (con upload del export).

---

## 2026-07-23 (tarde) — Excel-oráculo actualizado + reconciliado 20/20 + modelo M9
**Autor:** Claude (Opus 4.8), con Franco.
- Franco pasó el export completo de inviu + la Tenencia del broker. Se reconstruyó `Inversiones.xlsx` (con respaldo): export + saldos sintéticos + ajuste de ratio SPY (+70); Procesado con Moneda alineada; Config + Resumen corregidos; MEP/BTC al día. **Recalc con LibreOffice: 20/20 posiciones exactas vs broker.** El parser reprodujo 19/20 solo con movimientos → validación fuerte del motor.
- **M9** (aditiva, `core/db.py`): tablas `cartera_instrumentos`, `cartera_movimientos` (dedupe por `UNIQUE(user_id, hash_dedupe)`, `tc_mep` para paso 3), `cartera_precios_cache`; scope por user_id. `tests/test_cartera_db.py` (8).
- **Ingest** (`ingest.py` + `posiciones.py`): carga de instrumentos desde Config + import de movimientos con dedupe; posiciones portando `Resumen Cartera`. Gate `tests/test_cartera_recon.py` **reconcilia exacto** contra el Excel (verificado con recalc; skip elegante sin Excel/caché). `tests/test_cartera_ingest.py` (5). Suite **170 passed, 1 skipped**.
- Convención `Borrar/` para basura de git del mount OneDrive (gitignoreada).
**Próximo:** `core/market_data` (paso 3) — MEP histórico + precios ARG/CEDEARs/BTC con caché + override.

---

## 2026-07-23 — Fase 3a, paso 1: parser del broker construido y testeado
**Autor:** Claude (Opus 4.8), con Franco.
- Se **rescató y completó** el borrador `places/inversiones/cartera/parser.py` (estaba untracked y no compilaba). 3 arreglos: `SyntaxError` de la línea 196 (carácter U+0640 incrustado, probable sync OneDrive); espejo de dividendos/renta apareado por `(fecha, ticker_base)` tolerante a categoría para cubrir el **formato nuevo**; detección de saldo inicial sintético sin el paréntesis. Se agregó `__init__.py` y `tests/test_cartera_parser.py` (**43 tests**).
- **Verificado contra el Excel** (crudo real): mapeo de columnas de ambos formatos, `MAPA_OPERACION == Config!A5:B16`, patrones de espejo viejo/nuevo.
- **Hallazgo nuevo:** la col Moneda de `Movimientos Procesado` está **desalineada ~30 filas** (lee la moneda de otra operación); no afecta cantidades del recon y el parser infiere la moneda → app inmune. Fila 32 de Procesado ya borrada por Franco (sin `#REF!`).
- **Estado:** suite completa **157 en verde**. Commit local en `fase-3a/cartera-nativa`, pendiente de push (GitHub Desktop).
**Por qué:** es el cimiento de la carga recurrente; sin un parser con red de tests, todo el recon posterior queda sobre arena.
**Próximo:** paso 2 — modelo de datos (migración M9, `mov_cartera`).

---

## 2026-07-19 — Fase 3a diseñada: cartera nativa (handoff listo para construir)
**Autor:** Claude (Fable 5), con Franco.
- Se estudió `Inversiones.xlsx` a fondo y se decidió el **giro a cartera nativa** (ADR-0003): DB propia de movimientos con mecánica tipo Transacciones — import del histórico, carga recurrente del archivo del broker con dedupe, alta manual — en lugar del espejo Excel-in-the-loop. El Excel pasa a ser **oráculo de reconciliación**.
- Decisiones cerradas con Franco: TC MEP histórico por operación (BCRA) · costo promedio ponderado · precios automáticos (data912/BYMA/BCRA/yahoo vía gauss314/skills, caché + override manual) · Cartera visible solo para Franco (generalizable) · renta fija fuera de cartera (futura sección de análisis de mercado).
- **Hallazgos en el Excel:** el broker cambió el formato del export y la planilla no procesa 31 movimientos desde el 20/5/2026 (avisado); 2 celdas #REF! con reparación indicada. El parser nativo soportará ambos formatos → la app quedará más al día que el Excel.
- Spec completa del parser (12 categorías, espejos, sintéticos, cauciones) documentada en `ESTADO.md`.
**Por qué:** Franco quiere actualización cotidiana sin depender del Excel; el LEEME de la planilla documenta la lógica lo bastante bien como para portarla con red de reconciliación.
**Estado al cierre:** diseño completo, cero código de cartera aún. La próxima sesión arranca construyendo el parser (necesita acceso a la carpeta "Cartera personal").

---

## 2026-07-17 (tarde) — Incidente en producción y resolución mismo día
**Autor:** Claude (Fable 5), con Franco.
- **Síntoma:** tras deployar D2, la app mostró onboarding como usuario nuevo (datos "desaparecidos") y luego crash de migración (UNIQUE en configuracion_new).
- **Causa raíz:** el guard de M4 ("¿la PK contiene user_id?") daba falso tras M8 (PK por workspace) → M4 se re-ejecutó, reconstruyó las tablas **descartando `workspace_id`** y desvinculó todas las filas. El crash posterior fue por duplicados escritos en la ventana rota.
- **Resolución:** guard de M4 corregido (exige tabla no-post-D2) + **M8.5**: reparación idempotente que re-vincula filas huérfanas al workspace personal de su usuario, prefiriendo el dato original ante duplicados. Deploy verificado por Franco: datos restaurados por completo.
- **Autocrítica:** el test de idempotencia original corría sobre DB vacía y no detectaba la desvinculación. Se agregaron 2 tests de regresión que reproducen el incidente (doble migración con datos + estado roto). Suite final: **114 en verde**. Lecciones anotadas en `ESTADO.md`.
- Los datos nunca estuvieron en riesgo real: `user_id` intacto en cada fila + snapshots diarios del volumen + radar-financiero como respaldo.
**Estado al cierre:** D2 en producción, verificado. Próximo: Fase 3 (Cartera).

---

## 2026-07-17 — Grupo familiar D2: gastos compartidos completos (código)
**Autor:** Claude (Fable 5), con Franco.
- Cutover completo del modelo de datos a **workspaces**: migración M8 (PKs por workspace), `core/workspaces.py`, contextvar, y refactor de todas las queries del dominio (`user_id` queda como autor). Sin switcher, todo cae al espacio personal → cero cambio de comportamiento.
- UI completa: badge por modo (violeta/esmeralda), switcher en sidebar, "Espacio compartido" en Configuración (crear con código de un solo uso visible, unirse, salir), "Firmar como" en Transacciones.
- 11 tests nuevos; suite total **112 en verde**. Riesgos del premortem #5 mitigados.
- En la misma sesión: correcciones del tablero de scoring pedidas por Franco (categorías Resto/señal, filtros persistentes, popover de metodología, encabezado simple, NU y SATL → USA en el repo Scoring).
**Por qué:** D1 ya estaba en producción y la feature es de uso real con Agustina; se adelantó de Fase 4 con alcance cerrado.
**Estado al cierre:** código completo y commiteado; falta deploy + verificación de Franco. Próximo: Fase 3 (Cartera).

---

## 2026-07-15 — Fase 2: un solo login, dos lugares, scoring adentro
**Autor:** Claude (Fable 5), con Franco.
- **Shell unificado:** `app.py` ahora es auth gate + `st.navigation` (barra superior) entre 🏠 Finanzas (`places/finanzas/home.py`, la app original intacta) y 📈 Inversiones (`places/inversiones/home.py`, estructura triple con placeholders honestos para F3/F5).
- **Scoring embebido (ADR-0002):** el batch NO se migró — sigue corriendo en el repo público con su cron y su tablero en Pages. La superapp lee el `data.json` publicado con caché 15 min + fallback local + estado de error con retry. Vista nativa Cosmic Slate: KPIs, filtros, scores como barras, cambios de categoría, links a Yahoo (skill `ui-ux-web-moderno` aplicada).
- **Tests:** 101 en verde (4 nuevos para el lector de snapshot, sin red).
**Por qué:** Fase 2 del roadmap; consumir el snapshot en vez de mover el batch mantiene vivo el tablero público y no arriesga lo que ya funciona.
**Estado al cierre:** código completo y commiteado; falta `fly deploy` + verificación visual de Franco. Próximo: Fase 3 (Cartera) o grupo familiar D2.

---

## 2026-07-10 — Fase 1 cerrada: Mis-Finanzas vive en el monorepo, con datos de producción
**Autor:** Claude (Fable 5), con Franco.
- **Migración de código** (~7.000 LOC): lógica de negocio a `places/finanzas/core`, vistas a `places/finanzas/views`, helpers a `places/finanzas/helpers`; auth/db/theme subieron a `core/` compartido. Imports re-cableados con `core.db` como módulo plano (los tests monkeypatchean sus atributos — no convertirlo en paquete).
- **Tests:** 97/97 en verde (reconciliación, KPIs, parsers, premortems, backup). Los CSV ancla (`Diario.csv`/`Mensual.csv`) viven solo en local, ignorados por git.
- **Deploy:** Dockerfile/fly.toml/entrypoint heredados de la config probada de radar-financiero (puerto 8501, volumen `finanzas_data` 1 GB con snapshots, health check). Máquinas del hola mundo destruidas.
- **Datos:** DB de producción copiada de radar-financiero → superapp-finanzas vía backup consistente de sqlite + `fly ssh sftp get/put` (el shell sftp interactivo se come caracteres en Windows; usar `fly ssh sftp put` directo). Verificado por Franco: mismos números.
- radar-financiero queda vivo como respaldo hasta validar la superapp unos días.
**Por qué:** Fase 1 del roadmap — mover sin reescribir, con los tests como gate y sin arrancar de cero en datos.
**Estado al cierre:** Fase 1 ✅. Próximo: Fase 2 (shell unificado + scoring embebido; requiere acceso al repo Scoring-Inversiones).

---

## 2026-07-10 — Fase 0 cerrada: repo publicado, hook probado, hola mundo en Fly.io
**Autor:** Claude (Fable 5), con Franco.
- Primer commit del esqueleto (`3a72222`, 53 archivos, cero datos) pusheado a `fmarconi1-dev/SuperAppFinanzas`.
- Pre-commit hook instalado con doble capa: chequeo anti-datos en `sh` puro (protege también los commits desde GitHub Desktop en Windows, donde no hay `pre-commit`) + framework completo cuando está disponible. Probado: `prueba-hook.xlsx` bloqueado en ambas capas; `pre-commit run --all-files` en verde.
- Hola mundo Streamlit desplegado en Fly.io: `app.py` mínimo, `Dockerfile`, `fly.toml` (región `gru`, auto-stop), `.dockerignore` anti-leak. Deploy verificado por Franco.
- Incidentes resueltos (git + OneDrive): locks huérfanos que bloqueaban GitHub Desktop, archivos commiteados truncados por sync parcial (restaurados) y un índice corrupto que generó un commit destructivo (nunca pusheado; recuperado con `git reset`, sin pérdida). Protocolo de verificación anotado en `ESTADO.md`.
**Por qué:** cerrar los candados y el pipeline de deploy antes de tocar código real (mitigación directa del premortem: fuga de datos y deploy como cuello de botella).
**Estado al cierre:** Fase 0 ✅ completa. Próximo: Fase 1 (migrar Mis-Finanzas-App a `places/finanzas/`).

---

## 2026-07-09 — Evaluación de 9 repos externos
**Autor:** Claude (Opus 4.8), con Franco.
- Se estudiaron 9 repos y se registró el veredicto en `docs/HERRAMIENTAS-EVALUADAS.md`.
- **Adoptar:** `lightweight-charts` (gráficos de cartera/mercado) y `FreeDomain` (URL gratis del deploy).
- **Opcional:** `ccxt` (datos cripto si crece) y `loopkit` (skills de dev).
- **Futuro (capa IA, F7+):** `ollama` + `langgraph`/`crewAI` + `mem0`.
- **Fuera de alcance:** `hyperliquid-sdk` (operar perpetuos choca con la regla de no ejecutar trades).
**Por qué:** sumar valor sin caer en alcance infinito; solo 2 entran al MVP.
**Estado al cierre:** sin cambios de fase; Fase 0 sigue pendiente de cierre.

---

## 2026-07-09 — Arranque: premortem, plan y esqueleto
**Autor:** Claude (Opus 4.8), con Franco.

- Se corrió un **premortem** sobre la idea de unificar Mis-Finanzas-App + Scoring-Inversiones + los Excel de inversiones. 7 modos de fallo. Conclusión: factible como *integración progresiva de activos que ya funcionan*, no como app nueva desde cero. Riesgo #1 = alcance/refactor; más peligroso = fuga de datos al repo. → `Premortem - Superapp Finanzas.html`.
- Se redactó el **plan de trabajo maestro** con prefactibilidad, arquitectura de "dos lugares" (Finanzas / Inversiones-Mercado, esta con estructura triple), comparativa de hosting (recomendado Fly.io para el MVP) y roadmap por fases. → `PLAN DE TRABAJO - Superapp Finanzas.md`.
- Decisiones: monorepo con `core/` compartido + package por lugar · repo privado · MVP = integrar lo existente · renta fija/opciones Excel-in-the-loop primero · multiusuario a futuro.
- Se creó el **esqueleto del monorepo**: estructura de carpetas, `README` y `bitacora_de_trabajo.md` por módulo, y documentos de gobierno (README, ESTADO, GUIA-DE-TRABAJO, ROADMAP, MEJORAS, claude.md), `.gitignore`, `.pre-commit-config.yaml`, `.env.example`, `docs/` con ARQUITECTURA y ADR-0001.

**Por qué:** dejar un flujo de trabajo limpio para que varias conversaciones/Claudes continúen el proyecto (secuencialmente) sin pisarse.

**Estado al cierre:** Fase 0 en curso — falta `git init`/repo privado, probar el hook y el deploy "hola mundo". Ver `ESTADO.md`.

---

<!-- Plantilla de entrada:
## AAAA-MM-DD — Título corto
**Autor:** …
- Qué se hizo.
**Por qué:** …
**Estado al cierre:** …
-->
