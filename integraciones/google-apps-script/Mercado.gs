/**
 * Números de mercado armados por código, no por Gemini (ADR-0010, 19/10/2026).
 *
 * Gemini, en su conversación recurrente, buscaba las cotizaciones en la web y
 * presentaba cierres de días anteriores como si fueran de hoy (el 19/10 el
 * matutino trajo el cierre del jueves y el cierre, el del viernes). Desde acá:
 *   - el matutino lo sigue escribiendo Gemini, pero su bloque "📊 TABLERO" se
 *     reemplaza por `tableroMatutino_` antes de mandarlo (ver `Reenvio.gs`);
 *   - el cierre de las 18:30 lo arma entero `textoCierre_` y sale por el mismo
 *     disparador de cada 10 minutos (`cierrePendiente_`).
 *
 * Reglas: cada dato lleva su fecha si no es de hoy, y una fuente que no
 * contesta se ve como "s/d" (y queda en el registro), nunca como un número
 * viejo. Las frases describen solo lo que muestran los números.
 *
 * Fuentes (gratis, sin clave; probadas el 19/10/2026):
 *   Yahoo                S&P, Nasdaq, Dow, Brent, oro (y 10/30 años de respaldo)
 *   Tesoro de EE.UU.     tasas a 2, 10 y 30 años (curva oficial del día)
 *   BYMA                 MSCI MERVAL (arrancó el 19/10/2026 en base 100.000)
 *   dolarapi             dólares del día
 *   argentinadatos       dólares del día hábil anterior y riesgo país
 *   data912              bonos hard dollar y curva en pesos
 *
 * Va en el mismo proyecto que `Reenvio.gs` (usa `mandarASuperApp_`).
 */

const ZONA_AR = "America/Argentina/Buenos_Aires";

// El cierre sale en la primera corrida del disparador desde esta hora
// (lunes a viernes). Desde el 1/11 Wall Street cierra a las 18:00 hora
// argentina; 18:30 sirve todo el año y el BYMA ya cerró (17:00).
const HORA_CIERRE = "18:30";

const URL_YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/";
const URL_TESORO = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{anio}/all?type=daily_treasury_yield_curve&field_tdr_date_value={anio}&page&_format=csv";
const URL_BYMA_INDICES = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/index-price";
const URL_DOLARAPI = "https://dolarapi.com/v1/dolares";
const URL_DOLAR_HISTORICO = "https://api.argentinadatos.com/v1/cotizaciones/dolares/";
const URL_RIESGO_PAIS = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais";
const URL_DATA912 = "https://data912.com/live/";

// Sin User-Agent de navegador, Yahoo responde 429.
const UA_NAVEGADOR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

const SIMBOLOS_YAHOO = {
  sp: "^GSPC", nasdaq: "^IXIC", dow: "^DJI", brent: "BZ=F", oro: "GC=F",
  y10: "^TNX", y30: "^TYX"
};

// [clave, nombre en el texto, casa en dolarapi/argentinadatos]
const DOLARES = [
  ["mayorista", "Dólar Mayorista", "mayorista"],
  ["bna", "Dólar Minorista (BNA)", "oficial"],
  ["blue", "Dólar Blue", "blue"],
  ["mep", "Dólar MEP", "bolsa"],
  ["ccl", "Dólar CCL", "contadoconliqui"]
];

const BONOS_HD = ["AL30", "GD30", "AL35", "GD35", "GD38", "GD41", "AE38"];
const RE_LECAP = /^S\d{2}[A-Z]\d$/;
const RE_BONCAP = /^T\d{2}[A-Z]\d$/;
const RE_CER = /^(TZX[A-Z0-9]{2,3}|TX\d{2})$/;


// ---------------------------------------------------------------------------
// 1. Lo que usan Reenvio.gs y el disparador
// ---------------------------------------------------------------------------

/** Bloque "📊 TABLERO" del matutino, con los números de las fuentes. */
function tableroMatutino_() {
  const hoy = hoyAR_();
  return armarTableroMatutino_(traerDatosDeMercado_(hoy), hoy);
}

