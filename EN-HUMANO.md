# En humano 🧑‍💻→🙂

Este archivo cuenta, **en lenguaje llano y sin tecnicismos**, qué se fue haciendo en el proyecto y para qué sirve. Es para Franco (y para cualquiera que no quiera leer código ni bitácoras técnicas). Si algo acá suena a jerga, está mal escrito.

**Reglas de este archivo:**
- Lo actualiza el Claude que trabaja, **cada vez que completa un avance importante** (y como mínimo una vez por sesión).
- Cada entrada responde tres cosas: **qué se hizo**, **para qué te sirve a vos**, y **qué sigue**.
- Nada de nombres de archivos raros ni términos técnicos sin traducir. Si hay que nombrar algo técnico, se explica al lado con una analogía.

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
