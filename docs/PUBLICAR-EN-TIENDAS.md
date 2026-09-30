# Publicar en App Store y Play Store — requisitos

> **Estado: referencia, no plan.** Hoy la Superapp es web (Streamlit en Fly.io) y de uso personal; publicarla en las tiendas exigiría una app nativa y abrirla a otros usuarios, que es la **Fase 8 (opcional)** del `ROADMAP.md`. Esto queda anotado para ese día.
>
> **Fuente:** hilo de Gon Nahmias (@gonahmias), 28/9/2026, sobre publicar **Kesef** (app de gastos personales, ~10–12 mil usuarios) — [x.com/gonahmias/status/2104682110141530513](https://x.com/gonahmias/status/2104682110141530513). Anotado el 29/9/2026.
>
> ⚠️ **Los requisitos de las tiendas cambian.** Antes de arrancar, verificar cada punto contra la documentación oficial de Apple y Google del momento; esto es un mapa de qué preguntar, no la respuesta.

---

## 1. Lo que habría que resolver antes (propio de esta app)

La lista del hilo asume una app nativa. Para la Superapp, antes de todo eso:

- **Una app nativa.** Streamlit no se publica en las tiendas. El autor usó **Expo + EAS** (React Native), que además resuelve compilar para iOS sin una Mac. Implica reescribir el frente; la lógica en Python (`core/`, `places/*/core`) quedaría detrás de una API — el viejo **M5 (API sidecar)**, que la Fase 5 ya pone como vía de captura del efectivo.
- **Multiusuario de verdad (Fase 8):** aislamiento de datos, alta de cuentas abierta (hoy es con código de invitación, `SIGNUP_CODE`), costos de infraestructura por usuario.
- **La Cartera:** depende de exports de un broker concreto (inviu) y del Excel de Franco; no generaliza sin trabajo.

## 2. Costos

| | Apple | Google |
|---|---|---|
| Cuenta de desarrollador | **USD 99 por año** — si no se renueva, **bajan la app** | **USD 25, una sola vez** |
| Pago | tarjeta en dólares | tarjeta en dólares |

## 3. ¿Cuenta personal o de empresa?

- **Personal:** más rápida de aprobar, pero **tu nombre queda visible** en la tienda.
- **Empresa:** requiere **número D-U-N-S**, **sitio web propio** y una verificación lenta.

## 4. Requisitos técnicos

**iOS**
- "En teoría necesitás una Mac": con **Expo EAS** se compila en la nube.
- Probar en un **iPhone real**: el simulador no reproduce todo.

**Android**
- ⚠️ **Cuentas personales nuevas:** antes de publicar, **testeo cerrado con 12 o más personas durante 14 días consecutivos**. Es el cuello de botella más largo: conseguir los testers antes de necesitarlos.

## 5. Imágenes

| | App Store | Google Play |
|---|---|---|
| Ícono | 1024×1024, **sin transparencias** | 512×512 |
| Capturas de teléfono | 1320×2868 (iPhone), 1 a 10 | mínimo 2, idealmente 1080×1920 |
| Otras | iPad 2064×2752 (si se soporta tablet) | imagen destacada 1024×500 |

## 6. Requisitos funcionales que rebotan una revisión

- [ ] **Borrar la cuenta desde la propia app** (no alcanza con "mandá un mail").
- [ ] **Política de privacidad** publicada en una web pública.
- [ ] Si hay **login con Google en iOS**, también **login con Apple**.
- [ ] Formularios de **encriptación** y de **clasificación por edad**.
- [ ] Declaración de **datos recolectados** (en una app financiera, completa y honesta: montos, categorías, cuentas).

## 7. Revisión

- **Apple:** 1–2 días, revisión manual.
- **Google:** hasta **7 días** la primera versión; las actualizaciones, ~1 hora.

## 8. Cobrar

- Solo con el **sistema de pagos de cada tienda**: comisión del **30%** por defecto, **15%** para negocios chicos (programas de cada tienda).
- Hay que declarar **datos bancarios y fiscales** antes de poder cobrar.
- Referencia de precio: Kesef cobra **USD 35/año** su plan Pro (Mercado Pago automático, carga por voz ilimitada, sin anuncios, export a Excel), con 14 días de prueba.

## 9. Mantenimiento

- Publicar **al menos una actualización por año** para no perder visibilidad.
- Apple: renovar los USD 99 **cada año**.
