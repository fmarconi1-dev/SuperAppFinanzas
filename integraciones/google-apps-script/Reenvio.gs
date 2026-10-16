/**
 * Reenvío de los briefings de Gemini al Secretario (SuperApp en Fly.io).
 *
 * Reemplaza al script que los mandaba por CallMeBot (16/10/2026): misma
 * función, misma etiqueta `WA-Enviado`, mismo filtro, así el disparador de
 * cada 10 minutos que ya existe sigue sirviendo.
 *
 * Toma de Gmail los mails "[Briefing-WhatsApp] Briefing Matutino y Agenda - …"
 * y "[Briefing-WhatsApp] Cierre de Mercado - …", acorta sus links y los manda
 * a `POST /api/briefing`. La SuperApp los manda tal cual por WhatsApp (o los
 * guarda hasta que le escribas, por la ventana de 24 h de Meta).
 *
 * Nada de credenciales en este archivo. Propiedades del script
 * (Configuración del proyecto -> Propiedades del script):
 *   SUPERAPP_URL      https://superapp-finanzas.fly.dev
 *   SUPERAPP_TOKEN    el mismo valor que SUPERAPP_API_TOKEN en `fly secrets`
 *
 * Funciona solo, sin `Codigo.gs`. `Codigo.gs` (agenda: Calendar y Tasks) se
 * suma al mismo proyecto más adelante.
 */

const NOMBRE_ETIQUETA = "WA-Enviado";
const FILTRO_BUSQUEDA = 'subject:"[Briefing-WhatsApp]" -label:' + NOMBRE_ETIQUETA + " newer_than:1d";

// Links más cortos que esto se dejan como están: acortarlos no gana nada.
const LARGO_MINIMO_PARA_ACORTAR = 35;

// ---------------------------------------------------------------------------
// 1. Briefings de Gemini (mañana y cierre): Gmail -> SuperApp -> WhatsApp
// ---------------------------------------------------------------------------

/**
 * Reenvía al Secretario los mails de Gemini que todavía no salieron.
 *
 * Reemplaza al reenvío por CallMeBot (16/10/2026). Cambios contra aquel:
 *   - va a la SuperApp (`POST /api/briefing`), no a CallMeBot. La SuperApp ya
 *     sabe tu número, parte en 4.096 caracteres y respeta la ventana de 24 h;
 *   - ya no cambia `$` por `ARS` (era un parche para el PHP de CallMeBot) ni
 *     parte en bloques de 650 con esperas de 6 s;
 *   - procesa TODOS los mails pendientes, del más viejo al más nuevo (antes
 *     agarraba uno por corrida), y distingue el cierre por el asunto;
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
    const etiqueta = GmailApp.getUserLabelByName(NOMBRE_ETIQUETA) || GmailApp.createLabel(NOMBRE_ETIQUETA);

    // `search` devuelve los más nuevos primero: se dan vuelta para mandar en orden.
    const hilos = GmailApp.search(FILTRO_BUSQUEDA, 0, 10).reverse();
    if (hilos.length === 0) {
      console.log("No hay briefings pendientes.");
      return;
    }

    for (let i = 0; i < hilos.length; i++) {
      const hilo = hilos[i];
      const mensajes = hilo.getMessages();
      const ultimo = mensajes[mensajes.length - 1];
      const asunto = ultimo.getSubject();
      const tipo = /cierre de mercado/i.test(asunto) ? "cierre" : "briefing";
      const texto = acortarUrls(ultimo.getPlainBody().replace(/\r\n/g, "\n").trim());

      // El token va en el header, no en la URL: las query strings quedan en
      // los logs de nginx y de `fly logs`.
      const resp = UrlFetchApp.fetch(url, {
        method: "post",
        contentType: "application/json",
        headers: { Authorization: "Bearer " + token },
        // `id` = id del mail en Gmail: si la respuesta se pierde y esto se
        // reintenta, la SuperApp reconoce el mismo mail y no lo manda dos veces.
        payload: JSON.stringify({ texto: texto, tipo: tipo, id: ultimo.getId() }),
        muteHttpExceptions: true
      });
      const codigo = resp.getResponseCode();
      const cuerpo = resp.getContentText();
      console.log("[" + tipo + "] " + asunto + " → HTTP " + codigo + " " + cuerpo);

      // Se etiqueta solo si la SuperApp lo tomó: {"ok": true} con estado
      // "enviado" (ya salió) o "en_cola" (sale apenas le escribas al bot).
      // Cualquier otra cosa corta acá y el próximo disparo reintenta, sin
      // saltearse el orden.
      let ok = false;
      try {
        ok = codigo === 200 && JSON.parse(cuerpo).ok === true;
      } catch (err) {
        console.error("La SuperApp no devolvió JSON: " + err);
      }
      if (!ok) break;
      hilo.addLabel(etiqueta);
    }
  } finally {
    lock.releaseLock();
  }
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
