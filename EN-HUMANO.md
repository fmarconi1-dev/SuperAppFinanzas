# En humano 🧑‍💻→🙂

Este archivo cuenta, **en lenguaje llano y sin tecnicismos**, qué se fue haciendo en el proyecto y para qué sirve. Es para Franco (y para cualquiera que no quiera leer código ni bitácoras técnicas). Si algo acá suena a jerga, está mal escrito.

**Reglas de este archivo:**
- Lo actualiza el Claude que trabaja, **cada vez que completa un avance importante** (y como mínimo una vez por sesión).
- Cada entrada responde tres cosas: **qué se hizo**, **para qué te sirve a vos**, y **qué sigue**.
- Nada de nombres de archivos raros ni términos técnicos sin traducir. Si hay que nombrar algo técnico, se explica al lado con una analogía.

---

## 14 de octubre de 2026 — Chau, Inversiones

**Qué se hizo.** Saqué de la app toda la sección de Inversiones: la cartera (tus posiciones, rendimientos, bonos, vencimientos, la comparación contra el mercado) y el lugar reservado para "Mercado en vivo". Ahora la app es solo Finanzas Personales: entrás y estás directo en tus gastos e ingresos, sin la barra para cambiar de sección.

**Lo que NO borré.** Tus movimientos de la cartera siguen guardados en la base de datos, quietos, como cajas en un depósito: nadie las abre, pero están. Y el programa que los mostraba queda en el historial del proyecto, así que si algún día cambiás de idea, se puede volver a armar. Borrar esos datos de verdad es otra decisión, y es tuya: no tiene vuelta atrás.

**Para qué te sirve.** Menos cosas que mantener: la app ya no depende de tres servicios de afuera (cotizaciones, dólar MEP, cronogramas de bonos) que a veces se caían, y las pruebas automáticas pasaron de 909 a 359, todas las que quedan son de lo que sí usás. Todas en verde.

**Qué sigue.** Revisarlo, guardarlo y publicarlo cuando quieras (hasta que lo publiques, la app online sigue mostrando Inversiones). Después, la etapa grande: que los gastos salgan solos de los resúmenes del banco.

---

## 27 de septiembre de 2026 — Tu backup llevaba un mes apagado

**Lo importante primero.** La última copia de tus datos en tu PC era del **26 de agosto**. La tarea que tenía que hacerla todas las mañanas **no existía** en tu computadora, y aunque hubiera existido habría fallado: dependía de que tu sesión de Fly estuviera abierta, y esa sesión vence sola. Es como un portero que necesita que le abras la puerta para salir a trabajar: a las 9 de la mañana no hay nadie para abrirle. Y nada te avisaba.

**Qué hice.** Saqué una copia en el momento: tus 406 transacciones están a salvo y verificadas. Esa misma copia me confirmó que la publicación del 23/9 quedó bien. Y arreglé el backup para que no vuelva a pasar:
- ahora puede usar una **llave propia**, que solo sirve para esta app y dura un año, en vez de tu sesión;
- si algo falla, **te deja un archivo en el Escritorio** que dice qué pasó y qué hacer, y se borra solo cuando vuelve a andar;
- el comando que revisa el estado ahora también te dice si la tarea existe y si la llave está por vencer.

Lo probé haciéndolo fallar a propósito: se da cuenta en 2 segundos y te deja el aviso.

**Lo que te toca a vos** (la llave es una credencial y la tarea queda instalada en tu PC, así que no las hago yo). Son dos comandos, una sola vez, desde la carpeta de la app:
1. `powershell -ExecutionPolicy Bypass -File scripts\guardar_token_fly.ps1` — crea y guarda la llave (yo nunca la veo).
2. `powershell -ExecutionPolicy Bypass -File scripts\programar_backup.ps1` — deja el backup programado todos los días a las 9.

**Tres mejoras chicas más:**
- El "error" que viste en los registros al abrir Transacciones no era un error: era un aviso de la herramienta por una combinación que hacemos a propósito, la que hace que después de cargar un gasto el motivo quede elegido. Lo silencié sin tocar ese comportamiento.
- El login ahora tiene 30 pruebas automáticas, incluida una que asegura que nadie pueda entrar por la cuenta interna sin contraseña. **Encontré algo para decidir:** si escribís "Franco" con mayúscula, que es lo que hace el celular solo, no te deja entrar. Se puede arreglar, pero toca la seguridad del login, así que prefiero que lo decidas vos.
- La comparación "contra el mercado" ya no puede usar sin avisarte un índice sin dividendos (lo que haría que tu cartera pareciera mejor de lo que es). Hoy no pasaba: lo dejé cubierto por si pasa.

**Ningún número tuyo cambió.** Lo comparé antes y después sobre la copia de hoy.

**Qué sigue.** Los dos comandos de arriba. Después, cuando quieras: decidir lo de las mayúsculas del login, o arrancar la etapa grande (que los gastos salgan de los resúmenes del banco).

---

## 22 de septiembre de 2026 — Una revisión a fondo antes de arrancar lo nuevo

Hoy no agregamos nada: revisamos la app entera buscando problemas escondidos, arreglamos los que aparecieron y ordenamos la casa. **Ninguno de tus números cambió**: comparé tu cartera y tus gastos (sobre una copia de la base de producción) antes y después de todos los arreglos, y dieron idénticos, peso por peso.

**Lo más serio que encontramos.** Si alguna vez apretabas el botón para que un pagaré "rinda una tasa", **la pantalla de Cartera se caía entera y ya no volvía**: no había forma de deshacerlo desde la app. Estuvo escondido dos meses porque nunca lo usaste. Ya está arreglado, hay un botón para quitar la tasa y, como decidiste, **el precio que informa el broker manda sobre la tasa**.

**Otro que te habría confundido.** Cuando Docta (la fuente de los cupones de tus bonos) o Yahoo (la de los sectores) no contestaban —porque se caían o porque se te acababan las 15 consultas del día—, la app anotaba el bono como "no existe en la fuente" **para siempre**, y encima te decía que era normal. Es como si el cajero de un banco estuviera en el almuerzo y concluyeras que no tenés cuenta. Ahora distingue "no contestó" (lo vuelve a intentar) de "no lo tiene" (lo anota).

**Tres cosas más que no se veían:**
- Cada vez que la app se reiniciaba —y en Fly eso pasa seguido— volvía a aplicar unos arreglos viejos a tus categorías. Si alguna vez cambiabas "Compra Divisa" de grupo, se te iba a volver a cambiar sola. Ahora esos arreglos corren una sola vez.
- Si en tus CSV había un importe mal escrito (una letra O en vez de un cero, por ejemplo), entraba como un gasto de $0 sin avisar. Ahora te avisa cuál fila fue. Revisé tus CSV reales: no tienen ninguno.
- El comando para reimportar tus CSV desde la consola estaba roto, y nadie se había enterado.

**Para qué te sirve lo demás.** Saqué código que no usaba nadie, sincronicé los documentos que contaban historias distintas (esta vez los revisé todos, para que no se repita lo de la tarea descartada que seguía apareciendo como "próximo paso") y agregué una red nueva: **tests que abren las pantallas de verdad**, como lo harías vos. Hasta ahora los tests revisaban las cuentas pero ninguno abría una pantalla, y por eso los errores los encontrabas vos. Comprobé que el test nuevo habría cazado el problema del pagaré.

**Qué sigue.** Te toca a vos: revisar y subir el cambio (GitHub Desktop) y publicarlo en internet. Después, cuando vos digas, arrancamos la etapa grande que ya aprobaste: que Finanzas Personales se alimente de los resúmenes del banco en vez de tu memoria.

---

## 27 de agosto de 2026 (tercera parte) — Por qué las apps de gastos se abandonan, y qué vamos a hacer distinto

Hoy no tocamos código: tomamos una decisión que cambia hacia dónde va la app.

**Tu pregunta.** Todas las apps de finanzas personales fallan igual: dejás de cargar unos días, después ponerte al día es un garrón, y abandonás.

**Lo que encontramos.** El diagnóstico de siempre es "el usuario se olvida", y por eso todo el mundo propone recordatorios y felicitaciones. Está mal. El problema es que **la app solo es exacta si vos sos disciplinado**, y eso no se sostiene. Hay un número que lo explica: **pasadas 72 horas ya no te acordás, así que cargar los gastos se convierte en copiarlos del resumen del banco.** Y si vas a terminar mirando el resumen igual, el resumen tendría que haber sido la fuente desde el principio.

**Lo mejor: esto ya lo resolviste una vez.** Tu Cartera nunca tuvo este problema, porque la foto del broker es un ancla que no se olvida. Si vos no cargás nada, tu patrimonio sigue siendo correcto. Finanzas Personales no tiene ancla: su verdad es la suma de lo que tipeaste. Vamos a darle la misma ancla.

