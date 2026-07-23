# En humano 🧑‍💻→🙂

Este archivo cuenta, **en lenguaje llano y sin tecnicismos**, qué se fue haciendo en el proyecto y para qué sirve. Es para Franco (y para cualquiera que no quiera leer código ni bitácoras técnicas). Si algo acá suena a jerga, está mal escrito.

**Reglas de este archivo:**
- Lo actualiza el Claude que trabaja, **cada vez que completa un avance importante** (y como mínimo una vez por sesión).
- Cada entrada responde tres cosas: **qué se hizo**, **para qué te sirve a vos**, y **qué sigue**.
- Nada de nombres de archivos raros ni términos técnicos sin traducir. Si hay que nombrar algo técnico, se explica al lado con una analogía.

---

## 23 de julio de 2026 (noche) — La app ya carga tu cartera y se autoexamina contra el Excel

**Qué se hizo (en criollo):**
Enseñamos a la app a **cargar tus movimientos en su memoria** (leyendo el archivo del broker) sin duplicar nada si subís el mismo archivo dos veces, y a **calcular cuántas unidades tenés de cada cosa**. Lo más importante: dejamos una prueba automática que agarra los movimientos, calcula las tenencias por su cuenta, y **las compara contra tu planilla** — y dan idénticas. Es la "regla de oro" del proyecto funcionando: la app no vale hasta que sus números coinciden con el Excel.

**Para qué te sirve:**
Es la garantía de que, cuando la cartera esté en pantalla, los números van a ser los de siempre — verificados, no inventados.

**Qué sigue:**
Conectar los precios de mercado: el dólar MEP de cada fecha (para valuar con el cambio correcto) y las cotizaciones de acciones/CEDEARs/bonos.

---

## 23 de julio de 2026 (tarde) — Tu Excel al día, cuadrado con el broker, y la "memoria" de la app lista

**Qué se hizo (en criollo):**
- Actualizamos tu `Inversiones.xlsx` con el resumen completo de movimientos que bajaste de inviu y lo dejamos **cuadrado con lo que el broker dice que tenés hoy**: las 20 posiciones coinciden exactas. (Guardé tu Excel viejo como respaldo por las dudas.) De paso salieron a la luz y se arreglaron dos cositas de la planilla: una columna de moneda que estaba corrida y un ticker (NBIS) que no aparecía. El único ajuste "a mano" fue SPY, por el cambio de conversión del CEDEAR que vos confirmaste. Le puse el dólar MEP del día y el Bitcoin al cierre de ayer.
- Lo más importante: el "lector" que hicimos ayer procesó tus movimientos REALES y reprodujo solo él 19 de 20 posiciones — la prueba más fuerte de que calcula bien.
- Y arrancamos la app: construimos la **"memoria"** donde va a vivir tu cartera (las tablas de la base de datos), separada y privada, con una traba para que no se dupliquen movimientos si volvés a subir el mismo archivo.

**Para qué te sirve:**
Ya tenés un punto de partida confiable y actualizado, y la app tiene dónde guardar tu cartera. A partir de acá, actualizarla va a ser subir el archivo del broker y listo.

**Qué sigue:**
Cargar de verdad tus movimientos en esa memoria (con una prueba que compara contra el Excel), y después conectar los precios de mercado para poner el dólar de cada fecha.

---

## 23 de julio de 2026 — El lector de tu cartera ya está hecho y probado

**Qué se hizo (en criollo):**
- Construimos la **primera pieza** de la cartera nueva: el "lector" que entiende el archivo que te da el broker. Sabe leer los **dos formatos** que usa tu broker (el viejo y el nuevo que apareció en mayo), reconoce cada tipo de movimiento (compra, venta, dividendo, caución, renta…), saca el ticker, y descifra si algo está en pesos o en dólares **sin fiarse de la etiqueta del archivo** (que a veces miente).
- Le pusimos **43 pruebas automáticas** que verifican que todo eso salga bien, con ejemplos calcados de tu propia planilla. Todo el proyecto quedó en verde (157 pruebas).
- Un detalle fino: encontré que en tu Excel la columna que dice la **moneda** está corrida ~30 filas (lee el dato de otra operación) — por eso algunos dividendos en dólares figuran como pesos. La app nueva no usa esa columna, la deduce sola, así que queda más precisa que la planilla. Y confirmé que la **fila 32 que tenías que borrar ya la borraste**: las dos celdas rotas quedaron sanas.

**Para qué te sirve:**
Es el cimiento para que, más adelante, actualizar la cartera sea subir un archivo y listo. Esta pieza es la que garantiza que ni un movimiento se lea mal.

**Qué sigue:**
La próxima pieza es la **memoria**: dónde y cómo la app guarda esos movimientos (con el dólar de cada fecha congelado), para después calcular posiciones y rendimientos.

