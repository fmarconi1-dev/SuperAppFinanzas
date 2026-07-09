# Premortem — Superapp de Finanzas · Transcripción

**Fecha:** 9 de julio de 2026
**Objeto:** Unificar tres proyectos en una sola app web (monorepo, login único, GitHub como centro de verdad, escalable a multiusuario).

## Contexto recopilado

**¿Qué es?** Una superapp web que fusiona: (1) `Mis-Finanzas-App` — Streamlit + SQLite multiusuario, en producción en Fly.io; (2) `Scoring-Inversiones` — batch EOD con yfinance que genera un tablero HTML estático publicado en GitHub Pages vía Actions; (3) la lógica de los Excel de inversiones (cartera con parser de movimientos del broker, renta fija ARG con flujos de fondos/TIRs/duales/CER, opciones con Black-Scholes).

**¿Para quién?** En principio para Franco (uso personal). Potencialmente escalable a multiusuario.

**¿Cómo es el éxito?** Una app mantenible con las tres secciones bajo un login único, desplegada de forma estable y barata, reutilizando el máximo del código existente, con posibilidad de escalar.

**Decisiones del usuario:** monorepo con una sola app · evaluar alternativas de hosting · MVP = integrar lo existente bajo un login · renta fija a criterio del analista.

## Razones de fallo (premortem en bruto)

1. Refactor de "una sola app" subestimado: carpetas `ui/` colisionantes, estados y estéticas distintas; el proyecto se estanca en plumbing.
2. Mismatch de modelo de datos: público (scoring) vs. privado multiusuario (finanzas) vs. PII (cartera) bajo un mismo login, sin modelo de permisos claro.
3. El deploy se vuelve el cuello de botella: DonWeb shared no corre Streamlit; VPS agrega carga operativa.
4. Datos de mercado ARG sin fuente automatizada confiable: MEP y precios se cargan a mano; la Cartera "en vivo" se desactualiza.
5. Pérdida de la lógica validada del Excel: reescribir sin reconciliación fila-a-fila rompe la confianza en los números.
6. Alcance infinito / burnout de un solo dev con tres dominios ricos.
7. Multiusuario prematuro: se construye plataforma en vez de herramienta.

## Análisis por modo de fallo

### 1 · Refactor de integración subestimado
**Historia.** Arrancás motivado moviendo ambas apps a un monorepo. Pronto chocan: las dos tienen `ui/`, distintos helpers de tema, distinto manejo de estado de sesión. Cada intento de "una sola navegación con login único" toca decenas de archivos. Semana 3, los commits son todos "refactor: mover X"; no hay ni una pantalla nueva funcionando. El impulso se apaga.
**Supuesto subyacente.** Que fusionar es sumar código, cuando en realidad es reescribir todos los puntos de contacto (routing, auth, tema, config).
**Señales tempranas.** (a) Semana 3 sin un login que lleve a las dos secciones; (b) el 100% de los commits dicen "refactor" y ninguno agrega valor visible.

### 2 · Mismatch de modelo de datos
**Historia.** El scoring es idéntico para cualquiera (dato público de mercado); las finanzas y la cartera son privadísimas. Al meterlos bajo un login te trabás en "¿el scoring se calcula por usuario o es global?", "¿dónde vive la cartera?, ¿en la DB multiusuario o aparte?". Terminás sobre-ingenierizando un modelo de tenancy para algo que hoy usás solo vos.
**Supuesto.** Que "un login" implica "un modelo de datos".
**Señales tempranas.** Aparece la pregunta de visibilidad del scoring sin respuesta en el diseño; empezás a duplicar tablas "por las dudas".

### 3 · El deploy se vuelve el cuello de botella
**Historia.** Intentás usar el hosting de DonWeb que tenías en mente; el plan shared (cPanel/PHP) no levanta un proceso Streamlit de larga duración. Migrás a un VPS y te encontrás administrando nginx, TLS, systemd y backups un fin de semana entero. La app funciona local pero nunca queda publicada de forma estable.
**Supuesto.** Que el hosting mencionado sirve para esta stack.
**Señales tempranas.** Más de un fin de semana peleando con el server; la app "anda en mi máquina" pero no online.

### 4 · Datos de mercado ARG sin fuente confiable
**Historia.** La sección Cartera necesita MEP y precios de bonos/CEDEARs/ONs. Hoy los cargás a mano en el Excel. Al automatizarlo descubrís que no hay una API gratis y estable para el mercado local; los scrapers se rompen en días. La cartera queda mostrando precios viejos y dejás de confiar en ella.
**Supuesto.** Que lo manual del Excel se automatiza fácil en la web.
**Señales tempranas.** El primer consumo de precios ARG falla o se cae a los pocos días.

### 5 · Se pierde la lógica validada del Excel
**Historia.** Portás el parser de movimientos y la matemática de renta fija a Python. Sin un test de reconciliación fila-a-fila (como el que sí tenés en Mis-Finanzas), los números difieren del Excel. No sabés cuál está bien, y ante la duda volvés a la planilla que "siempre anduvo".
**Supuesto.** Que portar es traducir fórmulas, no re-validar resultados.
**Señales tempranas.** Cartera de la app ≠ cartera del Excel y no hay test que arbitre.

### 6 · Alcance infinito / burnout
**Historia.** Tres dominios ricos, un dev, tiempo libre. Sin recorte brutal, saltás entre secciones sin cerrar ninguna. A los dos meses hay un monorepo a medias, peor que los tres proyectos que ya andaban por separado.
**Supuesto.** Que alcanzan tiempo y ganas para las tres secciones en paralelo.
**Señales tempranas.** Un mes sin commits; o tres secciones al 40% y ninguna al 100%.

### 7 · Multiusuario prematuro
**Historia.** Diseñás desde el día 1 para SaaS: planes, aislamiento, billing. Todo eso retrasa el momento en que la app te sirve a vos. Construís plataforma antes de tener producto.
**Supuesto.** Que "escalable" hay que construirlo ahora, no dejarlo preparado.
**Señales tempranas.** Discutís billing/planes antes de usar la app a diario.

## Síntesis

- **Más probable:** el refactor de "una sola app" se come el proyecto (modo 1).
- **Más peligroso:** fuga de datos financieros personales al repo público (cruce de modos 2 + operación de git).
- **Supuesto oculto:** que "integrar bajo un login" es un beneficio neto, cuando puede ser el costo (romper lo que hoy es gratis y estable).
- **Revisión #1 (la más importante):** no arrancar con "una sola app". Monorepo con `core/` compartido + tres packages, y Fase 1 = shell con login que embebe las apps casi tal cual. Repo privado desde el commit 0. Alcance del MVP congelado a integración.

Ver `Premortem - Superapp Finanzas.html` para el informe visual completo.