/**
 * Si ya son las 18:30 de un día hábil y el cierre de hoy todavía no salió,
 * lo arma y lo manda. Lo llama `reenviarBriefingAWhatsApp` (cada 10 minutos,
 * bajo su lock): si la SuperApp no lo toma, la próxima corrida reintenta.
 */
function cierrePendiente_(url, token) {
  const hoy = hoyAR_();
  const diaSemana = diaDeSemana_(hoy); // 0 = domingo … 6 = sábado
  if (diaSemana === 0 || diaSemana === 6) return;
  if (Utilities.formatDate(new Date(), ZONA_AR, "HH:mm") < HORA_CIERRE) return;

  const props = PropertiesService.getScriptProperties();
  if (props.getProperty("ULTIMO_CIERRE") === hoy) return;

  const texto = armarTextoCierre_(traerDatosDeMercado_(hoy, true), hoy);
  // `id` fijo por día: si la respuesta se pierde y se reintenta, la SuperApp
  // reconoce el mismo cierre y no lo manda dos veces.
  if (mandarASuperApp_(url, token, texto, "cierre", "cierre-" + hoy, "[cierre] " + hoy)) {
    props.setProperty("ULTIMO_CIERRE", hoy);
  }
}

/**
 * Manual, desde el editor: arma el cierre de ahora y lo manda aunque hoy ya
 * haya salido (o sea fin de semana). Va con un `id` nuevo porque la SuperApp
 * descarta en silencio un `id` repetido: borrar ULTIMO_CIERRE no alcanza.
 */
function reenviarCierreAhora() {
  const props = PropertiesService.getScriptProperties();
  const url = requerirPropiedad_(props, "SUPERAPP_URL").replace(/\/+$/, "") + "/api/briefing";
  const token = requerirPropiedad_(props, "SUPERAPP_TOKEN");
  const hoy = hoyAR_();
  const texto = armarTextoCierre_(traerDatosDeMercado_(hoy, true), hoy);
  mandarASuperApp_(url, token, texto, "cierre", "cierre-" + hoy + "-manual-" + new Date().getTime(), "[cierre manual] " + hoy);
}

/** Prueba manual desde el editor: muestra el tablero y el cierre, no manda nada. */
function probarMercado() {
  const hoy = hoyAR_();
  const datos = traerDatosDeMercado_(hoy, false);
  console.log(armarTableroMatutino_(datos, hoy));
  console.log(armarTextoCierre_(traerDatosDeMercado_(hoy, true), hoy));
  if (datos.errores.length) console.warn("Fuentes con problemas:\n" + datos.errores.join("\n"));
  else console.log("Todas las fuentes contestaron.");
}


// ---------------------------------------------------------------------------
// 2. Traer y leer las fuentes
// ---------------------------------------------------------------------------

/**
 * Trae todo en dos tandas en paralelo (la segunda, los dólares del día hábil
 * anterior, necesita la fecha de los de hoy). Nunca tira: cada fuente que
 * falla queda en `errores` y su dato en null, que el texto muestra "s/d".
 */