**Cómo queda.** Tres fuentes que no dependen de tu memoria: los movimientos de la caja de ahorro (donde está todo tu débito), los resúmenes de tus dos tarjetas, y WhatsApp solo para el efectivo. Son **3 descargas por mes** en lugar de unos 90 actos de acordarte. Y lo lindo: hasta el efectivo tiene ancla, porque **las extracciones figuran en tu cuenta** — la app va a saber cuánta plata en efectivo pasó por tus manos aunque no sepa en qué se fue, y te va a decir cuánto le falta en vez de mentirte.

**Lo que de verdad cambia:** con esto, **atrasarte deja de costarte datos**. Si no abrís la app en tres semanas, los archivos siguen ahí, exactos. Hoy atrasarte te cuesta la información para siempre.

**Dos cosas que frené a tiempo.** Vos propusiste borrar la categoría "Pago tarjeta": no se puede, porque hoy es el único rastro de tu consumo con tarjeta en todos los meses cerrados, y borrarla te derrumba el gasto de 2025 y 2026. Y yo había propuesto una fecha de corte fija, que también estaba mal: como el pago de la tarjeta corresponde a compras del mes anterior, el primer mes se habría perdido entero. La regla quedó mejor: **el pago se descuenta solo si el resumen que lo explica fue cargado.** Si te olvidás de cargar un resumen, no perdés la plata, perdés el detalle.

**Qué sigue.** Reescribimos el plan: son 7 pasos, unas dos semanas y media. Empezamos por lo más aburrido y más importante — darle a la app la noción de "cuentas" — con una condición: **ningún número de tu historia se puede mover un peso.** Para el segundo paso voy a necesitar que me pases un export real de los movimientos de tu cuenta.

---

## 27 de agosto de 2026 (segunda parte) — Cuatro cosas chicas, y una que casi te rompe el próximo deploy

Pediste algo más corto que el importador de CSV y terminamos haciendo las cuatro opciones. Te las cuento de la más útil a la más invisible.

### 1. El AE38 ya te muestra cuándo vence

Te acordás que en agosto te avisé que la app te decía el vencimiento de **uno solo** de tus tres bonos vivos. El AE38 se llama *"Bono USD 2038"*, y ese 2038 es parte del nombre, no una fecha de vencimiento — la app hacía bien en no adivinarla.

Resulta que **el dato ya lo tenías**. En agosto conectamos Docta, que baja el calendario de pagos de cada bono y lo guarda. Y la última fecha de ese calendario **es** el vencimiento. Estaban las dos cosas en tu base de datos y no se hablaban entre ellas. Ahora sí.

Le puse una condición que me parece importante: si el calendario del bono y la descripción de tu Excel dicen fechas **distintas**, la app no elige una y tira la otra en silencio. Te muestra las dos y te avisa, porque si difieren es que una está mal y conviene que la mires vos.

### 2. Ahora sabés si le ganaste al mercado

Panel nuevo en Cartera: **"Contra el mercado"**. Elegís S&P 500 o Merval y te dice cuánto tendrías hoy **si hubieras puesto la misma plata, en las mismas fechas, en el índice** en lugar de en tus papeles.

Ojo con por qué está planteado así, porque es la única forma honesta. La cuenta fácil sería "vos hiciste +36%, el S&P hizo +52%, perdiste". Eso es tramposo: vos fuiste metiendo plata de a poco, en 24 momentos distintos a lo largo de casi dos años. El índice, en esa comparación, es como si hubiera puesto todo el primer día. Son dos preguntas distintas. La comparación buena simula **tus** aportes, en **tus** fechas.

Un detalle que suma varios puntos: uso el índice **con dividendos reinvertidos**. Tus dividendos la app ya te los cuenta; si te comparaba contra un S&P sin dividendos te estaba regalando como un punto y medio por año.

### 3. La que casi te rompe el próximo deploy

Esta era la tarea más aburrida de las cuatro —"congelar las versiones de las librerías para que la app se arme siempre igual"— y fue donde apareció el problema.

Cuando fui a mirar qué versiones instalar, me encontré con que **la librería que hace todas las cuentas de tablas (pandas) sacó una versión nueva mayor**, la 3.0, con cambios que rompen cosas. Si yo congelaba "lo último que hay hoy", tu próximo deploy habría sido **la primera vez en la historia que tu app corre con esa versión** — y te ibas a enterar en producción.

Así que congelé la versión anterior, la que tus pruebas vienen usando. Y después lo verifiqué de verdad: armé un entorno limpio con esas versiones exactas y corrí las 679 pruebas encima. Todas pasaron.

Actualizar a pandas 3 en algún momento se puede, pero es una tarea con su propio día: hay que correr todo y mirar que los números de la cartera no se muevan. No algo que pase de casualidad un martes.

### 4. Plomería (no vas a ver nada)

Ordené un enredo interno: había dos partes del código que se necesitaban mutuamente, y por ese enredo los módulos que hacen las cuentas de tus gastos cargaban una librería de encriptación de contraseñas **para leer un número**. Ya no. Dejé pruebas que hacen que el enredo no pueda volver.

---

### 5. Y sobre el final, partimos la pantalla de Cartera

Me diste el OK y lo hice. El archivo de la pantalla de Cartera tenía **1.990 líneas** y era, por lejos, el que más se toca del proyecto: **27 de los 97 commits de la historia** pasaron por ahí. El problema no era que fuera grande, era que para cambiar *una* cosa había que abrirlo entero — y así fue como una vez se coló una función usada sin importar, que reventaba recién al apretar el botón.

Ahora hay **un archivo por panel**: la composición, el benchmark nuevo, los vencimientos, cuándo cobrás, las operaciones cerradas, la plata quieta, los ajustes, la subida de archivos. El archivo principal quedó en 760 líneas y ya no hace de todo: decide quién puede entrar, arma los números de arriba y llama a cada panel en orden.

**Lo importante: no cambié nada de lo que hace.** Fue mudar código de un archivo a otro. Y no te lo digo de palabra — comparé una por una las funciones contra la versión anterior: **23 idénticas, ninguna perdida, ninguna duplicada**. Las dos que difieren son las que había tocado a propósito esta misma tarde.

Se rompieron 5 pruebas y estuvo bien que se rompieran: eran pruebas que iban a buscar funciones *por nombre dentro del archivo viejo*. Las apunté al lugar nuevo.

---

**Cómo quedó todo.** Las pruebas pasaron de 664 a **740**, todas en verde. No se tocó ni la estructura de la base ni tus datos.

**Qué sigue.** Vos: subir esto. Ya no queda nada esperando tu OK — las dos propuestas que venían del 18 de agosto están hechas. Lo próximo grande es el importador de CSV cuando quieras encararlo.

---

## 27 de agosto de 2026 — El cuaderno de "qué sigue" te estaba mandando a hacer algo que ya habías decidido no hacer

**Qué se hizo.** Repasé la app entera para arrancar la jornada y me encontré con algo que conviene contarte tal cual: **el archivo que dice "próximo paso" te apuntaba a una tarea que vos mismo descartaste el 4 de agosto.**

Era la de "voz consistente y celebrar hitos" (que la app te felicite por la transacción número 10, la 100, el primer año). La miraste ese día y dijiste que no valía la pena, que era cosmética y no te resolvía nada. Eso quedó bien anotado en el archivo de ideas… **pero nadie lo borró del archivo de "qué sigue"**. Y como la regla del proyecto es "si dos papeles se contradicen, gana el de qué sigue", la próxima sesión habría arrancado justo por ahí.

Ya está corregido, y con el motivo escrito al lado para que no vuelva a pasar. **El próximo paso real de la fase actual es el importador inteligente de CSV**: subir el resumen de cualquier banco y que la app sola entienda qué columna es qué y te sugiera las categorías. Con una condición que no es negociable: **te muestra una vista previa antes de tocar nada**, porque si se equivoca categorizando no hay forma de que te enteres solo.

**Las otras dos cosas que no cerraban.** El mapa de fases decía que la Cartera seguía "en curso" cuando la cerraste hace un mes, y el archivo de ideas daba por pendientes tres cosas que ya están hechas (la TIR, la duration y el calendario de cobros de tus bonos). Todo sincronizado.

**Una pregunta para vos.** La última vez que hay constancia de que subiste la app a internet fue el **5 de agosto**. Pero el 13 y el 14 se hizo el panel de renta fija (el calendario de cuándo cobrás cada bono). Si nunca lo subiste, ese panel existe en tu computadora y en GitHub, **pero no en la app que abrís desde el celular**. Vale la pena que lo chequees.

