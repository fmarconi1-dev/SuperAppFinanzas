/**
 * Reenvío de los briefings de Gemini al Secretario (SuperApp en Fly.io).
 *
 * Reemplaza al script que los mandaba por CallMeBot (16/10/2026): misma
 * función, misma etiqueta `WA-Enviado`, mismo filtro, así el disparador de
 * cada 10 minutos que ya existe sigue sirviendo.
 *
 * Toma de Gmail el mail "[Briefing-WhatsApp] Briefing Matutino y Agenda - …",
 * le pone el tablero de números de `Mercado.gs`, acorta sus links y lo manda
 * a `POST /api/briefing`. La SuperApp lo manda tal cual por WhatsApp (o lo
 * guarda hasta que le escribas, por la ventana de 24 h de Meta).
 *
 * Desde el 19/10/2026 (ADR-0010) el cierre de mercado no sale de Gemini: lo
 * arma `Mercado.gs` y lo manda este mismo disparador desde las 18:30. Si
 * Gemini todavía manda su "Cierre de Mercado", se descarta.
 *
 * Nada de credenciales en este archivo. Propiedades del script
 * (Configuración del proyecto -> Propiedades del script):
 *   SUPERAPP_URL      https://superapp-finanzas.fly.dev
 *   SUPERAPP_TOKEN    el mismo valor que SUPERAPP_API_TOKEN en `fly secrets`
 *
 * Necesita `Mercado.gs` en el mismo proyecto. `Codigo.gs` (agenda: Calendar
 * y Tasks) y `Balances.gs` (balances de la semana, con su propio disparador)
 * son aparte.
 */

const NOMBRE_ETIQUETA = "WA-Enviado";
const FILTRO_BUSQUEDA = 'subject:"[Briefing-WhatsApp]" -label:' + NOMBRE_ETIQUETA + " newer_than:1d";

// Links más cortos que esto se dejan como están: acortarlos no gana nada.
const LARGO_MINIMO_PARA_ACORTAR = 35;

// Dónde va el tablero en el matutino: Gemini deja este renglón solo (ver
// docs/PEDIDO-GEMINI.md). Si no lo deja, se reemplaza su bloque "TABLERO".
const MARCA_TABLERO = "[TABLERO]";

// ---------------------------------------------------------------------------
// 1. Briefings de Gemini (mañana) y cierre de mercado: -> SuperApp -> WhatsApp
// ---------------------------------------------------------------------------

/**
 * Reenvía al Secretario los mails de Gemini que todavía no salieron y, desde
 * las 18:30 de un día hábil, el cierre de mercado de hoy si todavía no salió.
 *
 * Reemplaza al reenvío por CallMeBot (16/10/2026). Cambios contra aquel:
 *   - va a la SuperApp (`POST /api/briefing`), no a CallMeBot. La SuperApp ya
 *     sabe tu número, parte en 4.096 caracteres y respeta la ventana de 24 h;
 *   - ya no cambia `$` por `ARS` (era un parche para el PHP de CallMeBot) ni
 *     parte en bloques de 650 con esperas de 6 s;
 *   - procesa TODOS los mails pendientes, del más viejo al más nuevo (antes
 *     agarraba uno por corrida);
 *   - un lock impide que dos corridas solapadas manden lo mismo dos veces;
 *   - nada de claves en el código: salen de las Propiedades del script.
 */
function reenviarBriefingAWhatsApp() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) {
    console.log("Ya hay una corrida en curso; esta se saltea.");
    return;
  }
  try {
    const props = PropertiesService.getScriptProperties();
    const url = requerirPropiedad_(props, "SUPERAPP_URL").replace(/\/+$/, "") + "/api/briefing";
    const token = requerirPropiedad_(props, "SUPERAPP_TOKEN");
    if (reenviarMailsPendientes_(url, token)) cierrePendiente_(url, token);
  } finally {
    lock.releaseLock();
  }
}

/** Devuelve false si un mail no salió (el cierre espera a la próxima corrida, para no adelantarse). */
function reenviarMailsPendientes_(url, token) {
  const etiqueta = GmailApp.getUserLabelByName(NOMBRE_ETIQUETA) || GmailApp.createLabel(NOMBRE_ETIQUETA);

  // `search` devuelve los más nuevos primero: se dan vuelta para mandar en orden.
  const hilos = GmailApp.search(FILTRO_BUSQUEDA, 0, 10).reverse();
  for (let i = 0; i < hilos.length; i++) {
    const hilo = hilos[i];
    const mensajes = hilo.getMessages();
    const ultimo = mensajes[mensajes.length - 1];
    const asunto = ultimo.getSubject();

    // El cierre de Gemini traía números de otros días: ya no se reenvía.
    if (/cierre de mercado/i.test(asunto)) {
      console.warn("Descartado (el cierre lo arma Mercado.gs; apagá esta acción en Gemini): " + asunto);
      hilo.addLabel(etiqueta);
      continue;
    }

    const texto = acortarUrls(ponerTablero_(ultimo.getPlainBody().replace(/\r\n/g, "\n").trim()));
    // `id` = id del mail en Gmail: si la respuesta se pierde y esto se
    // reintenta, la SuperApp reconoce el mismo mail y no lo manda dos veces.
    // Si no lo tomó, corta acá y el próximo disparo reintenta, sin saltearse
    // el orden.
    if (!mandarASuperApp_(url, token, texto, "briefing", ultimo.getId(), "[briefing] " + asunto)) return false;
    hilo.addLabel(etiqueta);
  }
  return true;
}

/**
 * POST a `/api/briefing`. true solo si la SuperApp lo tomó: {"ok": true} con
 * estado "enviado" (ya salió) o "en_cola" (sale apenas le escribas al bot).
 */