function traerDatosDeMercado_(hoy, paraCierre) {
  const d = { errores: [], dolares: {}, dolaresPrevios: {} };

  const tanda1 = [];
  Object.keys(SIMBOLOS_YAHOO).forEach(function (clave) {
    tanda1.push({
      clave: clave, leer: leerYahoo_,
      pedido: { url: URL_YAHOO + encodeURIComponent(SIMBOLOS_YAHOO[clave]) + "?range=10d&interval=1d", headers: { "User-Agent": UA_NAVEGADOR } }
    });
  });
  tanda1.push({ clave: "tesoro", leer: leerTesoro_, pedido: { url: URL_TESORO.split("{anio}").join(hoy.slice(0, 4)) } });
  tanda1.push({
    clave: "merval", leer: leerMervalByma_,
    pedido: { url: URL_BYMA_INDICES, method: "post", contentType: "application/json", payload: "{}" }
  });
  tanda1.push({ clave: "dolarapi", leer: leerDolarapi_, pedido: { url: URL_DOLARAPI } });
  tanda1.push({ clave: "riesgo", leer: leerRiesgoPais_, pedido: { url: URL_RIESGO_PAIS } });
  tanda1.push({ clave: "bonos", leer: leerData912_, pedido: { url: URL_DATA912 + "arg_bonds" } });
  tanda1.push({ clave: "letras", leer: leerData912_, pedido: { url: URL_DATA912 + "arg_notes" } });
  leerTanda_(d, tanda1);

  // El 10 y el 30 salen del Tesoro (la curva oficial). Yahoo, solo si el
  // Tesoro no contestó o, para el cierre, si todavía no publicó la de hoy. A
  // la mañana Yahoo trae la tasa en plena rueda, no un cierre: ahí manda el
  // cierre oficial de ayer, con su fecha.
  const tesoro = d.tesoro;
  ["y10", "y30"].forEach(function (k) {
    const t = tesoro ? tesoro[k] : null;
    const y = d[k];
    if (y && (!t || (paraCierre && t.fecha !== hoy && y.fecha === hoy))) d[k] = y;
    else d[k] = t;
  });
  d.y2 = tesoro ? tesoro.y2 : null;

  // BYMA no devuelve el índice antes de que abra la rueda (el 20/10 a las
  // 9:56 vino vacío): se guarda el último que vino y se usa, con su fecha.
  const props = PropertiesService.getScriptProperties();
  if (d.merval) {
    props.setProperty("ULTIMO_MERVAL", JSON.stringify(d.merval));
  } else {
    const guardado = props.getProperty("ULTIMO_MERVAL");
    if (guardado) d.merval = JSON.parse(guardado);
  }

  // Dólares: el de hoy de dolarapi contra el del día hábil anterior de
  // argentinadatos (son del mismo autor y cierran igual).
  const tanda2 = [];
  DOLARES.forEach(function (fila) {
    const actual = d.dolarapi ? d.dolarapi[fila[2]] : null;
    if (!actual) return;
    const previo = diaHabilAnterior_(ultimoDiaHabilHasta_(actual.fecha));
    tanda2.push({
      clave: fila[0], leer: leerDolarHistorico_,
      pedido: { url: URL_DOLAR_HISTORICO + fila[2] + "/" + previo.split("-").join("/") }
    });
  });
  leerTanda_(d.dolaresPrevios, tanda2, d.errores);
  DOLARES.forEach(function (fila) {
    const actual = d.dolarapi ? d.dolarapi[fila[2]] : null;
    const previo = d.dolaresPrevios[fila[0]];
    d.dolares[fila[0]] = actual
      ? { valor: actual.valor, fecha: actual.fecha, varPct: previo ? (actual.valor / previo - 1) * 100 : null }
      : null;
  });
  return d;
}

/** Hace los pedidos de una tanda y guarda en `destino[clave]` lo que lee cada uno. */
function leerTanda_(destino, tanda, errores) {
  errores = errores || destino.errores;
  const respuestas = traer_(tanda.map(function (t) { return t.pedido; }));
  tanda.forEach(function (t, i) {
    const r = respuestas[i];
    try {
      if (r.error) throw new Error(r.error);
      if (r.codigo !== 200) throw new Error("HTTP " + r.codigo);
      destino[t.clave] = t.leer(r.texto);
    } catch (err) {
      destino[t.clave] = null;
      const msj = t.clave + " (" + t.pedido.url.split("?")[0] + "): " + (err && err.message ? err.message : err);
      errores.push(msj);
      console.error("Mercado: " + msj);
    }
  });
}

/**
 * `fetchAll` en paralelo. Si tira (una URL que ni siquiera conecta tumba la
 * tanda entera), se repite de a uno para que una fuente caída no se lleve a
 * las demás.
 */