---

## 19 de julio de 2026 — La cartera de inversiones ya tiene plano de obra

**Qué se hizo (en criollo):**
- Estudiamos tu Excel de inversiones a fondo y definimos juntos cómo va a vivir la cartera en la app: **igual que tus gastos** — la app guarda cada movimiento, vos cargás lo nuevo subiendo el archivo que te da el broker (o a mano), y ella calcula posiciones, rendimientos y ganancias. Los precios los va a buscar sola al mercado, con la opción de corregirlos a mano si hace falta.
- Antes de confiar en ningún número, la app se va a **examinar contra tu planilla**: sus cuentas tienen que dar exactamente lo mismo que tu Excel. Recién ahí se avanza.
- De paso, el estudio encontró dos cosas en tu Excel: **desde el 20 de mayo tu planilla no está sumando los movimientos nuevos** (el broker cambió el formato del archivo y las fórmulas no lo reconocen — 31 movimientos afuera, incluidas compras de junio), y dos celdas rotas con arreglo de 10 segundos ya indicado. La app nueva va a entender ambos formatos, así que va a estar más al día que la planilla.

**Para qué te sirve:**
Cuando esté construida, actualizar tu cartera será subir un archivo — sin fórmulas, sin pegar paneles — y vas a ver de verdad cuánto rindió cada cosa (con el dólar de cada fecha, no el de hoy).

**Qué sigue:**
La próxima sesión construye la primera pieza: el lector de movimientos del broker, con sus pruebas. Todo el plano quedó escrito para retomar sin perder nada.

---

## 17 de julio de 2026 (cierre) — Un susto, la lección, y todo funcionando

**Qué pasó (en criollo):**
Al publicar los espacios compartidos, la app pareció "olvidar" tus datos: te trató como usuario nuevo. El motivo: una regla vieja del sistema de actualización de la base chocó con la nueva y desenchufó tus datos de su lugar (sin borrarlos — siempre estuvieron ahí, más los backups diarios). Se encontró la causa, se arregló, y se agregó un mecanismo que repara solo ese enganche si algo parecido volviera a pasar. También quedaron dos pruebas automáticas que simulan exactamente este accidente para que no se repita jamás. Verificaste que está todo de vuelta y andando.

**Para qué te sirve:**
Además del arreglo, el sistema quedó más robusto que antes del susto: 114 pruebas en verde y una lección registrada para los próximos cambios de base de datos.

**Qué sigue:**
La Fase 3: tu cartera de inversiones dentro de la app, leyendo tus Excel, con la regla de oro de que cada número tiene que coincidir exactamente con la planilla.

---

## 17 de julio de 2026 — Los gastos compartidos con Agustina, listos

**Qué se hizo (en criollo):**
- La app ahora tiene **espacios**: tu espacio personal de siempre, y espacios compartidos que podés crear para manejar una caja en común (la casa, un viaje). Cada espacio tiene sus propios gastos, categorías y presupuesto — nada se mezcla.
- Para invitar a alguien generás un **código** (se muestra una sola vez, como una llave) y la otra persona lo usa para unirse desde su propia cuenta.
- Un **cartel de color** te dice siempre dónde estás parado: violeta = personal, verde = compartido. Así no cargás un gasto en el lugar equivocado — el error más probable según el ensayo de fracaso que hicimos.
- Al cargar un gasto en un espacio compartido podés **firmar** quién lo hizo.
- Todo respaldado por pruebas automáticas: 112 en verde, incluyendo una que verifica que tu espacio personal y el compartido nunca se contaminan entre sí.
- Yapa: las correcciones que pediste del tablero de acciones (categorías más claras, filtros que no se resetean, el botón "?" con la metodología, y NU/SATL bien clasificadas).

**Para qué te sirve:**
Vos y Agus pueden anotar los gastos de la casa en un solo lugar, viendo quién cargó qué, sin renunciar cada uno a sus finanzas personales privadas.

**Qué sigue:**
Publicar todo esto en internet (tu comando de deploy), probarlo entre los dos, y después la Fase 3: tu cartera de inversiones en la app.

---

## 15 de julio de 2026 — Una sola puerta de entrada, y el tablero de acciones adentro

**Qué se hizo (en criollo):**
- Ahora la app tiene **una sola puerta**: te logueás una vez y arriba aparecen dos secciones — tus gastos de siempre y una nueva sección de Inversiones.
- Adentro de Inversiones ya vive tu **tablero de scoring de acciones**: las 100 empresas con sus puntajes, filtros y las "triple corona". La app no calcula nada: le pide los datos ya cocinados al robot que corre solo todas las noches en GitHub. Si un día ese servicio no responde, la app muestra la última copia guardada y avisa — no se rompe.
- Las secciones de Cartera y Mercado en vivo ya tienen su lugar reservado, con un cartel claro de "llega en Fase 3/5" (sin promesas vacías).
- Todo pasó por las pruebas automáticas: 101 en verde.

