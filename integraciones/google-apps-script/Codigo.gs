/**
 * Puente Google <-> SuperAppFinanzas.
 *
 * Dos sentidos:
 *   1. reenviarBriefingAWhatsApp(): toma el briefing matutino de Gmail, acorta
 *      sus links y lo manda a la API de la SuperApp (Fly.io), que le agrega el
 *      resumen de finanzas y lo envía por WhatsApp.
 *   2. doPost(e): la SuperApp le pide crear/listar eventos y tareas de Google
 *      Calendar / Google Tasks. El contrato está en README.md (misma carpeta).
 *
 * Nada de credenciales en este archivo: todo sale de las Propiedades del
 * script (Configuración del proyecto -> Propiedades del script):
 *   SUPERAPP_URL      https://superapp-finanzas.fly.dev
 *   SUPERAPP_TOKEN    el mismo valor que SUPERAPP_API_TOKEN en `fly secrets`
 *   SECRETO_WEBHOOK   el mismo valor que GOOGLE_WORKSPACE_SECRET en `fly secrets`
 *   CALENDARIOS       (opcional) ids separados por coma para listar por defecto
 *
 * La zona horaria sale de appsscript.json (America/Argentina/Buenos_Aires):
 * `new Date(anio, mes, dia, h, m)` la usa, así que tiene que estar bien ahí.
 */

const NOMBRE_ETIQUETA = "WA-Enviado";
const FILTRO_BUSQUEDA = 'subject:"[Briefing-WhatsApp]" -label:' + NOMBRE_ETIQUETA + " newer_than:1d";

// Links más cortos que esto se dejan como están: acortarlos no gana nada.
const LARGO_MINIMO_PARA_ACORTAR = 35;

// Tope de rango para listar_eventos: el dashboard pide la semana; esto evita
// que un pedido mal armado recorra años de calendario.
const MAX_DIAS_LISTADO = 62;

// Cuánto se recuerda un id_solicitud ya procesado (máximo de CacheService).
const SEGUNDOS_IDEMPOTENCIA = 6 * 60 * 60;

const RE_FECHA = /^(\d{4})-(\d{2})-(\d{2})$/;
const RE_HORA = /^([01]\d|2[0-3]):([0-5]\d)$/;


// ---------------------------------------------------------------------------
// 1. Briefing matutino: Gmail -> SuperApp -> WhatsApp
// ---------------------------------------------------------------------------

