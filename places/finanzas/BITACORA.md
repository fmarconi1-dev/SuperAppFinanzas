# places/finanzas/

<!-- huella: 815a1a53f088 -->

Resumen: Lugar A — Finanzas Personales (ex Mis-Finanzas-App / Radar Financiero): home con onboarding y las 5 pestañas. La lógica vive en `core/` local, las pantallas en `views/`.

## Buscar acá si

- el onboarding aparece cuando no debería (se evalúa SIEMPRE contra el espacio personal)
- el orden de las pestañas o una pestaña entera caída → `home.py`
- el badge grande del modo familiar

## Qué hay acá

- `home.py` — puerta del lugar: onboarding si faltan categorías, si no las 5 pestañas.
- `core/`, `views/`, `helpers/` — cada una con su propia BITACORA.md.

## Trampas

- El flag de onboarding vive en el workspace **personal** del usuario; en un familiar no hay flag y dispararía onboarding.

## Estado

- **Funciona:** en producción desde Fase 1; Fase 4 (pulido) en curso.

## Proximo paso

Ver "Próximo paso concreto" en `/ESTADO.md`. La crónica del lugar está en `bitacora_de_trabajo.md`.