**Para qué te sirve:**
Es la primera vez que la "superapp" se siente superapp: un login, dos mundos. Y el tablero de acciones que antes vivía en una página aparte ahora está integrado con tu día a día financiero.

**Qué sigue:**
Publicar esta versión en internet (un comando tuyo) y elegir el próximo paso: la cartera de inversiones (Fase 3) o terminar el espacio familiar de gastos compartidos.

---

## 10 de julio de 2026 (tarde) — Tu app de gastos ya vive en la casa nueva, con todas tus cosas

**Qué se hizo (en criollo):**
La mudanza completa, en un solo día:
- Todo el código de tu app de gastos de siempre se mudó adentro del proyecto nuevo. No se reescribió nada: se movió con cuidado y se volvió a conectar cada pieza.
- Antes de dar nada por bueno, corrimos las 97 pruebas automáticas que verifican que las cuentas den igual que siempre. Pasaron todas.
- La app quedó publicada en internet en su nueva dirección (superapp-finanzas.fly.dev), y le mudamos también **tus datos reales** desde la app vieja. Entraste, te logueaste y comprobaste que está todo.
- La app vieja sigue encendida como red de seguridad; en unos días, si todo anda bien, se apaga.

**Para qué te sirve:**
Ya no tenés dos mundos separados: tu app de gastos vive dentro de la futura superapp, funcionando igual que siempre y con tus datos al día. Sobre esta base se van a ir sumando las secciones de inversiones.

**Qué sigue:**
La Fase 2: armar la "entrada única" — un solo login que te lleve a Finanzas o a Inversiones — y traer el tablero de scoring de acciones que ya generás automáticamente.

---

## 10 de julio de 2026 — Los cimientos quedaron terminados

**Qué se hizo (en criollo):**
Se cerró todo lo que faltaba de la etapa de preparación:
- Todo el proyecto quedó guardado en tu GitHub (tu "caja fuerte" de código en internet, visible solo para vos).
- Se instaló y **se puso a prueba** el candado anti-accidentes: intentamos a propósito subir una planilla de Excel y el sistema la rechazó, como debía. Ese candado funciona tanto desde acá como desde el programa que usás vos en Windows.
- Se publicó una página de prueba en internet (un simple "hola mundo") para confirmar que el "terreno" donde va a vivir la app funciona. Vos mismo verificaste que se ve bien. Cuando nadie la mira, no gasta prácticamente nada.
- Hubo un par de sustos técnicos porque la carpeta vive en OneDrive (que a veces sincroniza a medias), pero se detectaron y arreglaron sin perder nada, y quedó anotado cómo evitarlos.

**Para qué te sirve:**
Ya no hay riesgo de que tus datos de plata se suban por error, y ya existe el lugar en internet donde va a vivir la app. La obra puede empezar.

**Qué sigue:**
La Fase 1: mudar tu app actual de finanzas personales adentro de este proyecto nuevo, sin cambiarle nada, y verificar que todos sus números sigan dando igual.

---

## 9 de julio de 2026 — Armamos los cimientos del proyecto

**Qué se hizo (en criollo):**
Todavía no se programó nada de la app. Lo que hicimos fue *planificar bien antes de construir*, como cuando antes de levantar una casa se hacen los planos, se elige el terreno y se ponen las reglas de la obra. En concreto:
- Pensamos qué podría salir mal y cómo evitarlo (una especie de "ensayo de fracaso" para no tropezar después).
- Escribimos el plan maestro: qué va a tener la app, en qué orden se construye, y dónde va a "vivir" en internet.
- Dejamos armada la estructura de carpetas vacías y una serie de "cuadernos de obra" para que distintos asistentes puedan seguir el trabajo sin pisarse.
- Revisamos herramientas ya hechas por otros (gráficos, fuentes de datos del mercado argentino, etc.) para no reinventar la rueda.

**Para qué te sirve:**
Que cuando empiece la construcción, sea ordenada, barata y difícil de romper. Y que puedas seguir el proyecto en varias conversaciones distintas sin perder el hilo.

**Qué sigue:**
La "Fase 0": subir todo a tu GitHub como repositorio privado, poner un candado que impida que se suban por error tus datos de plata, y publicar una página de prueba vacía en internet para confirmar que el "terreno" funciona.

---

<!-- Plantilla para la próxima entrada:
## FECHA — Título simple de lo que se logró
**Qué se hizo (en criollo):** …
**Para qué te sirve:** …
**Qué sigue:** …
-->