**Y una limpieza.** La carpeta `Borrar` tenía **355 archivos basura** acumulados desde principios de agosto — casi 6 MB de restos que deja git cuando trabaja sobre OneDrive. Vaciada. Dejé adentro a propósito el código viejo del scoring y dos copias de respaldo, porque esos los decidís vos.

**Para qué te sirve.** Esto no agrega nada a la app, pero evita que la próxima sesión (conmigo o con quien sea) arranque construyendo algo que ya habías dicho que no.

**Qué sigue.** Vos: subir estos cambios (es todo texto, riesgo cero) y chequear las dos cosas de arriba — el respaldo diario programado y si el panel de bonos llegó a internet. Después arrancamos con el importador de CSV, si te parece bien. Y siguen esperando tu OK las dos propuestas del 18 de agosto: partir la pantalla de Cartera en pedazos más chicos y un arreglo de plomería interna.

---

## 18 de agosto de 2026 — El proyecto ahora tiene mapa (y el archivo de estado dejó de ser una novela)

**Qué se hizo.** Dos cosas de orden, ninguna toca la app que usás:

1. **Le puse un mapa al proyecto.** Un archivo nuevo (`MAPA.md`) que funciona como el índice de un libro: dice qué hay en cada carpeta y, sobre todo, tiene una tabla de "si buscás tal cosa, andá acá" — dólar MEP, backups, el formulario de gastos, lo que sea. Además, cada carpeta tiene ahora una ficha corta con sus trampas conocidas (esas cosas que costaron caro descubrir, como "el orden de importación importa" o "los bonos vienen multiplicados por 100"). El mapa se regenera solo cada vez que se hace un commit.

2. **Adelgacé `ESTADO.md`.** Tenía 285 líneas donde el 80% era historia de fases ya cerradas; cada Claude nuevo tenía que leerse todo eso antes de arrancar. Ahora son 58 líneas con la foto de hoy y el próximo paso. **No se borró nada:** la historia completa está guardada tal cual en `docs/archivo/`.

**Para qué te sirve.** Cada sesión conmigo (o con quien sea) arranca más rápido y más barata: en vez de releer medio proyecto para ubicarse, se lee un índice de dos páginas. Y las lecciones aprendidas ya no viven solo en la memoria de las bitácoras largas — están en la ficha de la carpeta donde muerden.

**Qué sigue.** Vos: commitear y pushear esta sesión (todo es documentación, no hay riesgo). Después seguimos con la Fase 4, y quedan dos propuestas mías esperando tu OK: partir la pantalla de Cartera en pedazos más chicos y un arreglo menor de plomería interna.

## 5 de agosto de 2026 — Vencimientos, y las correcciones que pediste

**Lo nuevo: la app te dice qué se te vence.** Y lo mejor es que **no hubo que cargar nada**: las fechas ya estaban escritas en tu Excel, adentro del nombre de cada bono ("Bono Tesoro Nacional Vto. 30/11/2029"). La app ahora las lee sola.

Ojo con una cosa, para que no te ilusiones de más: de tu renta fija **viva** solo resuelve el AN29. El AE38 y el pagaré no traen fecha en ningún lado y los tenés que poner a mano si los querés. Y para el AE38 la pregunta está mal planteada igual: **ese bono no vence hasta 2038, pero te empieza a devolver plata en julio de 2027**. Lo que te sirve saber no es cuándo termina sino cuándo cobrás — y eso es lo que sigue.

**Investigué de dónde sacar eso** (el calendario de cobros de cada bono, que además destraba la TIR esperada y la duration). Encontré una fuente que sirve: **Docta Capital**. Necesito que crees una cuenta gratuita en `app.docta.com.ar` cuando quieras seguir por ahí. El plan gratis da 15 consultas por día, que parece poquísimo pero alcanza de sobra: el calendario de un bono no cambia, se baja una vez y se guarda.

**Las cinco correcciones que pediste:**

1. **Editar transacciones.** Era peor de lo que pensabas: una transacción con el gasto cargado **en negativo** quedaba **imposible de editar**, ni siquiera para cambiarle la categoría. Arreglado.
2. **Scoring eliminado.** Los sectores de tu cartera ahora los resuelve Yahoo solo, que ya los cubría todos. Tu tablero público de scoring sigue funcionando aparte: nunca fue parte de esta app.
3. **Números con puntos de miles**, en las tablas igual que en las tarjetas de arriba.
4. **"El número que importa"** sacado.
5. **"Cómo está repartida" rehecha.** Los cuadros van ahora **uno debajo del otro y a lo ancho**, con gráficos de barras. Además de que ya no se cortan, es más honesto: son cortes sobre cosas distintas (toda la cartera, tus acciones, tus bonos), y ponerlos al lado daba a entender que se comparaban entre sí. Y para los bonos agregué un corte nuevo: **quién te debe la plata** (el Estado, una provincia o una empresa), que es lo que de verdad define el riesgo de un bono — preguntarle el "sector" a un bono no significa nada.

**Lo que más me importa contarte de todo esto.** Al hacer el cambio de los números **rompí la pantalla Mensual**: quedó con un error que impedía que cargara. Y la batería de pruebas dijo *"532 correctas"* igual, porque tenía la información y la trató como si faltara una librería en vez de como código roto.

Lo encontraste vos, mirando que aparecían **2 pruebas salteadas donde tenían que ser 0**. Esa convención la habíamos escrito hace unos días justamente para eso. Ahora hay una prueba nueva que revisa que **todos** los archivos del proyecto se puedan leer, y falla diciendo el archivo y la línea. La probé al revés: con el error puesto, la caza.

---

## 4 de agosto de 2026 (arreglo) — La app se moría al cargar el ajuste de TXAR

**Qué viste:** cargaste el ajuste y la app se cayó entera con `database is locked`.

**Qué pasaba, con una analogía.** La base de datos es un cuaderno donde solo puede escribir una persona a la vez. Al guardar el ajuste pasaban tres cosas casi simultáneas: se sacaba una copia de seguridad, se escribía el dato, y la app se recargaba sola para mostrarte el resultado. Y **cada vez que la app se recarga volvía a revisar la estructura del cuaderno entero** — algo que solo hace falta una vez, cuando arranca. Las tres cosas quisieron el lápiz al mismo tiempo y la app, en vez de esperar su turno, se murió.

**Cuatro cosas arregladas**, y la tercera es la que me costó encontrar:

1. La revisión de la estructura ahora corre **una sola vez** cuando la app arranca, no en cada click. De paso, cada interacción tuya es más liviana.
2. Cuando el cuaderno está ocupado, ahora se **espera hasta 30 segundos** en vez de fallar.
3. **El punto 2 no alcanzaba solo.** La revisión de estructura pedía el lápiz de una forma en la que la espera *no se aplica*: SQLite se niega a esperar si la operación ya empezó leyendo, porque los dos podrían quedar trabados para siempre. Había que pedir el lápiz **desde el principio**, no a mitad de camino. Un renglón de diferencia.
4. La copia de seguridad ahora se saca **antes** de tomar el lápiz, no con el lápiz en la mano.

**Lo que más me importa:** dejé cinco tests que levantan dos procesos de verdad peleando por la base. Y lo probé al revés — volví a poner el renglón viejo y el test falló, lo saqué y pasó. Este error no vuelve sin que nos enteremos.

**Para qué te sirve:** más allá de que ahora podés cargar el ajuste, la app dejó de tener un punto donde dos operaciones normales podían matarla. Iba a volver a pasar en cualquier momento.

---

## 4 de agosto de 2026 — Los papeles que el broker "no te contó"

**El problema, en criollo:**
La app te avisaba de cinco operaciones raras. Tres decían lo mismo: *"vendiste 18 unidades pero solo tengo 9 registradas"*. Cuando eso pasa, la app cierra las unidades que le sobran **sin costo**, o sea como si te las hubieran regalado — y entonces el rendimiento sale disparatado.

**Por qué faltaban unidades.** Tres motivos distintos, todos legítimos:

- **BYMA** hizo un *split*: te dieron el doble de papeles y cada uno pasó a valer la mitad. No pusiste plata, pero ahora tenés 18 donde tenías 9. **El broker no informa eso como movimiento**, así que la app no se enteró.
- **TXAR**: esas 300 las tenías desde antes de que arrancara tu historial. Nunca hubo una compra que registrar.
- **GGALX**: eran cupones que te dieron gratis por tener acciones de Galicia. Los vendiste por $1.494 y esa plata es ganancia entera, pero la app no tenía de dónde sacar las unidades.

**Lo que se construyó:** un panel nuevo, **"Ajustar unidades que el broker no informa"**, donde cargás estos cuatro casos —split, papel que ya tenías, canje o cupón, y cambio de ratio de CEDEAR— y la app rehace las cuentas. Los ajustes viven aparte de los movimientos del broker, así que si algún día borrás todo y reimportás el Excel, **no se pierden**.

