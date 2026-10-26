"""Web vitals por CDP con Chrome headless (perfil nuevo por corrida = caché fría).

Uso: python medir_frontend.py <url_base_con_token> <salida.json>
Perfiles: "desktop" (sin throttling) y "movil_lighthouse" (4x CPU, 150 ms RTT,
1,6 Mbps de bajada: lo mismo que simula Lighthouse para mobile).
"""
import asyncio
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE, SALIDA = sys.argv[1], sys.argv[2]
SOLO = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "todos" else None
SOLO_PAGINA = sys.argv[4] if len(sys.argv) > 4 else None
TOKEN = BASE.split("?s=")[1]
ORIGEN = BASE.split("/?")[0]
PAGINAS = {"inicio": f"{ORIGEN}/?s={TOKEN}", "finanzas": f"{ORIGEN}/finanzas?s={TOKEN}"}
PERFILES = {
    "desktop": None,
    "movil_lighthouse": {"cpu": 4, "latency": 150, "down": 1.6 * 1024 * 1024 / 8, "up": 750 * 1024 / 8},
}
ESPERA_S = 14

OBSERVADOR = r"""
window.__m = {mut: 0, n: 0};
new MutationObserver(() => { window.__m.mut = performance.now(); window.__m.n++; })
  .observe(document, {subtree: true, childList: true, characterData: true});
window.__lt = [];
new PerformanceObserver(l => window.__lt.push(...l.getEntries().map(e => [e.startTime, e.duration])))
  .observe({type: 'longtask', buffered: true});
window.__lcp = [];
new PerformanceObserver(l => window.__lcp.push(...l.getEntries().map(e => [e.startTime, (e.element && e.element.tagName) || '', ((e.element && e.element.textContent) || '').slice(0, 40)])))
  .observe({type: 'largest-contentful-paint', buffered: true});
window.__cls = 0;
new PerformanceObserver(l => l.getEntries().forEach(e => { if (!e.hadRecentInput) window.__cls += e.value; }))
  .observe({type: 'layout-shift', buffered: true});
"""

LEER = r"""(() => {
  const nav = performance.getEntriesByType('navigation')[0];
  const paint = Object.fromEntries(performance.getEntriesByType('paint').map(p => [p.name, p.startTime]));
  const fcp = paint['first-contentful-paint'] || 0;
  const lcp = window.__lcp[window.__lcp.length - 1] || [null, '', ''];
  const res = performance.getEntriesByType('resource');
  return JSON.stringify({
    ttfb: nav.responseStart, dcl: nav.domContentLoadedEventEnd, load: nav.loadEventEnd,
    fcp: fcp, lcp: lcp[0], lcp_elemento: lcp[1] + ' ' + lcp[2],
    cls: window.__cls,
    tbt: window.__lt.filter(t => t[0] >= fcp).reduce((s, t) => s + Math.max(0, t[1] - 50), 0),
    longtasks: window.__lt.length, longtask_max: Math.max(0, ...window.__lt.map(t => t[1])),
    contenido_estable: window.__m.mut, mutaciones: window.__m.n,
    requests: res.length + 1,
    nodos_dom: document.getElementsByTagName('*').length,
    // ¿Es la pantalla que se quería medir? (26/10/2026: con el token de sesión
    // vencido se midió dos veces la pantalla de login sin darse cuenta.)
    es_inicio: document.body.innerText.toLowerCase().includes('saldo de la cuenta'),
    es_finanzas: document.querySelectorAll('[role="tab"]').length >= 5,
    recursos: res.map(r => [r.name.replace(location.origin, ''), r.initiatorType, r.transferSize, r.decodedBodySize, r.duration]),
  });
})()"""


class CDP:
    def __init__(self, ws):
        self.ws, self.i, self.eventos = ws, 0, []

    async def send(self, metodo, **params):
        self.i += 1
        mid = self.i
        await self.ws.send(json.dumps({"id": mid, "method": metodo, "params": params}))
        while True:
            m = json.loads(await self.ws.recv())
            if m.get("id") == mid:
                return m.get("result", m.get("error"))
            self.eventos.append(m)

    async def drenar(self, segundos):
        fin = time.time() + segundos
        while time.time() < fin:
            try:
                m = await asyncio.wait_for(self.ws.recv(), timeout=max(0.05, fin - time.time()))
            except asyncio.TimeoutError:
                break
            if m is None:
                break
            self.eventos.append(json.loads(m))


