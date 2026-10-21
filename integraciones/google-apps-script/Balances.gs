/**
 * Balances de la semana (ADR-0011, docs/PLAN-BALANCES.md): el reloj y el Calendar.
 *
 * La SuperApp no tiene reloj (la máquina de Fly se duerme). Este archivo le
 * avisa cuándo hacer cada cosa, con su **propio disparador** de cada 10
 * minutos (`relojDeBalances`), que no depende de los mails de Gemini:
 *
 *   - Domingo desde las 20:00: "armá la lista de la semana del lunes AAAA-MM-DD".
 *   - Lunes a viernes desde las 18:30: el resumen de los 📊 de **hoy** que
 *     presentaron antes de la apertura (cómo les fue en la rueda).
 *   - Todos los días desde las 9:30: el resumen de los 📊 de **ayer** que
 *     presentaron después del cierre o sin hora (cómo les fue en el posmercado).
 *
 * Los 📊 salen del Calendar (la fuente de verdad: entra lo que Franco eligió):
 * los eventos con la etiqueta `balance` (`TICKER:AAAA-MM-DD`) y su momento en
 * `balance_momento`, que pone `Codigo.gs` al agendar. Acá no se trae ningún
 * dato de mercado: los precios los trae la SuperApp.
 *
 * Si la SuperApp no contesta `ok: true`, la propiedad no se marca y la
 * próxima corrida reintenta; la SuperApp no repite un `id` que ya recibió.
 *
 * Necesita `Reenvio.gs` (SUPERAPP_URL, SUPERAPP_TOKEN, requerirPropiedad_) y
 * `Mercado.gs` (ZONA_AR, hoyAR_, diaDeSemana_, sumarDias_) en el mismo
 * proyecto. Instalación: correr `instalarDisparadorBalances` una vez.
 */

// La lista sale en la primera corrida del domingo desde esta hora.
const HORA_LISTA_BALANCES = "20:00";
// El resumen de las de antes de la apertura: después del cierre de Wall
// Street (17:00 hora argentina hasta el 1/11, 18:00 después).
const HORA_RESUMEN_PRE = "18:30";
// El resumen de las de después del cierre: el posmercado terminó a las
// 21:00 o 22:00 hora argentina del día anterior.
const HORA_RESUMEN_POST = "09:30";

/** El disparador: cada 10 minutos. Cada parte por separado, para que un error no tape a las otras. */
function relojDeBalances() {
  const props = PropertiesService.getScriptProperties();
  const base = requerirPropiedad_(props, "SUPERAPP_URL").replace(/\/+$/, "");
  const token = requerirPropiedad_(props, "SUPERAPP_TOKEN");
  [balancesPendientes_, resumenesPendientes_].forEach(function (paso) {
    try {
      paso(base, token);
    } catch (err) {
      // Queda en Ejecuciones; la próxima corrida reintenta.
      console.error(err && err.stack ? err.stack : err);
    }
  });
}

/** Deja un único disparador de `relojDeBalances` cada 10 minutos. */
function instalarDisparadorBalances() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === "relojDeBalances") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("relojDeBalances").timeBased().everyMinutes(10).create();
  console.log("Disparador instalado: relojDeBalances cada 10 minutos.");
}


// ---------------------------------------------------------------------------
// La lista del domingo
// ---------------------------------------------------------------------------

/** Si es domingo desde las 20:00 y la lista de la semana que viene no salió, se la pide a la SuperApp. */
function balancesPendientes_(base, token) {
  const hoy = hoyAR_();
  if (diaDeSemana_(hoy) !== 0) return;
  if (Utilities.formatDate(new Date(), ZONA_AR, "HH:mm") < HORA_LISTA_BALANCES) return;

  const lunes = sumarDias_(hoy, 1);
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty("ULTIMO_BALANCES") === lunes) return;

  // `id` fijo por semana: si la respuesta se pierde y se reintenta, la
  // SuperApp reconoce la misma lista y no la rearma ni la manda dos veces.
  const cuerpo = { accion: "semana", lunes: lunes, id: "balances-" + lunes };
  if (postearASuperApp_(base + "/api/balances", token, cuerpo, "[balances] semana del " + lunes)) {
    props.setProperty("ULTIMO_BALANCES", lunes);
  }
}