function traer_(pedidos) {
  const completos = pedidos.map(function (p) {
    const c = { muteHttpExceptions: true };
    Object.keys(p).forEach(function (k) { c[k] = p[k]; });
    return c;
  });
  const aRespuesta = function (r) { return { codigo: r.getResponseCode(), texto: r.getContentText() }; };
  try {
    return UrlFetchApp.fetchAll(completos).map(aRespuesta);
  } catch (err) {
    console.warn("Mercado: fetchAll falló (" + err + "); se reintenta de a uno.");
    return completos.map(function (p) {
      try {
        const url = p.url;
        const opciones = {};
        Object.keys(p).forEach(function (k) { if (k !== "url") opciones[k] = p[k]; });
        return aRespuesta(UrlFetchApp.fetch(url, opciones));
      } catch (e) {
        return { error: String(e) };
      }
    });
  }
}

/** Yahoo: último cierre de la serie, su fecha (en la zona del mercado) y la variación contra el anterior. */
function leerYahoo_(texto) {
  const r = JSON.parse(texto).chart.result[0];
  const zona = r.meta.exchangeTimezoneName;
  const cierres = r.indicators.quote[0].close;
  const puntos = [];
  (r.timestamp || []).forEach(function (t, i) {
    if (cierres[i] == null) return; // día sin dato (el 19/10 el ^MERV quedó así)
    const fecha = Utilities.formatDate(new Date(t * 1000), zona, "yyyy-MM-dd");
    if (puntos.length && puntos[puntos.length - 1].fecha === fecha) puntos.pop();
    puntos.push({ fecha: fecha, valor: cierres[i] });
  });
  if (puntos.length < 2) throw new Error("serie con menos de dos cierres");
  const u = puntos[puntos.length - 1], a = puntos[puntos.length - 2];
  return { valor: u.valor, fecha: u.fecha, varPct: (u.valor / a.valor - 1) * 100, varPb: (u.valor - a.valor) * 100 };
}

/** Tesoro: curva oficial (CSV, lo más nuevo arriba). Devuelve 2, 10 y 30 años. */
function leerTesoro_(texto) {
  const filas = texto.trim().split(/\r?\n/).map(function (l) {
    return l.split(",").map(function (c) { return c.replace(/^"|"$/g, ""); });
  });
  const cab = filas[0];
  const col = { y2: cab.indexOf("2 Yr"), y10: cab.indexOf("10 Yr"), y30: cab.indexOf("30 Yr") };
  if (col.y2 < 0 || col.y10 < 0 || col.y30 < 0) throw new Error("columnas inesperadas: " + cab.join(","));
  if (filas.length < 2) throw new Error("sin datos");
  const fecha = function (mdy) { const p = mdy.split("/"); return p[2] + "-" + p[0] + "-" + p[1]; };
  const res = {};
  Object.keys(col).forEach(function (k) {
    const u = Number(filas[1][col[k]]);
    const a = filas.length > 2 ? Number(filas[2][col[k]]) : NaN;
    res[k] = { valor: u, fecha: fecha(filas[1][0]), varPb: isNaN(a) ? null : (u - a) * 100 };
  });
  return res;
}

/** BYMA: MSCI MERVAL (símbolo MMSCI). `variation` viene como fracción. */
function leerMervalByma_(texto) {
  const datos = JSON.parse(texto).data || [];
  const m = datos.filter(function (x) { return x.symbol === "MMSCI"; })[0];
  if (!m) throw new Error("no vino MMSCI");
  const valor = m.price != null ? m.price : m.closingPrice;
  return { valor: valor, fecha: m.date, varPct: m.variation != null ? m.variation * 100 : null };
}

/** dolarapi: venta de cada casa y la fecha (hora argentina) de su última actualización. */
function leerDolarapi_(texto) {
  const res = {};
  JSON.parse(texto).forEach(function (x) {
    res[x.casa] = { valor: x.venta, fecha: Utilities.formatDate(new Date(x.fechaActualizacion), ZONA_AR, "yyyy-MM-dd") };
  });
  return res;
}