**El detalle que casi rompe todo (y es el que más me importa contarte).** Cuando cargás un papel que ya tenías, hay que decirle cuánto te costó. Pero esa plata **nunca apareció como depósito en tu cuenta**, porque entró antes de que empezara el registro. Si solo cargaba el costo, la app iba a contar los $186.751 que cobraste por las TXAR como **ganancia pura** — plata inventada.

La solución: cada vez que declarás el costo de algo que ya tenías, la app registra automáticamente ese mismo monto como capital que aportaste. Lo verifiqué con tus números reales y cierra al centavo: la ganancia total baja exactamente $233.439, que es exactamente el capital que se agregó. Un split no genera nada de esto, porque ahí no entró plata.

**Sobre TXAR y el "más o menos".** No te acordabas del precio de compra, pero sí de que la vendiste alrededor de **−20%**. Con eso la app despeja el costo hacia atrás: $233.439. Ahora bien, **un número recordado no es lo mismo que uno del resumen del broker**, y en seis meses no hay forma de distinguirlos si no se anota. Así que los ajustes se guardan con una marca de *aproximado* y la app te los muestra señalados. Si algún día conseguís el dato real, lo reemplazás.

**Otra cosa que salió de acá.** Mientras armaba el panel me olvidé de importar una función y el botón "Agregar ajuste" habría reventado en tu cara — el mismo tipo de error que el de "Agregar gasto" de la semana pasada. Así que dejé un test que **lee todos los módulos del proyecto y verifica que no usen nada que no exista**. Lo probé al revés: puse el error a propósito y el test lo cazó por nombre. Ese error ya no llega a producción.

**Para qué te sirve:** las tres operaciones ahora tienen resultado de verdad —BYMA empata en −$7,92, TXAR pierde $46.688, GGALX gana $1.494— y tu ganancia total deja de estar inflada en $233.439.

**Qué sigue:** cargar el ajuste de **GGALX**, que quedó pendiente.

> ⚠️ **Corrección (mismo día).** Acá decía que faltaba el costo real de las 100 acciones de GGAL y que eso inflaba una venta en ~$500.000. **Era un error mío, no un problema tuyo.** Esa fila está anotada **en dólares** (US$449 por 100 acciones, o sea US$4,49 cada una — que es el precio correcto que tenía GGAL en diciembre de 2024). Yo la verifiqué con una herramienta que **no conoce el tipo de cambio** de cada fecha, así que leyó "449" como si fueran 449 pesos en vez de 449 dólares. Tu app siempre lo tuvo bien: esa venta da **+$339.257**, no lo que yo dije. No tenés que buscar ningún dato.

---

## 4 de agosto de 2026 (arreglo) — El botón "Agregar gasto" rompía la app

**Qué pasó (en criollo):**
Tocaste **💸 Agregar gasto** desde el celular y la app se cayó entera con un error rojo. No era un mensaje amable: era la app muriéndose.

**Por qué:** el formulario tiene dos modos. El **rápido** (solo importe y motivo, el que usás del teléfono) y el **detallado**, con fecha, tipo y — si estás en el espacio familiar — el "Firmar como". Los dos modos terminan guardando por el mismo camino, pero el dato de *quién firma* solo se creaba en el modo detallado. Al guardar desde el rápido, la app buscaba algo que nunca había existido y explotaba.

Nunca se había notado porque el error solo aparece **al enviar** el formulario, no al abrirlo, y desde la computadora solés usar el modo detallado.

**Cómo quedó:** en modo rápido ya no se pregunta quién firma — esa es justamente la gracia del modo — y se asume que sos vos, el miembro activo del espacio. Si no estás en un espacio familiar, no cambia nada.

**Lo que me parece más valioso:** el test que dejé no revisa ese dato puntual. Revisa **la forma del error**: lee el código y verifica que ninguna variable que use el guardado esté definida en un solo modo. Si mañana agregamos un campo nuevo al formulario detallado y nos olvidamos del rápido, salta antes de llegar a tu celular. Lo probé al revés: volví a poner el bug a propósito y el test falló; lo saqué y pasó.

**Para qué te sirve:**
Que puedas cargar un gasto desde el celular sin que se caiga. Y que este tipo de error —el más tonto y el más molesto— tenga red.

**Qué sigue:**
Desplegar. Este arreglo va en el mismo lote que todo lo demás.


---

## 4 de agosto de 2026 — Un robot que revisa tu código cada vez que subís algo

**Qué se hizo (en criollo):**
Hasta hoy tus 352 pruebas corrían **solo si vos escribías el comando**. Ahora corren solas: cada vez que subas código a GitHub, un robot arranca una computadora limpia, instala todo desde cero y las ejecuta. Si algo se rompió, te avisa ahí mismo con una cruz roja.

Lo de **"computadora limpia"** es lo importante. Hoy pasó justo eso: tu Python local se había quedado sin las librerías del proyecto y las pruebas ni siquiera arrancaban. Nadie se había enterado. Y al revés también sirve: si algo funciona en tu PC porque tenés algo instalado a mano, en la máquina del robot va a fallar — que es exactamente cuando querés enterarte.

**Y de yapa, un segundo guardián.** Revisa que no se te haya colado ningún archivo con tus datos (Excel, base de datos, CSV, contraseñas) en el repositorio. Ya tenías un candado para eso, pero vive en tu máquina y se puede saltear con un comando. Este no: corre en GitHub y no hay forma de puentearlo.

**Para qué te sirve:**
Para no ser vos el único control de calidad. Y porque el repositorio es privado pero tiene tus finanzas adentro: que algo revise siempre que no se filtre nada vale más que el minuto que tarda.

**Qué sigue:**
La **voz consistente**: que la app te hable siempre igual y te celebre los hitos (la transacción número 10, la 100, el primer año). Un día de trabajo, riesgo cero.


---

## 30 de julio de 2026 (Fase 4) — Tus datos ahora tienen una copia de verdad

**Qué se hizo (en criollo):**
Antes de tocar ninguna mejora, fui a mirar cómo estaban los respaldos. No estaban bien.

- Las copias automáticas de tu base **viven en el mismo disco que la base**. Si ese disco se pierde, se pierden las dos juntas.
- **Importar la cartera no generaba ninguna copia.** Cargabas 585 movimientos y no quedaba punto de retorno.
- El script que bajaba la base a tu PC existía en la app vieja, pero **nunca se copió a la superapp**.
- El manual de operación eran cinco líneas que decían "placeholder".
- **Nunca probaste un restore.** Estaba en tu propia lista desde julio, sin tildar.

Lo importante: tu **cartera se puede reconstruir** del Excel si pasa algo. Tus **gastos personales no**. Esos 230 y pico de registros no existen en ningún otro lado.

**Qué hay ahora:**

| | |
|---|---|
| `backup_remoto.ps1` | Baja la base a tu PC y **la verifica**: si viene vacía o rota, falla y te avisa |
| `restaurar_backup.ps1` | El que faltaba. Por defecto hace un **simulacro** y no toca nada |
| Copias en la cartera | Importar, corregir un movimiento o subir una tenencia ahora deja punto de retorno |
| `RUNBOOK.md` | El manual de verdad: qué se pierde, cómo volver, y qué hacer si la app no responde |
| Ensayo automático | El ciclo completo (copiar → perder → volver) corre con los tests |

**Dos detalles que importan más de lo que parecen:** el script de restore **primero guarda lo que hay en producción** antes de pisarlo — si el restore sale mal, podés volver. Y borra dos archivos auxiliares que SQLite usa para las escrituras recientes: si no se borran, la base restaurada se mezcla con la vieja y queda corrupta. Eso es exactamente el tipo de detalle que uno descubre el peor día.

**Para qué te sirve:**
Para que un problema de disco, un borrado sin querer o un import equivocado sean un mal rato de veinte minutos y no la pérdida de dos años de datos.

**Qué sigue — dos cosas que tenés que hacer vos**, porque no las puedo hacer desde acá:

1. **Ensayar el restore una vez.** Corré el backup, después el restore en modo simulacro, y comprobá que los números coinciden con lo que ves en la app. No toca producción.
2. **Programar el backup diario** en el Programador de tareas de Windows. Los pasos están en el RUNBOOK.


---

## 30 de julio de 2026 — La app ya reconoce sola el sector de cada empresa

**Qué se hizo (en criollo):**
Tenías razón en las tres: TGNO4 faltaba, los ETF merecían su propia categoría, y la app tenía que poder averiguar los sectores sola en vez de depender de una lista.

Ahora los busca sola en Yahoo. **Cobertura: 18 de 18 papeles. Cero "Sin dato".**

Los ETF quedaron como pediste: **ETF · Oro**, **ETF · Uranio**, **ETF · Cobre**, **ETF · S&P 500**. La app los reconoce sola (Yahoo los marca como ETF y les deja el sector vacío, justamente porque un ETF es una canasta) y les arma la etiqueta con el subyacente.