/**
 * Manual, desde el editor: pide la lista de la semana del próximo lunes (o
 * de hoy, si es lunes) con un `id` nuevo, aunque ya haya salido.
 */
function pedirBalancesAhora() {
  const props = PropertiesService.getScriptProperties();
  const base = requerirPropiedad_(props, "SUPERAPP_URL").replace(/\/+$/, "");
  const token = requerirPropiedad_(props, "SUPERAPP_TOKEN");
  const hoy = hoyAR_();
  const dia = diaDeSemana_(hoy);
  const lunes = dia === 1 ? hoy : sumarDias_(hoy, (8 - dia) % 7 || 7);
  postearASuperApp_(base + "/api/balances", token,
    { accion: "semana", lunes: lunes, id: "balances-" + lunes + "-manual-" + new Date().getTime() },
    "[balances manual] semana del " + lunes);
}


// ---------------------------------------------------------------------------
// El resumen del día
// ---------------------------------------------------------------------------

/**
 * Desde las 18:30 de un día hábil, las de hoy que presentaron antes de la
 * apertura. Desde las 9:30, las de ayer que presentaron después del cierre o
 * sin hora. Cada tanda sale una vez (ULTIMO_RESUMEN_PRE / ULTIMO_RESUMEN_POST).
 */
function resumenesPendientes_(base, token) {
  const hoy = hoyAR_();
  const hora = Utilities.formatDate(new Date(), ZONA_AR, "HH:mm");
  const dia = diaDeSemana_(hoy);
  if (dia !== 0 && dia !== 6 && hora >= HORA_RESUMEN_PRE) {
    resumenDeTanda_(base, token, hoy, "pre", ["pre"], "ULTIMO_RESUMEN_PRE");
  }
  if (hora >= HORA_RESUMEN_POST) {
    resumenDeTanda_(base, token, sumarDias_(hoy, -1), "post", ["post", ""], "ULTIMO_RESUMEN_POST");
  }
}

function resumenDeTanda_(base, token, fecha, tanda, momentos, propiedad) {
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty(propiedad) === fecha) return;
  const empresas = balancesDelDia_(fecha).filter(function (e) { return momentos.indexOf(e.momento) >= 0; });
  if (!empresas.length) {
    props.setProperty(propiedad, fecha);   // nada que contar ese día
    return;
  }
  const cuerpo = { accion: "resumen", fecha: fecha, tanda: tanda, empresas: empresas,
                   id: "resumen-" + tanda + "-" + fecha };
  if (postearASuperApp_(base + "/api/balances", token, cuerpo, "[balances] resumen " + tanda + " " + fecha)) {
    props.setProperty(propiedad, fecha);
  }
}

/** Los 📊 agendados por el Secretario para ese día: [{ticker, momento}]. */
function balancesDelDia_(fecha) {
  const p = fecha.split("-").map(Number);
  const eventos = CalendarApp.getDefaultCalendar().getEventsForDay(new Date(p[0], p[1] - 1, p[2]));
  const salida = [];
  eventos.forEach(function (ev) {
    const clave = ev.getTag("balance");
    if (!clave || clave.split(":")[1] !== fecha) return;   // no es un 📊 del Secretario
    salida.push({ ticker: clave.split(":")[0], momento: ev.getTag("balance_momento") || "" });
  });
  return salida;
}

/** Manual, desde el editor: muestra qué 📊 hay hoy y ayer, sin mandar nada. */
function probarBalancesDelDia() {
  const hoy = hoyAR_();
  console.log("Hoy (" + hoy + "): " + JSON.stringify(balancesDelDia_(hoy)));
  const ayer = sumarDias_(hoy, -1);
  console.log("Ayer (" + ayer + "): " + JSON.stringify(balancesDelDia_(ayer)));
}


/** POST con el Bearer de la SuperApp. true solo si contestó {"ok": true}. */
function postearASuperApp_(url, token, cuerpo, rotulo) {
  const resp = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify(cuerpo),
    muteHttpExceptions: true
  });
  const codigo = resp.getResponseCode();
  const texto = resp.getContentText();
  console.log(rotulo + " → HTTP " + codigo + " " + texto);
  try {
    return codigo === 200 && JSON.parse(texto).ok === true;
  } catch (err) {
    console.error("La SuperApp no devolvió JSON: " + err);
    return false;
  }
}
