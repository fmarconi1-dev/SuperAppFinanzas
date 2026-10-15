# Decisiones de arquitectura (ADR)

Registro liviano de decisiones importantes. Una decisión = un archivo `ADR-NNNN-titulo.md`.
Formato: Contexto · Decisión · Alternativas · Consecuencias · Estado.

> **Numeración de fases.** Las ADR se escriben en su fecha y no se reescriben. Cuando la ADR-0003 o la ADR-0004 dicen "Fase 5" para el stack de datos de mercado, hoy eso es la **Fase 6** (Mercado en vivo): el 27/8/2026 la ADR-0006 insertó una Fase 5 nueva. La numeración vigente está en `ROADMAP.md`.

- `ADR-0001-monorepo-y-lugares.md` — Monorepo con núcleo compartido + lugares. ✅ Aceptada.
- `ADR-0002-scoring-snapshot-remoto.md` — El scoring se calcula en batch y la app lee el snapshot. ⛔ **Retirada (5/8/2026)**: el scoring se sacó de la app; el código quedó en `Borrar/`.
- `ADR-0003-cartera-nativa.md` — Cartera con DB propia; el Excel pasa a oráculo de reconciliación. ✅ Aceptada.
- `ADR-0004-fuente-mep-historico.md` — MEP histórico desde `argentinadatos` (el BCRA no publica MEP). ✅ Aceptada.
- `ADR-0005-realizado-ppc-movil.md` — El resultado realizado se mide con el PPC vigente al vender. ✅ Aceptada.
- `ADR-0006-captura-source-first.md` — Finanzas Personales pasa de transaction-first a source-first: cuentas y perímetro, tres fuentes que proponen, y el agente que dedupea. ✅ Aceptada.
- `ADR-0007-retiro-de-inversiones.md` — Se retira el lugar Inversiones entero (Cartera + Mercado en vivo); el código sale, las tablas `cartera_*` quedan quietas en la base. ✅ Aceptada (14/10/2026). **Deja como históricas las ADR-0003, 0004 y 0005.**
- `ADR-0008-enfoque-secretario.md` — La app pasa a ser un secretario personal: WhatsApp (Meta Cloud API, costo cero) + Google Calendar/Tasks vía Apps Script + dashboard nuevo, en fases A–D. ✅ Aceptada (14/10/2026). **Pone en pausa la Fase 5 (ADR-0006).**