function reenviarBriefingAWhatsApp() {
  const props = PropertiesService.getScriptProperties();
  const url = requerirPropiedad_(props, "SUPERAPP_URL");
  const token = requerirPropiedad_(props, "SUPERAPP_TOKEN");

  const etiqueta = GmailApp.getUserLabelByName(NOMBRE_ETIQUETA) || GmailApp.createLabel(NOMBRE_ETIQUETA);

  const hilos = GmailApp.search(FILTRO_BUSQUEDA, 0, 1);
  if (hilos.length === 0) return;

  const hilo = hilos[0];
  const mensajes = hilo.getMessages();
  const crudo = mensajes[mensajes.length - 1].getPlainBody().replace(/\r\n/g, "\n").trim();
  const texto = acortarUrls(crudo);

  // El token va en el header, no en la URL: las query strings quedan en los
  // logs de nginx y de `fly logs`.
  const resp = UrlFetchApp.fetch(url.replace(/\/+$/, "") + "/api/briefing", {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify({ texto: texto }),
    muteHttpExceptions: true
  });

  const codigo = resp.getResponseCode();
  const cuerpo = resp.getContentText();
  console.log("Respuesta SuperApp: " + codigo + " - " + cuerpo);

  // Se etiqueta solo si la SuperApp confirma que el WhatsApp salió. Un 200
  // con {"ok": false} es un fallo: el próximo disparo lo reintenta.
  let ok = false;
  try {
    ok = codigo === 200 && JSON.parse(cuerpo).ok === true;
  } catch (err) {
    console.error("La SuperApp no devolvió JSON: " + err);
  }
  if (ok) hilo.addLabel(etiqueta);
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
// 2. Webhook: SuperApp -> Google Calendar / Google Tasks
// ---------------------------------------------------------------------------

/**
 * Apps Script no expone los headers del request, por eso el secreto viaja en
 * el cuerpo. Siempre responde HTTP 200 (ContentService no permite elegir el
 * código): el resultado real está en `ok`.
 */
function doPost(e) {
  let datos;
  try {
    datos = JSON.parse((e && e.postData && e.postData.contents) || "");
  } catch (err) {
    return respuestaJson_({ ok: false, error: "json_invalido", detalle: String(err) });
  }
  if (!datos || typeof datos !== "object" || Array.isArray(datos)) {
    return respuestaJson_({ ok: false, error: "json_invalido", detalle: "se esperaba un objeto" });
  }

  const secreto = PropertiesService.getScriptProperties().getProperty("SECRETO_WEBHOOK");
  if (!secreto) {
    return respuestaJson_({ ok: false, error: "sin_configurar", detalle: "Falta SECRETO_WEBHOOK en las propiedades del script" });
  }
  if (!iguales_(String(datos.secreto || ""), secreto)) {
    return respuestaJson_({ ok: false, error: "no_autorizado" });
  }

  const acciones = {
    crear_evento: crearEvento_,
    crear_tarea: crearTarea_,
    completar_tarea: completarTarea_,
    listar_calendarios: listarCalendarios_,
    listar_eventos: listarEventos_,
    listar_tareas: listarTareas_,
    resumen_semana: resumenSemana_
  };
  const accion = Object.prototype.hasOwnProperty.call(acciones, datos.accion) ? acciones[datos.accion] : null;
  if (!accion) {
    return respuestaJson_({ ok: false, error: "accion_invalida", detalle: String(datos.accion) });
  }

  // Idempotencia: si la SuperApp reintenta (timeout, cold start de Fly) con el
  // mismo id_solicitud, se devuelve el resultado anterior en vez de crear el
  // evento dos veces. Solo aplica a las acciones que escriben.
  const escribe = datos.accion.indexOf("crear_") === 0 || datos.accion === "completar_tarea";
  const cache = CacheService.getScriptCache();
  const clave = escribe && datos.id_solicitud ? "sol:" + String(datos.id_solicitud).slice(0, 200) : null;

  // Con clave, el chequeo de cache y la escritura van bajo lock: dos reintentos
  // simultáneos no pueden pasar los dos el chequeo y crear dos veces.
  const lock = clave ? LockService.getScriptLock() : null;
  if (lock && !lock.tryLock(20000)) {
    return respuestaJson_({ ok: false, error: "ocupado", detalle: "otra solicitud en curso; reintentar" });
  }
  try {
    if (clave) {
      const previo = cache.get(clave);
      if (previo) {
        const r = JSON.parse(previo);
        r.repetida = true;
        return respuestaJson_(r);
      }
    }

    let resultado;
    try {
      resultado = accion(datos);
    } catch (err) {
      if (err instanceof ParametroInvalido) {
        return respuestaJson_({ ok: false, error: "parametros_invalidos", detalle: err.message });
      }
      console.error(err && err.stack ? err.stack : err);
      return respuestaJson_({ ok: false, error: "error_interno", detalle: String(err) });
    }

    resultado.ok = true;
    if (clave) cache.put(clave, JSON.stringify(resultado), SEGUNDOS_IDEMPOTENCIA);
    return respuestaJson_(resultado);
  } finally {
    if (lock) lock.releaseLock();
  }
}

/** Ping sin datos: sirve para probar que el deploy responde. */
function doGet() {
  return respuestaJson_({ ok: true, servicio: "superapp-google" });
}


// --- Acciones de escritura --------------------------------------------------

function crearEvento_(d) {
  const titulo = requerirTexto_(d.titulo, "titulo");
  const f = parsearFecha_(d.fecha, "fecha");
  const cal = d.calendario ? CalendarApp.getCalendarById(d.calendario) : CalendarApp.getDefaultCalendar();
  if (!cal) throw new ParametroInvalido("calendario inexistente: " + d.calendario);
  const opciones = { description: d.descripcion || "" };

  if (!d.hora_inicio) {
    if (d.hora_fin) throw new ParametroInvalido("hora_fin sin hora_inicio");
    const ev = cal.createAllDayEvent(titulo, new Date(f.anio, f.mes - 1, f.dia), opciones);
    return { id: ev.getId(), calendario_id: cal.getId(), todo_el_dia: true, inicio: d.fecha, fin: d.fecha };
  }

  const hi = parsearHora_(d.hora_inicio, "hora_inicio");
  const inicio = new Date(f.anio, f.mes - 1, f.dia, hi.h, hi.m);
  let fin;
  if (d.hora_fin) {
    const hf = parsearHora_(d.hora_fin, "hora_fin");
    fin = new Date(f.anio, f.mes - 1, f.dia, hf.h, hf.m);
    if (fin <= inicio) throw new ParametroInvalido("hora_fin tiene que ser posterior a hora_inicio");
  } else {
    fin = new Date(inicio.getTime() + 60 * 60 * 1000);
  }

  const ev = cal.createEvent(titulo, inicio, fin, opciones);
  return {
    id: ev.getId(),
    calendario_id: cal.getId(),
    todo_el_dia: false,
    inicio: formatearInstante_(inicio),
    fin: formatearInstante_(fin)
  };
}

function crearTarea_(d) {
  const tarea = { title: requerirTexto_(d.titulo, "titulo"), notes: d.descripcion || "" };
  if (d.fecha) {
    parsearFecha_(d.fecha, "fecha");
    // Google Tasks guarda solo la fecha: descarta la parte horaria.
    tarea.due = d.fecha + "T00:00:00.000Z";
  }
  const lista = d.lista || "@default";
  const creada = Tasks.Tasks.insert(tarea, lista);
  return { id: creada.id, lista_id: lista, titulo: creada.title, vence: d.fecha || null };
}

function completarTarea_(d) {
  const lista = requerirTexto_(d.lista_id, "lista_id");
  const id = requerirTexto_(d.tarea_id, "tarea_id");
  const t = Tasks.Tasks.patch({ status: "completed" }, lista, id);
  return { id: t.id, lista_id: lista, estado: t.status };
}


// --- Acciones de lectura (para el dashboard) --------------------------------

function listarCalendarios_() {
  const principal = CalendarApp.getDefaultCalendar().getId();
  const calendarios = CalendarApp.getAllCalendars().map(function (c) {
    return {
      id: c.getId(),
      nombre: c.getName(),
      color: c.getColor(),
      principal: c.getId() === principal,
      oculto: c.isHidden(),
      seleccionado: c.isSelected()
    };
  });
  return { calendarios: calendarios };
}

/**
 * Eventos entre `desde` y `hasta` (ambos inclusive, YYYY-MM-DD).
 * Calendarios: los ids de `calendarios`; si no vienen, la propiedad
 * CALENDARIOS; si tampoco, los que están tildados y visibles en Calendar.
 */
function listarEventos_(d) {
  const desde = parsearFecha_(d.desde, "desde");
  const hasta = parsearFecha_(d.hasta, "hasta");
  const inicio = new Date(desde.anio, desde.mes - 1, desde.dia);
  const finExclusivo = new Date(hasta.anio, hasta.mes - 1, hasta.dia + 1);
  if (finExclusivo <= inicio) throw new ParametroInvalido("hasta es anterior a desde");
  if ((finExclusivo - inicio) / 86400000 > MAX_DIAS_LISTADO) {
    throw new ParametroInvalido("rango mayor a " + MAX_DIAS_LISTADO + " días");
  }

  const calendarios = calendariosAListar_(d.calendarios);
  const eventos = [];
  calendarios.forEach(function (cal) {
    cal.getEvents(inicio, finExclusivo).forEach(function (ev) {
      const todoElDia = ev.isAllDayEvent();
      let ini, fin;
      if (todoElDia) {
        ini = formatearFecha_(ev.getAllDayStartDate());
        // getAllDayEndDate es exclusivo (el día siguiente al último): se
        // devuelve el último día, inclusive, que es lo que se muestra.
        fin = formatearFecha_(new Date(ev.getAllDayEndDate().getTime() - 86400000));
      } else {
        ini = formatearInstante_(ev.getStartTime());
        fin = formatearInstante_(ev.getEndTime());
      }
      eventos.push({
        id: ev.getId(),
        calendario_id: cal.getId(),
        calendario: cal.getName(),
        color: cal.getColor(),
        titulo: ev.getTitle(),
        descripcion: ev.getDescription(),
        ubicacion: ev.getLocation(),
        todo_el_dia: todoElDia,
        inicio: ini,
        fin: fin
      });
    });
  });

  // Orden: por inicio; los de todo el día primero dentro de cada fecha.
  eventos.sort(function (a, b) {
    const ka = a.inicio.slice(0, 10) + (a.todo_el_dia ? "0" : "1" + a.inicio);
    const kb = b.inicio.slice(0, 10) + (b.todo_el_dia ? "0" : "1" + b.inicio);
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });
  return { desde: d.desde, hasta: d.hasta, eventos: eventos };
}

/**
 * Tareas de todas las listas (o de los ids en `listas`). Por defecto solo las
 * pendientes; `incluir_completadas: true` trae también las hechas.
 */
function listarTareas_(d) {
  const todas = paginar_(function (pageToken) {
    return Tasks.Tasklists.list({ maxResults: 100, pageToken: pageToken });
  });
  const listas = d.listas && d.listas.length
    ? todas.filter(function (l) { return d.listas.indexOf(l.id) !== -1; })
    : todas;

  const tareas = [];
  listas.forEach(function (l) {
    const items = paginar_(function (pageToken) {
      return Tasks.Tasks.list(l.id, {
        maxResults: 100,
        pageToken: pageToken,
        showCompleted: d.incluir_completadas === true,
        showHidden: d.incluir_completadas === true
      });
    });
    items.forEach(function (t) {
      if (!t.title) return; // Tasks devuelve renglones vacíos al final de la lista
      tareas.push({
        id: t.id,
        lista_id: l.id,
        lista: l.title,
        titulo: t.title,
        notas: t.notes || "",
        vence: t.due ? t.due.slice(0, 10) : null,
        estado: t.status,
        padre: t.parent || null,
        actualizada: t.updated
      });
    });
  });

  // Primero las que vencen (más próximas arriba), después las sin fecha.
  tareas.sort(function (a, b) {
    const ka = a.vence || "9999-99-99";
    const kb = b.vence || "9999-99-99";
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });
  return { listas: listas.map(function (l) { return { id: l.id, nombre: l.title }; }), tareas: tareas };
}


/**
 * Eventos + tareas pendientes en una sola llamada: cada llamada a la web app
 * cuesta 1-3 s más el salto del 302, y el dashboard necesita las dos cosas.
 * `desde`/`hasta` opcionales: por defecto hoy y los 6 días siguientes.
 */
function resumenSemana_(d) {
  const hoy = new Date();
  const desde = d.desde || formatearFecha_(hoy);
  const hasta = d.hasta || formatearFecha_(new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() + 6));
  const ev = listarEventos_({ desde: desde, hasta: hasta, calendarios: d.calendarios });
  const ta = listarTareas_({ listas: d.listas });
  return { desde: desde, hasta: hasta, eventos: ev.eventos, listas: ta.listas, tareas: ta.tareas };
}


// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

function ParametroInvalido(mensaje) {
  this.name = "ParametroInvalido";
  this.message = mensaje;
}
ParametroInvalido.prototype = Object.create(Error.prototype);

function respuestaJson_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function requerirPropiedad_(props, nombre) {
  const v = props.getProperty(nombre);
  if (!v) throw new Error("Falta la propiedad del script " + nombre);
  return v;
}

function requerirTexto_(v, campo) {
  const s = v == null ? "" : String(v).trim();
  if (!s) throw new ParametroInvalido("falta " + campo);
  return s;
}

/** YYYY-MM-DD válida de verdad (rechaza 2026-02-31). */
function parsearFecha_(v, campo) {
  const m = RE_FECHA.exec(String(v || ""));
  if (!m) throw new ParametroInvalido(campo + " tiene que ser YYYY-MM-DD");
  const anio = Number(m[1]), mes = Number(m[2]), dia = Number(m[3]);
  const d = new Date(anio, mes - 1, dia);
  if (d.getFullYear() !== anio || d.getMonth() !== mes - 1 || d.getDate() !== dia) {
    throw new ParametroInvalido(campo + " no es una fecha real: " + v);
  }
  return { anio: anio, mes: mes, dia: dia };
}

function parsearHora_(v, campo) {
  const m = RE_HORA.exec(String(v || ""));
  if (!m) throw new ParametroInvalido(campo + " tiene que ser HH:MM");
  return { h: Number(m[1]), m: Number(m[2]) };
}

