# Cronogramas de renta fija — investigación de fuentes

> **Estado:** 🟢 fuente encontrada y viable. **Falta la decisión de Franco** (crear cuenta) antes de escribir código.
> **Fecha:** 5/8/2026.

## Por qué hace falta

La **TIR esperada** y la **duration** de la renta fija necesitan el cronograma
completo de cada bono: cada cupón y cada amortización, con su fecha y su monto.
Sin eso no hay cálculo posible — no es cuestión de programarlo mejor.

Y hay un motivo más concreto, que apareció al armar el panel de vencimientos:
**para un bono amortizable, "cuándo vence" es un dato pobre.** El AE38 no vence
hasta 2038 pero **empieza a devolver capital el 9/7/2027**. Lo que sirve saber
no es cuándo termina sino **cuándo cobrás y cuánto**. Eso es el cronograma.

**Lo que hay hoy:** nada. Ni la app ni el Excel lo tienen — la hoja *Flujo de
Fondos* tiene 3 instrumentos y **un solo flujo** cargado.

---

## Fuentes descartadas

| Fuente | Por qué no |
|---|---|
| **`data912`** (ya integrada) | Verificado contra su OpenAPI: solo **precios en vivo** (`/live/*`) e **histórico OHLC** (`/historical/*`). **No tiene ningún endpoint de flujos.** |
| **`argentinadatos`** (ya integrada) | Cotizaciones e índices macro. No modela instrumentos. |
| **Cbonds** | Cubre 600.000+ bonos globales, pero es un servicio comercial caro pensado para instituciones. Desproporcionado. |
| **IAMC / BYMA / Bolsar** | Publican los cronogramas, pero en **PDF y planillas**. Scraping frágil, se rompe cuando cambian el formato, y hay que mantenerlo. Último recurso. |

---

## 🟢 Fuente encontrada: Docta Capital

`https://api.doctacapital.com.ar` · [docs](https://docs.docta.com.ar/) · [onboarding para IA](https://docs.docta.com.ar/onboarding-ia.md)

**Cubre exactamente el hueco:** bonos argentinos **soberanos, sub-soberanos y
ONs**. Que incluya ONs importa: cubre el `RUCDO` (ON MSU Energy).

### Los endpoints que sirven

| Endpoint | Qué da |
|---|---|
| `GET /api/v1/bonds/analytics/{symbol}/cashflow` | **El cronograma**: `payment_date`, `capital`, `interest_amount`, `residual_value`, `cash_flow`, ajustado por CER/UVA |
| `GET /api/v1/bonds/analytics/{symbol}/calculadora` | TIR, TNA, TEM, valor técnico, valor residual, precio dirty, intereses corridos |
| `GET /api/v1/bonds/compare` | Hasta 20 bonos: TIR, TNA, TEM, **duration**, DTM |
| `GET /api/v1/bonds/instruments/search` | Resolver el ticker exacto antes de consultar |

O sea que **no solo desbloquea la TIR esperada y la duration: las trae
calculadas.** Igual conviene calcularlas también nosotros con el cronograma y
contrastar — es la disciplina de la identidad contable independiente aplicada a
un proveedor externo.

### Autenticación y costo

OAuth 2.0 *client credentials*. **Un humano tiene que crear la cuenta**
([app.docta.com.ar](https://app.docta.com.ar/auth)), generar `client_id` y
`client_secret`, y esos van a `.env` — **nunca al repo**.

| Plan | RPM | Límite diario |
|---|---|---|
| **Basic (gratuito)** | 10 | **15 requests por día** |
| Intermedio | 60 | 100 por día |
| Pro | 120 | ilimitado |

### ⚠️ El punto que decide la viabilidad

**15 requests por día suena a nada — y alcanza de sobra.** El motivo: **un
cronograma es dato estático.** El AE38 va a pagar lo mismo en las mismas fechas
el mes que viene que hoy. Se baja **una vez por bono** y se guarda en la DB.

Franco tiene **2 o 3 instrumentos de renta fija vivos**. Son 3 requests, una
vez. Después, refresco mensual por las si acaso.

Lo único que sí conviene consultar seguido es la TIR intradiaria, y **eso no lo
necesitamos**: con el cronograma cacheado y el precio que ya trae `data912`, la
TIR la calculamos nosotros con la bisección que ya existe en `posiciones.py`.

**Conclusión: el plan gratuito alcanza, y el diseño con caché no es una
optimización sino el uso correcto de la fuente.**

### Lo que NO cubre

* Acciones, CEDEARs, futuros y opciones — **no importa**, eso ya lo da `data912`.
* En bonos **no da precios ni OHLC** — tampoco importa, ya lo tenemos.
* ⚠️ **El pagaré `#UMV060770008` casi seguro no está.** Es un instrumento del
  **MAV**, y el catálogo declara soberanos, sub-soberanos y ONs. **Hay que
  verificarlo con credenciales antes de dar por cerrada la integración.**

---

## Riesgos y cómo se mitigan

| Riesgo | Mitigación |
|---|---|
| Es un servicio comercial: puede cambiar términos o desaparecer | **Caché en DB** (el cronograma queda guardado aunque la fuente se caiga) + **carga manual** como fallback. Misma disciplina que se aplicó a `data912` en la Fase 3a. |
| Credenciales | `.env`, nunca el repo. El pre-commit hook ya bloquea `.env`. |
| El pagaré queda afuera | La carga manual lo resuelve, y **hay que construirla igual** por el punto anterior. |
| Depender de la TIR que calcula el proveedor | Calcularla también nosotros con el cronograma y **contrastar**. Si difieren, hay algo que no entendemos del instrumento. |

---

## 💡 Aparte: tienen servidor MCP

`https://mcp.docta.com.ar/mcp` con OAuth, 26 herramientas (una por endpoint).
**Franco puede conectarlo a Cowork** y preguntar por bonos en el chat, sin
esperar a la integración en la app. Es independiente de todo lo de acá arriba y
sirve para explorar la fuente antes de comprometerse.

---

## Recomendación

1. **Franco crea la cuenta gratuita** y genera las credenciales.
2. **Primer paso, barato:** verificar cobertura de sus instrumentos reales
   (`AE38`, `AN29`, `RUCDO`, y probar el pagaré). Son 4 requests de los 15
   diarios. Si el pagaré no está, se sabe antes de escribir nada.
3. Recién ahí, `core/market_data/cronogramas.py` con **caché agresiva en DB**
   (M15), `fetch` inyectable para tests sin red, y carga manual como fallback —
   el mismo patrón de `sectores.py`, que ya está probado.
4. Con el cronograma en la base salen, sin más requests: **calendario de cobros
   futuros**, **TIR esperada** y **duration**.

**Alternativa si Docta no sirve:** cargar a mano los 2-3 bonos. Es ~1 hora, no
depende de nadie, y el mecanismo hay que construirlo igual como fallback. No es
un mal plan B.