async def una_corrida(pagina, perfil):
    perfil_dir = tempfile.mkdtemp()
    puerto = 9333
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={puerto}",
                             f"--user-data-dir={perfil_dir}", "--no-first-run",
                             "--no-default-browser-check", "--window-size=1350,940", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json").read())
                ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
                break
            except Exception:  # noqa: BLE001
                await asyncio.sleep(0.2)
        ws = await websockets.connect(ws_url, max_size=None)
        c = CDP(ws)
        await c.send("Network.enable")
        await c.send("Page.enable")
        await c.send("Network.setCacheDisabled", cacheDisabled=False)
        if perfil:
            await c.send("Emulation.setCPUThrottlingRate", rate=perfil["cpu"])
            await c.send("Network.emulateNetworkConditions", offline=False, latency=perfil["latency"],
                         downloadThroughput=perfil["down"], uploadThroughput=perfil["up"])
        await c.send("Page.addScriptToEvaluateOnNewDocument", source=OBSERVADOR)
        await c.send("Page.navigate", url=PAGINAS[pagina])
        await c.drenar(ESPERA_S if not perfil else 90)
        r = await c.send("Runtime.evaluate", expression=LEER, returnByValue=True)
        datos = json.loads(r["result"]["value"])
        if not datos["es_" + pagina]:
            raise RuntimeError(f"{pagina}: la página no es la esperada (¿login? ¿token vencido?)")
        # Bytes reales por la red (incluye el documento) y frames del websocket
        recibidos = sum(e["params"].get("encodedDataLength", 0) for e in c.eventos
                        if e.get("method") == "Network.loadingFinished")
        frames = [e for e in c.eventos if e.get("method") == "Network.webSocketFrameReceived"]
        ws_bytes = sum(len(f["params"]["response"]["payloadData"]) * (3 / 4 if f["params"]["response"]["opcode"] == 2 else 1)
                       for f in frames)
        datos["red_kb_total"] = round(recibidos / 1024, 1)
        datos["ws_frames"] = len(frames)
        datos["ws_kb_recibidos"] = round(ws_bytes / 1024, 1)
        await c.send("Page.navigate", url="about:blank")
        await c.drenar(1.5)
        await ws.close()
        return datos
    finally:
        proc.kill()
        proc.wait()
        time.sleep(0.5)
        shutil.rmtree(perfil_dir, ignore_errors=True)


async def main():
    out = {}
    for perfil_nombre, perfil in PERFILES.items():
        if SOLO and perfil_nombre != SOLO:
            continue
        for pagina in PAGINAS:
            if SOLO_PAGINA and pagina != SOLO_PAGINA:
                continue
            corridas = []
            for _ in range(3):
                corridas.append(await una_corrida(pagina, perfil))
            med = {}
            for k in ("ttfb", "fcp", "lcp", "cls", "tbt", "longtasks", "longtask_max", "contenido_estable",
                      "requests", "red_kb_total", "ws_frames", "ws_kb_recibidos", "nodos_dom", "dcl"):
                vals = [x[k] for x in corridas if x.get(k) is not None]
                med[k] = round(statistics.median(vals), 3 if k == "cls" else 1) if vals else None
            med["lcp_elemento"] = corridas[-1]["lcp_elemento"]
            rec = corridas[-1]["recursos"]
            med["js_kb_transfer"] = round(sum(r[2] for r in rec if r[1] == "script") / 1024, 1)
            med["js_kb_decodificado"] = round(sum(r[3] for r in rec if r[1] == "script") / 1024, 1)
            med["css_kb_transfer"] = round(sum(r[2] for r in rec if r[0].endswith(".css") or "css2?" in r[0]) / 1024, 1)
            med["fuentes_kb_transfer"] = round(sum(r[2] for r in rec if any(x in r[0] for x in (".woff", ".ttf", "gstatic"))) / 1024, 1)
            med["externos"] = sorted({r[0].split("/")[2] for r in rec if r[0].startswith("http")})
            med["top_recursos"] = [[r[0][:70], round(r[2] / 1024, 1), round(r[4])] for r in sorted(rec, key=lambda r: -r[2])[:8]]
            med["corridas"] = [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in x.items() if k != "recursos"} for x in corridas]
            out[f"{perfil_nombre}/{pagina}"] = med
            print(perfil_nombre, pagina, json.dumps({k: v for k, v in med.items() if k not in ("corridas", "top_recursos")}, ensure_ascii=False))
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)


asyncio.run(main())
