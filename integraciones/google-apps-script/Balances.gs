/**
 * Balances de la semana (ADR-0011, docs/PLAN-BALANCES.md): el reloj.
 *
 * La SuperApp no tiene reloj (la máquina de Fly se duerme). Este archivo le
 * avisa cuándo armar la lista: el domingo desde las 20:00, en la primera
 * corrida del disparador de cada 10 minutos de `Reenvio.gs`. La SuperApp
 * trae el calendario de Nasdaq, arma la lista y la manda por la cola de
 * salida (o la guarda hasta que le escribas, por la ventana de 24 h).
 *
 * Acá no se trae ningún dato: solo se dice "es domingo, armá la semana del
 * lunes AAAA-MM-DD". Si la SuperApp no contesta o Nasdaq no anda (503), la
 * propiedad ULTIMO_BALANCES no se marca y la próxima corrida reintenta.
 *
 * Necesita `Reenvio.gs` (SUPERAPP_URL, SUPERAPP_TOKEN, requerirPropiedad_) y
 * `Mercado.gs` (ZONA_AR, hoyAR_, diaDeSemana_, sumarDias_) en el mismo proyecto.
 */

// La lista sale en la primera corrida del domingo desde esta hora.
const HORA_LISTA_BALANCES = "20:00";

/**
 * Si es domingo desde las 20:00 y la lista de la semana que viene todavía
 * no salió, se la pide a la SuperApp. La llama `reenviarBriefingAWhatsApp`.
 */
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