**Cómo te queda la renta variable:**

| Sector | peso |
|---|---:|
| ETF · S&P 500 | 22,1% |
| Technology | 21,5% |
| Energy | 12,3% |
| Financial Services | 11,3% |
| Consumer Cyclical | 10,7% |
| Communication Services | 9,3% |
| ETF · Uranio, Oro y Cobre | 7,5% |
| Healthcare, Utilities e Industrials | 5,3% |

**Sobre TGNO4:** Yahoo lo clasifica como **Energy · Oil & Gas Midstream**, no Utilities. Las dos son defendibles — el estándar internacional GICS mete el transporte de gas dentro de Energía, aunque en Argentina TGN sea una utility regulada. Elegiste que mande Yahoo, así tu cartera queda comparable contra cualquier referencia. Igual dejé un panel para fijarle el sector a mano a cualquier papel: **tu valor gana siempre**.

**Y algo que apareció al sumar el nivel de industria:** tu 21,5% de "Technology" es en realidad **16% en semiconductores** (NVIDIA, TSMC y ASML juntos). El corte por sector lo escondía; el de industria lo muestra.

**Para qué te sirve:**
Para ver concentraciones que antes no se veían. Un 16% en un solo tipo de negocio es una apuesta, no una diversificación — y ahora la ves antes de la próxima compra.

**Qué sigue:**
Desplegar todo esto junto y usarlo unos días.


---

## 30 de julio de 2026 (cierre) — Cómo está repartida tu plata, y fin de la Fase 3b

**Qué se hizo (en criollo):**
La última pieza: una sección que te dice **dónde está parada tu plata**.

| | peso | qué es |
|---|---:|---|
| Renta fija | **60,1%** | el AE38, el AN29 y el pagaré |
| Renta variable | **38,3%** | tus 18 acciones y CEDEARs |
| Cripto | 1,3% | el bitcoin |
| Efectivo | 0,3% | lo que tenés en la cuenta |

Ahí hay una foto que quizás no tenías clara: **seis de cada diez pesos tuyos están en renta fija**, y de eso, más de la mitad es un solo pagaré.

Y dentro de tu renta variable, por sector: **Tecnología 21,5%**, Bancos 11,3%, Consumo 10,7%, Comunicaciones 9,3%, Energía 7,6%, y más chico Salud, Servicios públicos e Industria. Un **34,3%** queda como "Sin dato": son TGNO4 y tus cuatro ETFs (SPY, URA, GLD, COPX). A un ETF no le puedo poner un sector sin mentirte — el SPY es el mercado entero y el GLD es oro.

**Dos cosas que estaban mal en el primer intento y arreglé mirando tus números:**

La primera: **tu pagaré, que es el 34% de todo, aparecía como "Sin dato"**. Como nunca estuvo en la hoja Config de tu Excel, la app no sabía qué era. Ahora lo reconoce por el código (`#`) y lo cuenta como renta fija, que es lo que es.

La segunda: el cuadro por sector daba un "Sin dato" del **75%** y no servía para nada, porque metía adentro los bonos, el pagaré, el bitcoin y el efectivo. A esos no les *falta* el sector: **no tienen**. Ahora el cuadro mira solo tu renta variable, y ahí la cobertura real es del **66%**.

**Para qué te sirve:**
Para ver de un vistazo si estás donde querés estar. Si te parece mucho 60% en renta fija, o mucho 21% en tecnología, ahora lo ves antes de decidir la próxima compra.

**Con esto se cierra la Fase 3b.** La cartera ahora te dice: cuánto tenés, cuánto ganaste, en cuánto tiempo, **en qué acertaste operación por operación**, cuánto te rindió la plata quieta, y **dónde está parada**.

**Qué sigue:**
Desplegar esto y usarlo unos días. Después arranca la Fase 4, con las Finanzas Personales.


---

## 30 de julio de 2026 — Cuánto te rindió la plata quieta

**Qué se hizo (en criollo):**
Hasta ahora la app te mostraba cómo venían tus acciones y bonos, pero no decía nada de la plata que tenés parada. Y vos la hacés trabajar: colocaste **101 cauciones** desde diciembre de 2024, casi una por día hábil.

Ahora hay una sección nueva, **"La plata quieta"**, con tres números:

| | |
|---|---:|
| Interés de cauciones | **$33.365** — al **25,6% anual** |
| Dividendos cobrados (netos) | **$83.896** |
| Cuenta remunerada | **$3.301** |
| **Total** | **$120.562** |

**Importante: esto no es plata nueva.** Ya estaba adentro de tu patrimonio — el interés de las cauciones engordó tu efectivo y los dividendos ya contaban en cada papel. Lo que cambia es que ahora **sabés de dónde viene**.

**Sobre la tasa del 25,6%:** es la tasa de verdad, ponderada por cuánta plata pusiste y por cuántos días. No es el promedio de las 101 tasas, que sería tramposo: una caución de $20.000 por un día no puede pesar lo mismo que una de $2,7 millones por cinco. Por año te fue así: **24,5% en 2024, 29,3% en 2025 y 21,4% en 2026** — las tasas bajaron.

**Un detalle lindo:** las tasas más altas de toda tu serie, algunas arriba del 100% anual, son todas de **octubre de 2025** — el mes de las elecciones. El apretón de plata pre-electoral quedó grabado en tus propios movimientos sin que nadie lo anotara.

**Y algo que no se veía:** de tus dividendos te retuvieron **$5.190**. La retención cambia mucho según el papel: a GGAL le sacaron el **10,9%**, a TGNO4 y BMA el **7,1%**, y a los CEDEARs que pagan en dólares, **nada**.

**Para qué te sirve:**
Para saber si te conviene tener plata en caución o moverla a otra cosa: ahora tenés la tasa real para comparar contra un plazo fijo o una letra. Y para ver cuánto te comen las retenciones.

**Qué sigue:**
El último punto de esta fase: ver la cartera **por sector y por tipo de renta** (cuánto tenés en renta fija, cuánto en variable, cuánto en dólares).


---

## 30 de julio de 2026 (arreglo) — El ASML quedó limpio, y ahora podés corregir errores del broker

**Qué se hizo (en criollo):**
Tenías razón: el broker le sacó dos ceros. Las compraste a **$6.010** y el archivo decía **$60,10**. Ya está corregido en los dos lados — en la app y en tu Excel (con respaldo, por las dudas: *"Inversiones - respaldo pre-fix-ASML 2026-07-30.xlsx"*).

Con el precio real, esa venta del 21 de enero pasa de un imposible +22.754% a **+$69.803, o sea +128,5% en pesos y +80,2% en dólares, en 250 días**. Es, de verdad, **la mejor operación de tu cartera**.

**Y quedó una herramienta para la próxima.** En la pestaña Cartera hay ahora un panel para **corregir un movimiento mal informado por el broker**: buscás el ticker, elegís la operación y le arreglás el monto y el precio. Lo importante es que la app le recalcula la "huella" al movimiento, así que cuando después arregles la fila en tu Excel y vuelvas a importar, la app la reconoce en vez de cargarla dos veces. Sin eso, arreglar solo el Excel te dejaba **18 ASML donde tenés 9**.

**De paso revisé todos tus movimientos** buscando el mismo tipo de error: comparé cada precio contra lo normal de ese papel. Saltaron 12 filas y 11 son perfectamente correctas (son las compras en dólares, donde el precio está en dólares y por eso parece 1.000 veces más chico).

**Queda una para que preguntes vos:** el **TTM26** del 4 de febrero. Figura que compraste 17.395 láminas por **$17,78** — y ese mismo día compraste otras a $1,458 cada una. Si el precio bueno fuera ~$1,40, ese bono habría rendido **+9,1% en vez de +13,3%**. No lo toqué porque el +13,3% es el número que vos verificaste a mano en julio. Preguntale al broker qué es esa fila.

**Para qué te sirve:**
Que un error de carga del broker no te deforme los números sin que te enteres — y que cuando aparezca, lo puedas arreglar vos en dos clics sin romper nada.

**Qué sigue:**
El punto 3 de la fase: cauciones y dividendos como rendimiento propio.


---

## 30 de julio de 2026 (Fase 3b, paso 2) — Ya podés ver cómo salió cada venta, una por una

**Qué se hizo (en criollo):**
La línea de tiempo que armé antes ahora está enchufada a la app, y apareció una sección nueva: **Operaciones cerradas**. Es una fila por cada venta que hiciste, con lo que realmente te había costado ese papel **ese día**, a qué precio lo vendiste, cuánto ganaste o perdiste en pesos y en dólares, y **cuántos días** lo tuviste.