function mandarASuperApp_(url, token, texto, tipo, id, rotulo) {
  // El token va en el header, no en la URL: las query strings quedan en
  // los logs de nginx y de `fly logs`.
  const resp = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify({ texto: texto, tipo: tipo, id: id }),
    muteHttpExceptions: true
  });
  const codigo = resp.getResponseCode();
  const cuerpo = resp.getContentText();
  console.log(rotulo + " → HTTP " + codigo + " " + cuerpo);
  try {
    return codigo === 200 && JSON.parse(cuerpo).ok === true;
  } catch (err) {
    console.error("La SuperApp no devolvió JSON: " + err);
    return false;
  }
}

/**
 * Pone en el matutino el tablero de `Mercado.gs` en lugar de los números de
 * Gemini. Busca, en orden: el renglón `[TABLERO]`; el bloque de Gemini que
 * empieza con un título que dice "TABLERO" (hasta el próximo título); el
 * título de noticias, para ponerlo antes; y si no, lo agrega al final.
 */
function ponerTablero_(texto, tablero) {
  if (tablero == null) {
    try {
      tablero = tableroMatutino_();
    } catch (err) {
      // Un error de programación en Mercado.gs no puede trabar el matutino,
      // pero tampoco pueden salir los números de Gemini: se avisa en el texto.
      console.error(err && err.stack ? err.stack : err);
      tablero = "📊 TABLERO MACRO & FINANCIERO\nNo se pudo armar (error en Mercado.gs: " + err + ").";
    }
  }
  const lineas = texto.split("\n");
  const esVineta = function (l) { return /^\s*([-•·]|\*\s)/.test(l); };
  // Título de un bloque de cotizaciones de Gemini: "📊 TABLERO …" (en
  // mayúsculas, para no agarrar una frase de la síntesis que diga "tablero").
  const esTituloTablero = function (l) { return !esVineta(l) && (/TABLERO/.test(l) || /^\W*📊/.test(l)); };

  // Si Gemini armó su propio bloque de cotizaciones, sale siempre, aunque
  // también haya dejado la marca: sus números no se mandan nunca.
  let enLugarDe = -1;
  const titulo = lineas.findIndex(esTituloTablero);
  if (titulo !== -1) {
    let fin = titulo + 1;
    while (fin < lineas.length && (lineas[fin].trim() === "" || esVineta(lineas[fin]))) fin++;
    lineas.splice(titulo, fin - titulo, "");
    enLugarDe = titulo;
  }

  const marca = lineas.findIndex(function (l) { return l.trim() === MARCA_TABLERO; });
  if (marca !== -1) {
    lineas.splice(marca, 1, tablero);
    return lineas.join("\n").replace(/\n{3,}/g, "\n\n");
  }
  if (enLugarDe !== -1) {
    lineas.splice(enLugarDe, 0, tablero);
    return lineas.join("\n").replace(/\n{3,}/g, "\n\n");
  }

  const noticias = lineas.findIndex(function (l) { return /NOTICIAS/i.test(l) && !esVineta(l); });
  if (noticias !== -1) {
    lineas.splice(noticias, 0, tablero, "");
    return lineas.join("\n");
  }
  return texto + "\n\n" + tablero;
}

/**
 * Acorta con TinyURL los links largos del texto, todos en paralelo
 * (UrlFetchApp.fetchAll). Si TinyURL falla para un link, ese link queda
 * original: un link largo es incómodo, uno perdido es peor.
 */
function acortarUrls(texto) {
  const encontrados = texto.match(/https?:\/\/[^\s<>()"'\[\]]+/g) || [];
  const largos = [];
  encontrados.forEach(function (u) {
    const limpio = u.replace(/[.,;:!?]+$/, "");
    if (limpio.length >= LARGO_MINIMO_PARA_ACORTAR && largos.indexOf(limpio) === -1) largos.push(limpio);
  });
  if (largos.length === 0) return texto;

  const pedidos = largos.map(function (u) {
    return {
      url: "https://tinyurl.com/api-create.php?url=" + encodeURIComponent(u),
      muteHttpExceptions: true
    };
  });

  let respuestas;
  try {
    respuestas = UrlFetchApp.fetchAll(pedidos);
  } catch (err) {
    console.warn("TinyURL no respondió, el briefing sale con links originales: " + err);
    return texto;
  }

  let resultado = texto;
  largos.forEach(function (original, i) {
    const r = respuestas[i];
    const corto = r.getContentText().trim();
    if (r.getResponseCode() === 200 && /^https:\/\/tinyurl\.com\/\S+$/.test(corto)) {
      resultado = resultado.split(original).join(corto);
    } else {
      console.warn("TinyURL falló para " + original + " (" + r.getResponseCode() + ")");
    }
  });
  return resultado;
}


// ---------------------------------------------------------------------------
// Utilidades e instalación
// ---------------------------------------------------------------------------

function requerirPropiedad_(props, nombre) {
  const v = props.getProperty(nombre);
  if (!v) throw new Error("Falta la propiedad del script " + nombre);
  return v;
}

/** Deja un único disparador cada 10 minutos para el briefing. */
function instalarDisparadores() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === "reenviarBriefingAWhatsApp") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("reenviarBriefingAWhatsApp").timeBased().everyMinutes(10).create();
  console.log("Disparador instalado: reenviarBriefingAWhatsApp cada 10 minutos.");
}

/** Prueba el acortador con un texto de ejemplo. */
function probarAcortador() {
  console.log(acortarUrls("Nota: https://www.example.com/una/ruta/bastante/larga/para/probar?x=1. Corto: https://g.co/a"));
}