function formatearFecha_(d) {
  return Utilities.formatDate(d, Session.getScriptTimeZone(), "yyyy-MM-dd");
}

function formatearInstante_(d) {
  return Utilities.formatDate(d, Session.getScriptTimeZone(), "yyyy-MM-dd'T'HH:mm:ssXXX");
}

function calendariosAListar_(ids) {
  let lista = ids && ids.length ? ids : null;
  if (!lista) {
    const prop = PropertiesService.getScriptProperties().getProperty("CALENDARIOS");
    if (prop) lista = prop.split(",").map(function (s) { return s.trim(); }).filter(String);
  }
  if (lista) {
    return lista.map(function (id) {
      const c = CalendarApp.getCalendarById(id);
      if (!c) throw new ParametroInvalido("calendario inexistente: " + id);
      return c;
    });
  }
  return CalendarApp.getAllCalendars().filter(function (c) { return c.isSelected() && !c.isHidden(); });
}

function paginar_(pedir) {
  const items = [];
  let pageToken;
  do {
    const r = pedir(pageToken);
    (r.items || []).forEach(function (i) { items.push(i); });
    pageToken = r.nextPageToken;
  } while (pageToken);
  return items;
}

/** Comparación sin cortocircuito, para no filtrar el secreto por tiempos. */
function iguales_(a, b) {
  if (a.length !== b.length) return false;
  let dif = 0;
  for (let i = 0; i < a.length; i++) dif |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return dif === 0;
}


// ---------------------------------------------------------------------------
// Instalación y pruebas manuales (se corren a mano desde el editor)
// ---------------------------------------------------------------------------

/** Deja un único disparador cada 10 minutos para el briefing. */
function instalarDisparadores() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === "reenviarBriefingAWhatsApp") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("reenviarBriefingAWhatsApp").timeBased().everyMinutes(10).create();
  console.log("Disparador instalado: reenviarBriefingAWhatsApp cada 10 minutos.");
}

/** Muestra en el registro lo que vería el dashboard, sin pasar por la web. */
function probarLecturas() {
  const hoy = new Date();
  const enSiete = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() + 6);
  console.log(JSON.stringify(listarCalendarios_(), null, 2));
  console.log(JSON.stringify(listarEventos_({ desde: formatearFecha_(hoy), hasta: formatearFecha_(enSiete) }), null, 2));
  console.log(JSON.stringify(listarTareas_({}), null, 2));
}

/** Prueba el acortador con un texto de ejemplo. */
function probarAcortador() {
  console.log(acortarUrls("Nota: https://www.example.com/una/ruta/bastante/larga/para/probar?x=1. Corto: https://g.co/a"));
}