De tus 45 ventas, **38 fueron ganadoras**. La mejor: el **AE38, +97,7% en 578 días**. La peor: **AGRO, −31,8% en 130 días**.

**Encontré un movimiento tuyo que está mal.** El ASML de la venta del 21/1/2026 daba **+22.754%**, que obviamente no existe. Fui a la fila: tu broker anotó la compra del 16/5/2025 como **9 unidades a $60,10** — cuando las vendiste a $13.840. Ese precio de $60 no puede ser real. Lo importante es que ese dato **ya te estaba ensuciando la app de hoy**: hace que ASML figure con un costo promedio de $11.677 cuando las 15 unidades que tenés te costaron **$18.647**. **Convendría que le preguntes a inviu qué es esa fila.** Mientras tanto, la app ahora la marca como "revisar" en vez de mostrarla como si fuera el mejor trade de tu vida.

**Qué cambia en los números:**

| | Antes | Ahora |
|---|---:|---:|
| Valor de la cartera | $23.900.213 | **igual** |
| Lo que te costó lo que tenés | $21.070.343 | $20.640.875 |
| Ganancia todavía no realizada | $2.829.869 | **$3.259.338** |
| Ganancia ya realizada en ventas | $6.063.678 | $5.630.023 |
| Rendimiento sobre el costo | 13,4% | **15,8%** |

**Tu patrimonio, tu capital aportado, tu resultado total y tu tasa anual (TIR) no se mueven ni un peso.** Eso se calcula comparando lo que tenés hoy contra lo que pusiste, sin sumar operación por operación, así que nada de esto lo toca. Lo que mejora es la foto de **dónde** viene cada peso.

**Para qué te sirve:**
Para saber en qué acertaste y en qué no, y en cuánto tiempo. Un +30% en tres meses y un +30% en tres años no son lo mismo, y hasta ahora la app no te dejaba distinguirlos.

**Qué sigue:**
El punto 3 de esta fase: **cauciones y dividendos como rendimiento propio**. Tenés 101 cauciones hechas (unos $33.365 de interés) y $53.701 de dividendos cobrados, de los cuales te retuvieron $5.191 — hoy nada de eso se muestra por separado.


---

## 30 de julio de 2026 (Fase 3b) — Ahora la app va a mirar el orden en que pasaron las cosas

**Qué se hizo (en criollo):**
Arrancamos la Fase 3b y encontré algo que explica los cuatro pendientes de una sola vez: **la app hoy suma todo junto sin fijarse en qué orden ocurrió**. Junta todas tus compras de un papel, saca un promedio, y con ese promedio mide las ventas — incluso las ventas que hiciste **antes** de comprarlo de nuevo.

El caso más chico y más fácil de ver es **TGNO4**. Compraste 30 en septiembre a $3.132 y las vendiste en octubre a $3.183: ganaste $1.540. Pero en diciembre volviste a comprar, esta vez a $4.870. Esa compra de diciembre le sube el promedio a toda la historia, y la app termina diciéndote que en aquella venta de octubre **perdiste $37.700**. No es cierto: esa plata la ganaste.

Y el más grande es el **SPY**, que es el mismo problema pero al revés y por otro motivo. Acordate del ajuste de ratio: el broker te dio 70 unidades más sin cobrarte nada, y eso quedó anotado con fecha **23 de julio de 2026**. Pero vos habías vendido 35 SPY el **20 de abril**, tres meses antes. Como la app promedia todo junto, esas 70 unidades gratis de julio le abaratan el costo a una venta de abril que ya había pasado, y te informa una ganancia de **$1.122.268** cuando lo que realmente ganaste ese día fueron **$433.757** (que igual es un +31,5% en 143 días, un muy buen trade). Algo que pasó después no puede cambiar lo que ganaste antes.

Construí entonces la **línea de tiempo**: un motor que recorre tus movimientos en orden de fecha y va llevando la cuenta del costo real que tenías en cada momento. Cada venta queda registrada como una operación propia, con su fecha, su costo verdadero, su resultado y cuántos días tuviste el papel.

**Cuánto cambia:** en pesos, el resultado de tus ventas pasa de $3.297.014 a $3.145.965. Nueve papeles cambian; el resto queda igual. **Tu patrimonio, tu rendimiento total y tu tasa anual no se mueven ni un peso** — eso se calcula por otro camino que ya era correcto.

*(Estos números salieron de correr el motor sobre tu Excel, que no tiene el dólar de cada día congelado; contra la base de la app los montos exactos se van a mover un poco. Lo que no cambia es el mecanismo ni para qué lado va cada corrección.)*

**De paso, dos cosas sobre el AE38:**
Me dijiste que ya había amortizado el 9/7/2026, y fui a mirar tus movimientos: lo que cobraste ese día fue **solo el cupón** (US$89,65), a la misma tasa por lámina que venías cobrando desde enero de 2025. Si hubiera amortizado, habrías cobrado dos cosas y el cupón habría sido más chico. **La primera amortización del AE38 es el 9 de julio de 2027**, en 22 cuotas semestrales. El AN29 devuelve todo el capital junto al final, en 2029. O sea: tenés casi un año antes de que esto importe de verdad.
En cambio, tu dato de que **la amortización va por precio y nunca por cantidad de láminas** sí es la clave del diseño, y quedó escrito en el código y protegido con un test.

**Para qué te sirve:**
Vas a poder ver, operación por operación, cuánto ganaste o perdiste de verdad en cada venta y en cuántos días — en vez de un número global que mezcla todo. Y es la base sobre la que se apoyan los otros tres pendientes de esta fase.

**Qué sigue:**
Enchufar este motor a la pantalla de Cartera (hoy está construido y probado, pero todavía no cambia nada de lo que ves). Antes te muestro la tabla de los 8 papeles que cambian, para que lo confirmes.


---

## 30 de julio de 2026 (arreglo) — La tabla mostraba posiciones que no existen

**Qué pasó (en criollo):**
Me mostraste la pantalla y tenías razón: mostraba **37 posiciones cuando deberían ser 22**, con tickers raros (`SPYD`, `GOGLD`, `NVDAD`) y cantidades **negativas**. Eran **dos errores míos**, no tuyos.

**El primero.** En tu primera importación se colgó el archivo equivocado, así que los movimientos entraron **sin el mapa de instrumentos**. Sin ese mapa, la app no sabe que `SPYD` es la versión en dólares de `SPY`, y las anotó como dos cosas distintas. Lo peor: cuando volviste a importar con el Excel correcto, la app **salteó esas filas** (porque ya existían, para no duplicar) y el error quedó grabado. Ahora, al cargar el Excel, la app **repara lo que ya estaba mal**: en tus datos corrigió 65 filas.

**El segundo.** Las letras vencidas y GGALX aparecían como "abiertas" porque la app no estaba leyendo la marca de "vencido" de tu Excel. Una línea faltante.

**Cómo queda:**

| | Antes | Ahora |
|---|---|---|
| Posiciones | 37 | **22** |
| Sin precio | 9 | **0** |
| Patrimonio | US$14.794 | **US$15.742** |
| Resultado | +28,3% | **+36,5%** |
| Tasa anual | 19,2% | **24,4%** |

**Para que se aplique:** hay que hacer un deploy nuevo. Después entrás, importás los tres archivos otra vez (con `Inversiones.xlsx`, no el "Cartera - Resumen") y se repara solo.

**Lo que aprendí:** guardar un dato *calculado* (a qué activo pertenece cada movimiento) es riesgoso si la importación puede correr sin toda la información. Quedó anotado, y ahora hay una reparación automática.

---

## 30 de julio de 2026 — Arrastrás los tres archivos y listo

**Qué se hizo (en criollo):**
Me pediste no tener que cargar cuatro cosas a mano. No puedo hacerlo yo por vos —la base de datos de la app vive en el servidor, al que no llego desde acá, y tus archivos no pueden guardarse en el repositorio del proyecto— pero **sí pude convertir los cuatro pasos en uno**.

Ahora hay **un solo lugar donde arrastrás los tres archivos juntos** (tu Excel, los movimientos y la tenencia) y apretás "Importar todo". La app **reconoce cada archivo por su contenido**, no por el nombre, y los procesa **en el orden correcto**.

Ese último detalle es el que importa: el orden **tiene** que ser tu Excel primero (es el único que trae tus tenencias iniciales). Si se hace al revés, tu capital aportado aparece como US$4.941 en vez de US$11.534. Ahora eso lo decide la app, así que no te podés equivocar. Lo probé subiendo los archivos en orden salteado a propósito y salió bien.

La cantidad de Bitcoin queda **precargada** con tu número, así solo confirmás.

**Y encontré un problema que habría aparecido recién en el servidor:** el campo para cargar el mapa de instrumentos pedía una **ruta de tu computadora**. En el servidor esa carpeta no existe, así que esa función no habría funcionado online. Ya es un uploader como los demás.

