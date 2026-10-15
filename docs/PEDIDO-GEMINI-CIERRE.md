# Pedido para Gemini — cierre de mercado de las 18:30

> **Guía opcional.** Gemini ya genera el cierre (mail `[Briefing-WhatsApp] Cierre de Mercado - DD/MM/AAAA`). Esto sirve solo si querés ajustar el formato o las reglas del que ya tenés.

Va en el **Apps Script de Gemini**, el mismo que hoy arma el briefing de la mañana. Se usa igual: un disparador a las **18:30, de lunes a viernes**, que le pasa este pedido a Gemini y manda el resultado por mail.

- **Asunto del mail:** `[Briefing-WhatsApp] Cierre de Mercado - DD/MM/AAAA`, como ya lo manda. Nuestro Apps Script busca `[Briefing-WhatsApp]` y reconoce el cierre por "Cierre de Mercado": **no cambies esas dos partes del asunto**.
- **Cuerpo:** **texto plano**, sin HTML. Los asteriscos `*así*` son negritas de WhatsApp.
- **Largo:** menos de 3.000 caracteres. WhatsApp corta en 4.096 y la SuperApp lo partiría en dos mensajes.

## El pedido (copiar desde acá)

```
Sos mi asistente de mercados. Armá un resumen MUY corto del cierre de hoy ({{FECHA}}), en español rioplatense, para leer en WhatsApp.

REGLAS
- Solo datos de cierre de HOY y su variación contra el cierre anterior. Si un dato no es de hoy, poné su fecha entre paréntesis.
- Si no encontrás un dato confiable, escribí "s/d". NUNCA inventes ni estimes una cifra.
- Por bloque: una línea de datos y UN párrafo de una o dos frases que describa solo lo que muestran esos números. Nada de pronósticos, recomendaciones ni "conviene".
- Variaciones de índices y precios en %, con signo y coma decimal (+0,4%). Tasas en %, con su variación en puntos básicos (−15 pb).
- Si hoy un mercado no operó (feriado), poné "Sin operaciones hoy" en sus bloques.
- Texto plano. Negritas solo con *asteriscos*. Sin links. Menos de 3.000 caracteres.

FORMATO EXACTO

*📈 CIERRE {{DD/MM}}*

*🇺🇸 Acciones*
S&P 500 <nivel> (<var%>) · Nasdaq <nivel> (<var%>) · Dow <nivel> (<var%>)
<párrafo>

*🇺🇸 Treasuries*
2 años <tasa%> (<pb>) · 10 años <tasa%> (<pb>) · 30 años <tasa%> (<pb>)
<párrafo; si cambió la pendiente 2–10, decilo: "la curva se empinó/aplanó">

*🇦🇷 Acciones*
Merval <nivel> (<var%>)
<párrafo>

*🇦🇷 Bonos hard dollar*
AL30 <precio USD> (<var%>) · GD30 <…> · GD35 <…> · GD38 <…> · GD41 <…> · AE38 <…>
Riesgo país <pb> (<variación en pb>)
<párrafo>

*🇦🇷 Curva en pesos*
Tasa fija: <3 o 4 LECAP/BONCAP de distintos plazos con su TEM %>
CER: <2 o 3 bonos CER, solo variación de precio %>
<párrafo: si la tasa fija subió o bajó y en qué tramo>
```

`{{FECHA}}` y `{{DD/MM}}` los reemplaza el script con la fecha del día, igual que en el pedido del briefing.

## Notas

- **Exactitud:** los números los busca Gemini; la SuperApp no los puede verificar. Si un día alguno no cierra, se ajusta este pedido. Si tu script de Gemini puede traer los datos de una API antes de llamar a Gemini (con `UrlFetchApp`) y pasarle solo los números para que redacte, es más confiable que dejar que los busque. Fuentes gratis, sin clave, probadas el 15/10/2026:
  - Yahoo (`https://query1.finance.yahoo.com/v8/finance/chart/<símbolo>?range=5d&interval=1d`, con un User-Agent de navegador): `^GSPC`, `^IXIC`, `^DJI`, `^MERV`, y tasas `^IRX` (13 semanas), `^FVX` (5 años), `^TNX` (10 años), `^TYX` (30 años). No tiene los 2 años. La variación se calcula contra el cierre anterior de la serie; el `chartPreviousClose` de 5 días no es el de ayer.
  - data912 (`https://data912.com/live/arg_bonds` y `/live/arg_notes`): bonos hard dollar en especie D (`AL30D`, `GD30D`…) con `c` (precio) y `pct_change`; las LECAP (`S…`) y BONCAP (`T…`) cotizan cada 100 nominales.
  - argentinadatos (`https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo`): riesgo país, con su fecha.
- **18:30 y no 18:00:** desde el 1/11/2026 Wall Street cierra a las 18:00 hora argentina (fin del horario de verano en EE.UU.).
- **Días sin rueda:** el disparador corre de lunes a viernes. Si un mercado no operó por feriado, el pedido ya le dice a Gemini qué poner.