function leerDolarHistorico_(texto) {
  const v = JSON.parse(texto).venta;
  if (typeof v !== "number") throw new Error("sin venta");
  return v;
}

/** argentinadatos: la serie entera de riesgo país; se usan las dos últimas. */
function leerRiesgoPais_(texto) {
  const serie = JSON.parse(texto);
  if (serie.length < 2) throw new Error("serie corta");
  const u = serie[serie.length - 1], a = serie[serie.length - 2];
  return { valor: u.valor, fecha: u.fecha, varPb: u.valor - a.valor };
}

/** data912: precio (`c`), variación del día y volumen, por símbolo. No trae fecha. */
function leerData912_(texto) {
  const res = {};
  JSON.parse(texto).forEach(function (x) { res[x.symbol] = { valor: x.c, varPct: x.pct_change, volumen: x.v }; });
  return res;
}


// ---------------------------------------------------------------------------
// 3. Armar los textos
// ---------------------------------------------------------------------------

function armarTableroMatutino_(d, hoy) {
  const l = ["📊 TABLERO MACRO & FINANCIERO"];
  DOLARES.forEach(function (fila) {
    l.push("* " + fila[1] + ": " + lineaPrecio_(d.dolares[fila[0]], "ARS ", 2, hoy));
  });
  l.push("* Riesgo País: " + lineaPb_(d.riesgo, 0, " pb", hoy));
  l.push("* MSCI Merval: " + lineaPrecio_(d.merval, "", 2, hoy, " pts"));
  l.push("* S&P 500: " + lineaPrecio_(d.sp, "", 2, hoy, " pts"));
  l.push("* Nasdaq: " + lineaPrecio_(d.nasdaq, "", 2, hoy, " pts"));
  l.push("* Dow Jones: " + lineaPrecio_(d.dow, "", 2, hoy, " pts"));
  l.push("* UST 10Y: " + lineaPb_(d.y10, 2, "%", hoy));
  l.push("* Petróleo Brent: " + lineaPrecio_(d.brent, "USD ", 2, hoy));
  l.push("* Oro: " + lineaPrecio_(d.oro, "USD ", 2, hoy));
  l.push("_Datos de las fuentes; entre corchetes, la fecha si no es de hoy._");
  return l.join("\n");
}