**Cuando entres a la app después del deploy:** Inversiones → Cartera → arrastrás los tres archivos → "Importar todo". Eso es todo.

---

## 30 de julio de 2026 — Ya podés bajarte la cartera en Excel

**Qué se hizo (en criollo):**
Botón **"Descargar Excel"** en la pantalla de Cartera. Te baja una planilla con el mismo estilo que la tuya (los encabezados azules de siempre), pero mejorada:

- **Arriba, el resumen:** cuánto tenés, cuánto pusiste, cuánto ganaste y la tasa anual — en pesos y en dólares, con verde o rojo según corresponda.
- **La tabla agrupada por tipo** (Acciones, Bonos, Cedears, Cripto, Pagarés y Efectivo), cada grupo con su subtotal, su peso en la cartera y su rendimiento.
- **Una barrita** en la columna "% cartera" para ver de un vistazo qué pesa más. (Hoy: los pagarés 34%, los Cedears 34%, los bonos 26%.)
- **Los números formateados** como corresponde: tu planilla actual los muestra crudos porque están todos en formato "General".
- Al pie, una nota que explica cómo se calculó cada cosa.

**Dos detalles que te van a gustar:**
1. **La planilla queda viva.** Los totales y rendimientos son fórmulas de Excel, no números pegados. El **dólar MEP está en una celda amarilla**: lo cambiás y toda la planilla se recalcula sola.
2. **El total cierra con el patrimonio.** Sumé el efectivo como dos filas más (pesos y dólares en cuenta), así el TOTAL da exactamente lo mismo que el resumen de arriba — sin eso, la suma daba menos y parecía un error.

Te dejé una copia generada con tus datos de hoy en la carpeta Cartera personal para que la veas.

---

## 30 de julio de 2026 (cierre) — La cartera pasó el examen final contra tu Excel

**Qué se hizo (en criollo):**
Cerramos la última pieza: la prueba que compara **los costos en dólares** de la app contra tu planilla, usando el mismo criterio que usás vos (un solo dólar MEP para todo). Resultado: **coinciden los 49 activos comparables**.

Con eso la app quedó examinada por los dos lados: **cuántas unidades** tenés de cada cosa y **cuánto te costó cada una**. Los dos coinciden con tu Excel.

**Un detalle que me gusta de cómo quedó:** hay tres activos (AE38, GGAL y el Bitcoin) donde la app **a propósito no coincide** con tu planilla — son las tenencias iniciales que el Excel cuenta en pesos cuando en realidad son dólares. En vez de esconder esa diferencia, dejé una prueba que la vigila: si algún día corregís el Excel, esa prueba falla y avisa. Así nadie se olvida de por qué difieren.

**Con esto la etapa está terminada.** La cartera: lee los dos archivos de tu broker, entiende tu Bitcoin de Binance, valúa con precios de mercado, congela el dólar de cada operación, calcula cuánto rendiste en pesos y en dólares con su tasa anual, y se autoexamina contra tu planilla.

**Qué sigue:**
Subirla al servidor para que la uses desde el celular. Y después, las mejoras finas: resultado de cada operación cerrada, rendimiento de las cauciones, y análisis por sector.

---

## 30 de julio de 2026 — Se consolidó la semana y el pagaré ya rinde lo que rinde

**Qué se hizo (en criollo):**
Subiste los movimientos y la tenencia nuevos, y la app los consolidó sola: de los 586 movimientos del archivo, **reconoció que 580 ya los tenía y sumó solo los 6 nuevos** (tu ingreso de $300.000, las compras de NVDA y GOOGL, y una caución). Eso es exactamente lo que tenía que pasar: podés subir el archivo completo siempre, sin miedo a duplicar.

**Lo del pagaré, que era importante.** Tu pagaré es el 35% de la cartera y estaba mal medido por dos motivos:

1. **No tenía costo.** El broker registra su compra con un formato distinto al resto ("Compra cheque", sin cantidad), así que la app no lo asociaba y su rendimiento no aparecía. Arreglado: ahora sabe que invertiste US$5.032.
2. **Me equivoqué queriendo "corregir" su precio.** Pensé que el valor que informa el broker estaba inflado y armé una valuación alternativa. Vos me explicaste la mecánica: los pagarés **se compran a descuento**. Pagaste US$5.032 por algo que al vencimiento paga **US$5.500** — esos **US$468 de diferencia son la ganancia**, y a un año es justo tu 10% anual. El precio del broker es el valor de hoy, que se va acercando al nominal a medida que llega el vencimiento. Estaba bien desde el principio.

**Tu foto al 30 de julio:**

| | Pesos | Dólares |
|---|---|---|
| Aportaste | $13.462.628 | US$11.534 |
| Tenés hoy | $23.961.034 | **US$15.741** |
| **Resultado** | **+$10.498.406 (+78,0%)** | **+US$4.206 (+36,5%)** |
| **Tasa anual (TIR)** | **51,4%** | **24,4%** |

En 602 días (19,8 meses). Del pagaré ya tenés US$387 de esos US$468 ganados.

**Un detalle técnico que anoté para no olvidar:** si algún día se carga la cartera **solo** desde el archivo del broker, se pierden las tenencias iniciales (las que tenías antes de empezar a registrar, que viven en tu Excel). El orden correcto es Excel primero y los archivos del broker encima.

---

## 23 de julio de 2026 — ¿En cuánto tiempo? 19,6 meses, y la tasa anual real

**Qué se hizo (en criollo):**
Preguntaste en cuánto tiempo lograste ese rendimiento. Va con un detalle importante: como fuiste poniendo plata **en 24 momentos distintos** entre diciembre de 2024 y julio de 2026, no sirve dividir el acumulado por los años. La plata que pusiste el mes pasado no estuvo trabajando lo mismo que la de hace un año y medio.

La medida que corresponde se llama **TIR**: pondera cuánto tiempo estuvo invertido cada aporte.

**Tu foto temporal:**

- **Período:** del 5/12/2024 al 24/7/2026 → **596 días (19,6 meses, 1,63 años)**
- **Acumulado:** +39,2% en dólares · +82,2% en pesos
- **Tasa anual (TIR):** **26,0% anual en dólares** · **53,6% anual en pesos**

Para que se entienda por qué importa: si dividiéramos el acumulado por los años daría 22,4% anual, subestimando tu resultado — porque ignora que buena parte del capital entró hace poco y aun así rindió.

**Para qué te sirve:**
26% anual en dólares es un número comparable: podés medirlo contra un plazo fijo, contra el S&P 500 o contra cualquier alternativa. El "+39% acumulado" solo, no.

---

## 23 de julio de 2026 (cierre) — El Bitcoin: no era el precio, era la cantidad

**Qué pasó (en criollo):**
Me marcaste que tu Bitcoin vale US$203,04 y la app mostraba US$192. Yo sospechaba del precio… y era la **cantidad**: tu Excel tenía 0,003 BTC (el saldo inicial de cuando arrancaste), pero en realidad tenés **0,00316847**. Un 5% más. Con la cantidad real: **US$202,91**, o sea 13 centavos de tu número — pura variación del precio en el rato que pasó.

Ahora la app tiene un lugar para **activos que están fuera del broker** (tu BTC en Binance): cargás la cantidad una vez y el precio lo busca sola. Y no se borra cuando subís una tenencia nueva.

También ajusté algo importante: cuando subís la tenencia, la app usa **los precios de tu broker** en vez de los del mercado en vivo. Así los totales coinciden con lo que ves en tu cuenta, en lugar de diferir por unos pesos según el momento.

**Y resolví el misterio de los US$86** que no cerraban: el archivo de tenencias del broker tiene, adentro, una fórmula mal armada — calcula los montos con una columna que viene vacía. O sea que el "Total" del archivo daría cero. Tus 15.489 salen de la **pantalla** del broker (precios de ese instante), y yo sumo los precios que quedaron congelados en el archivo. Son dos fotos de momentos distintos: 0,55% de diferencia.

**Tu foto final:**

| | Pesos | Dólares |
|---|---|---|
| Aportaste | $13.162.628 | US$11.338 |
| Tenés hoy | — | **US$15.778** |
| **Resultado** | **+$10.815.664 (+82,2%)** | **+US$4.440 (+39,2%)** |

**Qué anoté para más adelante:** traer tu tenencia de Binance automáticamente (solo lectura — la app nunca opera por vos), así no tenés que cargar la cantidad a mano.

---

## 23 de julio de 2026 (corrección 2) — Faltaba el 35% de tu cartera: el pagaré

**Qué pasó (en criollo):**
Me dijiste "en dólares hay 15.489, como dice en las tenencias" y tenías razón: yo mostraba US$10.047. **Faltaba tu pagaré** (`#UMV060770008`): 5.500 unidades que valen **US$5.359** — más de un tercio de tu cartera.