function armarTextoCierre_(d, hoy) {
  const b = [];
  b.push("*📊 CIERRE DE MERCADOS - " + fechaLarga_(hoy) + "*");

  // EE.UU. — acciones
  const usa = [["S&P 500", d.sp], ["Nasdaq", d.nasdaq], ["Dow Jones", d.dow]];
  const s = ["*🇺🇸 ACCIONES*"];
  if (d.sp && d.sp.fecha !== hoy) s.push("Hoy no hubo rueda en Wall Street: último cierre del " + fechaCorta_(d.sp.fecha) + ".");
  usa.forEach(function (x) { s.push("* " + x[0] + ": " + lineaPrecio_(x[1], "", 2, hoy, " pts")); });
  pushSiHay_(s, fraseSubasBajas_(usa, "los tres índices"));
  b.push(s.join("\n"));

  // EE.UU. — Treasuries
  const t = ["*🇺🇸 TREASURIES*"];
  [["2 años", d.y2], ["10 años", d.y10], ["30 años", d.y30]].forEach(function (x) {
    t.push("* " + x[0] + ": " + lineaPb_(x[1], 2, "%", hoy));
  });
  pushSiHay_(t, frasePendiente_(d.y2, d.y10));
  b.push(t.join("\n"));

  // Argentina — acciones
  const a = ["*🇦🇷 ACCIONES*"];
  const sinRuedaAr = d.merval && d.merval.fecha !== hoy;
  if (sinRuedaAr) a.push("Hoy no hubo rueda en BYMA: último dato del " + fechaCorta_(d.merval.fecha) + ".");
  a.push("* MSCI Merval: " + lineaPrecio_(d.merval, "", 2, hoy, " pts"));
  b.push(a.join("\n"));

  // data912 no trae fecha: se le pone la de la rueda del BYMA si no es hoy.
  const fechaRuedaAr = d.merval ? d.merval.fecha : hoy;
  const ar = function (x) { return x ? { valor: x.valor, varPct: x.varPct, fecha: fechaRuedaAr } : null; };

  // Argentina — hard dollar y riesgo país
  const h = ["*🇦🇷 BONOS HARD DOLLAR*"];
  const bonos = BONOS_HD.map(function (sim) { return [sim, d.bonos ? ar(d.bonos[sim + "D"]) : null]; });
  bonos.forEach(function (x) { h.push("* " + x[0] + ": " + lineaPrecio_(x[1], "USD ", 2, hoy)); });
  h.push("* Riesgo País: " + lineaPb_(d.riesgo, 0, " pb", hoy));
  pushSiHay_(h, fraseSubasBajas_(bonos, "los " + BONOS_HD.length + " bonos"));
  b.push(h.join("\n"));

  // Argentina — dólar
  const u = ["*🇦🇷 DÓLAR*"];
  DOLARES.forEach(function (fila) { u.push("* " + fila[1].replace("Dólar ", "") + ": " + lineaPrecio_(d.dolares[fila[0]], "ARS ", 2, hoy)); });
  b.push(u.join("\n"));

  // Argentina — curva en pesos (promedio de la variación de precio del día)
  const p = ["*🇦🇷 CURVA EN PESOS*"];
  [["Lecaps", d.letras, RE_LECAP], ["Boncaps", d.bonos, RE_BONCAP], ["CER", d.bonos, RE_CER]].forEach(function (x) {
    p.push("* " + x[0] + ": " + lineaPromedio_(x[1], x[2], fechaRuedaAr, hoy));
  });
  b.push(p.join("\n"));

  b.push("_Fuentes: Yahoo, Tesoro de EE.UU., BYMA, data912, dolarapi y argentinadatos. Entre corchetes, la fecha si el dato no es de hoy._");
  return b.join("\n\n");
}


// --- Renglones y frases ------------------------------------------------------

/** "ARS 1.524,50 (+0,43%)", con "[16/10]" si no es de hoy; "s/d" si no hay dato. */
function lineaPrecio_(x, prefijo, dec, hoy, sufijo) {
  if (!x || x.valor == null) return "s/d";
  const v = x.varPct != null ? " (" + fmtPct_(x.varPct) + ")" : "";
  return prefijo + fmtNum_(x.valor, dec) + (sufijo || "") + v + marcaFecha_(x.fecha, hoy);
}

/** Tasas y riesgo país: nivel y variación en puntos básicos. */
function lineaPb_(x, dec, unidad, hoy) {
  if (!x || x.valor == null) return "s/d";
  const v = x.varPb != null ? " (" + fmtPb_(x.varPb) + ")" : "";
  return fmtNum_(x.valor, dec) + unidad + v + marcaFecha_(x.fecha, hoy);
}

function lineaPromedio_(tabla, re, fecha, hoy) {
  if (!tabla) return "s/d";
  const vars = Object.keys(tabla)
    .filter(function (sim) { return re.test(sim) && tabla[sim].volumen > 0 && tabla[sim].varPct != null; })
    .map(function (sim) { return tabla[sim].varPct; });
  if (!vars.length) return "s/d";
  const prom = vars.reduce(function (s, v) { return s + v; }, 0) / vars.length;
  return fmtPct_(prom) + " prom. (" + vars.length + " títulos, de " + fmtPct_(Math.min.apply(null, vars)) +
    " a " + fmtPct_(Math.max.apply(null, vars)) + ")" + marcaFecha_(fecha, hoy);
}

/** "Subieron los tres índices." / "Bajaron …" / "Mixto: subieron A; bajaron B." */
function fraseSubasBajas_(pares, todos) {
  if (pares.some(function (x) { return !x[1] || x[1].varPct == null; })) return null;
  const suben = pares.filter(function (x) { return x[1].varPct > 0; }).map(function (x) { return x[0]; });
  const bajan = pares.filter(function (x) { return x[1].varPct < 0; }).map(function (x) { return x[0]; });
  if (suben.length === pares.length) return "Subieron " + todos + ".";
  if (bajan.length === pares.length) return "Bajaron " + todos + ".";
  const partes = [];
  if (suben.length) partes.push("subieron " + suben.join(", "));
  if (bajan.length) partes.push("bajaron " + bajan.join(", "));
  const quietos = pares.length - suben.length - bajan.length;
  if (quietos) partes.push(quietos + " sin cambios");
  return "Mixto: " + partes.join("; ") + ".";
}

/** Pendiente 2–10: si se empinó o se aplanó, con los puntos básicos de antes y de ahora. */
function frasePendiente_(y2, y10) {
  if (!y2 || !y10 || y2.varPb == null || y10.varPb == null || y2.fecha !== y10.fecha) return null;
  const ahora = Math.round((y10.valor - y2.valor) * 100);
  const antes = Math.round(((y10.valor - y10.varPb / 100) - (y2.valor - y2.varPb / 100)) * 100);
  if (ahora === antes) return "La pendiente 2–10 no cambió (" + ahora + " pb).";
  return "La curva 2–10 se " + (ahora > antes ? "empinó" : "aplanó") + ": de " + antes + " a " + ahora + " pb.";
}

function pushSiHay_(lista, frase) {
  if (frase) lista.push(frase);
}


// --- Formatos y fechas -------------------------------------------------------

/** 1234567.891 → "1.234.567,89" (sin depender del locale del proyecto). */
function fmtNum_(x, dec) {
  const partes = Math.abs(x).toFixed(dec).split(".");
  const entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const signo = x < 0 && Number(Math.abs(x).toFixed(dec)) !== 0 ? "-" : "";
  return signo + entero + (partes[1] ? "," + partes[1] : "");
}

function fmtPct_(p) {
  if (Math.abs(p) < 0.005) return "0,00%";
  return (p > 0 ? "+" : "") + fmtNum_(p, 2) + "%";
}

function fmtPb_(pb) {
  const r = Math.round(pb);
  if (r === 0) return "sin cambios";
  return (r > 0 ? "+" : "") + r + " pb";
}

function marcaFecha_(fecha, hoy) {
  return fecha && fecha !== hoy ? " [" + fechaCorta_(fecha) + "]" : "";
}

function hoyAR_() {
  return Utilities.formatDate(new Date(), ZONA_AR, "yyyy-MM-dd");
}

/** "2026-10-16" → "16/10" */
function fechaCorta_(iso) {
  const p = iso.split("-");
  return p[2] + "/" + p[1];
}

/** "2026-10-16" → "16/10/2026" */
function fechaLarga_(iso) {
  const p = iso.split("-");
  return p[2] + "/" + p[1] + "/" + p[0];
}

function diaDeSemana_(iso) {
  const p = iso.split("-").map(Number);
  return new Date(Date.UTC(p[0], p[1] - 1, p[2])).getUTCDay(); // 0 = domingo
}

function sumarDias_(iso, n) {
  const p = iso.split("-").map(Number);
  return new Date(Date.UTC(p[0], p[1] - 1, p[2] + n)).toISOString().slice(0, 10);
}

/** El último lunes-a-viernes que no sea posterior a `iso` (sábado → viernes). */
function ultimoDiaHabilHasta_(iso) {
  let f = iso;
  while (diaDeSemana_(f) === 0 || diaDeSemana_(f) === 6) f = sumarDias_(f, -1);
  return f;
}

/** El lunes-a-viernes anterior a `iso` (no conoce feriados: ese día argentinadatos repite el valor). */
function diaHabilAnterior_(iso) {
  return ultimoDiaHabilHasta_(sumarDias_(iso, -1));
}