¿Por qué faltaba? Porque el archivo de **movimientos** del broker registra la compra del pagaré con el monto que pagaste, pero **sin decir cuántas unidades compraste**. Sin ese dato es imposible saber cuánto tenés. Lo mismo pasó con el ajuste de SPY: el broker cambió la relación del CEDEAR sin generar ningún movimiento.

**La conclusión importante:** el archivo de movimientos **solo no alcanza** para armar tu cartera. Ahora la app usa **dos archivos**: el de movimientos (que aporta la historia: qué pagaste, cuánto depositaste, cuánto rendiste) y el de **tenencias** (que aporta la foto de hoy: qué tenés exactamente). Y compara ambos: esa comparación es el control de que nada se escape.

También marcaste bien lo del **Bitcoin**: como está fuera del broker, no aparece en el archivo de tenencias. La app lo contempla — si algo no está en la tenencia pero sí en tus movimientos, lo conserva.

**Los números, ahora completos:**

| | Pesos | Dólares |
|---|---|---|
| Pusiste | $13.162.628 | US$11.338 |
| Tenés hoy | $23.946.439 | US$15.757 |
| **Resultado** | **+$10.783.811 (+81,9%)** | **+US$4.419 (+39,0%)** |

(Incluye el Bitcoin, US$192, que el broker no ve.)

**De regalo, la comparación encontró un error en tu Excel:** tenés **ASML** marcado como "Activo en cartera = NO", pero el broker dice que tenés 15. Conviene corregirlo en la planilla.

---

## 23 de julio de 2026 (corrección) — Me equivoqué en el rendimiento, vos lo cazaste

**Qué pasó (en criollo):**
Te di un número mal. Dije que habías invertido US$25.219 y ganado 16,9% en dólares. Vos dijiste "no hay 25 mil, hay unos 10/11 mil, revisá los ingresos de dinero". Tenías razón, y al revisar aparecieron **tres errores**:

1. **Estaba sumando la misma plata muchas veces.** Contaba "invertido" como la suma de todas tus compras. Pero si comprás algo, lo vendés y con esa misma plata comprás otra cosa, eso son dos compras… con el mismo dinero. Lo que realmente pusiste es lo que **depositaste**: **US$11.338** (justo lo que dijiste).
2. **Tus tenencias iniciales estaban contadas en pesos y son dólares.** El AE38, el Bitcoin y las GGAL con las que arrancaste figuran a "$4,49" y similares — eso son dólares, no pesos. Al tomarlos como pesos, tu capital inicial valía casi nada en el cálculo.
3. **El más grave:** estaba sumando el resultado de cada instrumento para sacar el total. Eso no funciona en una cartera con pesos y dólares: al pasar los dólares a pesos con el cambio de cada fecha, la devaluación aparece como "ganancia" cuando no lo es. Lo verifiqué **en pesos**, donde el dólar no influye: mi suma daba $9,9 millones y el cálculo correcto da $2,3 millones. Estaba inflado cuatro veces.

**Cómo lo arreglé:**
Ahora se mide como se debe: **lo que hoy vale todo** (inversiones + efectivo) **menos lo que pusiste**. Simple y a prueba de errores, porque no depende de sumar operación por operación. Además verifiqué el efectivo calculado contra lo que dice tu broker y coincide.

**Los números correctos:**

| | Pesos | Dólares |
|---|---|---|
| Pusiste | $13.162.628 | US$11.338 |
| Tenés hoy | $15.544.931 | US$10.137 |
| **Resultado** | **+$2.382.303 (+18,1%)** | **−US$1.201 (−10,6%)** |

O sea: **en pesos subiste 18%, pero medido en dólares estás 10,6% abajo**. Es la foto honesta, y es exactamente la razón por la que pediste ver el MEP de cada fecha.

**Qué aprendí (y quedó anotado):**
Antes de mostrarte cualquier total, hay que contrastarlo contra una cuenta independiente. Sumar operación por operación *parecía* razonable y daba un número muy equivocado. Gracias por no comerte el número.

---

## 23 de julio de 2026 (cierre del día) — Cuánto ganaste de verdad, en pesos y en dólares

**Qué se hizo (en criollo):**
Vos marcaste algo que faltaba: **las amortizaciones de las letras son ganancia** y no se estaban contando. Tenías razón — había **$6.345.528** cobrados (vencimientos de letras, rentas de bonos y dividendos) que la app ignoraba. Ahora se cuentan, y las letras vencidas dejaron de figurar como si todavía las tuvieras (uso la marca "Activo en cartera = NO" de tu propio Excel para saber cuáles vencieron).

Y como pediste, el rendimiento ahora se calcula **también en dólares**, convirtiendo cada compra y cada cobro al MEP **del día en que ocurrió**. Ahí aparece lo interesante:

- **En pesos: +$10.398.493 (+31,3%)**
- **En dólares: +US$4.273 (+16,9%)**

Sobre $33,2 millones invertidos (US$25.219) desde que arrancaste.

El caso que mejor muestra por qué importa: la letra **S15G5 ganó 3,8% en pesos… pero perdió 3,6% en dólares**. Sin mirar el dólar de cada fecha, eso no se ve.

**Un error que encontré y corregí:** al principio las letras mostraban 100% y 113% de rendimiento. El motivo: cuando una letra vence te devuelve **el capital más el interés**, y yo estaba contando todo como ganancia. Corregido: ahora se descuenta el capital que pusiste. Verifiqué cada letra contra un cálculo hecho aparte y dan idénticas.

**Para qué te sirve:**
Es la diferencia entre creer que ganaste 31% y saber que, medido en dólares, ganaste 17%. En Argentina esa distinción es todo.

**Qué sigue:**
La verificación final contra el Excel y subirla al servidor.

---

## 23 de julio de 2026 (final) — Tu cartera ya se ve en la app

**Qué se hizo (en criollo):**
- Construimos la **pantalla de Cartera**. Entrás a Inversiones → Cartera, **subís el archivo del broker** y ves: cuánto vale tu cartera en pesos y en dólares, cuánto ganaste o perdiste, y la tabla de posiciones con cantidad, precio promedio de compra, precio de hoy y rendimiento de cada una.
- Podés volver a subir el mismo archivo cuantas veces quieras: los movimientos repetidos se ignoran solos.
- **Probado con tus datos reales de punta a punta:** valor **$15.490.098** (unos **US$10.101**), **+19,8%** sobre lo invertido, 23 posiciones valuadas con precios en vivo. Tu Bitcoin también entra (se cotiza aparte, porque no cotiza en el mercado local).
- Detalle que vale la pena que sepas: hay **6 letras y bonos en pesos que ya vencieron** y quedan figurando con cantidad, porque el sistema registra el vencimiento como "amortización" y no como venta. Tu Excel arrastra exactamente lo mismo. No afectan los totales (no tienen precio), y lo vamos a limpiar en la próxima etapa.

**Para qué te sirve:**
Es el objetivo de todo esto: dejar de abrir la planilla para saber cómo viene tu cartera.

**Qué sigue:**
Una última verificación de los dólares contra el Excel, y después subirla al servidor para que la puedas usar desde cualquier lado.

---

## 23 de julio de 2026 (cierre) — La app ya sabe buscar precios y el dólar de cada fecha

**Qué se hizo (en criollo):**
- Conectamos la app al mercado: ya trae sola los **precios** de tus acciones, CEDEARs y bonos, y el de Bitcoin. Con tres redes de seguridad: guarda una copia de lo último que vio (si la fuente se cae, sigue funcionando), y podés **corregir cualquier precio a mano** — tu valor siempre gana.
- Y lo más importante: le pusimos a **cada una de tus 585 operaciones el dólar MEP del día en que la hiciste**. Quedó grabado a fuego: aunque mañana cambie la fuente de datos, tus operaciones viejas no se tocan. Probado de punta a punta con tus datos reales: las 585, sin una sola fecha sin cotización.
- **Apareció un problema y lo resolvimos con vos:** habíamos anotado que el dólar MEP histórico lo daba el Banco Central... y resulta que **el Banco Central no publica el MEP** (publica el mayorista, que va un 3% abajo y te subvaluaría las compras). Te lo planteé, elegiste otra fuente, y quedó documentado.

**Para qué te sirve:**
Es la diferencia entre "tengo 45 CEDEARs de Google" y "valen tanto, y me rindieron tanto". Además, valuar con el dólar de cada fecha es más fiel que lo que hace hoy tu Excel (que usa el dólar de hoy para todo, incluso para compras de 2024).

**Qué sigue:**
La pantalla de Cartera: ver todo esto en la app, con el botón para subir el archivo del broker.

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
