"""Qué mueve el layout (CLS) al cargar: cada layout-shift con los nodos que se corrieron.

Uso: python probar_cls.py <url_con_token>
Perfil nuevo (caché fría). Imprime cada corrimiento con su momento, su valor y
los elementos que se movieron (con el `data-testid` de Streamlit más cercano),
y cuándo terminó de cargar cada fuente: si los corrimientos caen justo cuando
llega una fuente, la culpa es de la fuente; si no, de lo que va apareciendo.
"""
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probar_runtime import CHROME, CDP  # noqa: E402

import websockets  # noqa: E402

URL = sys.argv[1]

OBSERVADOR = r"""
window.__ls = [];
new PerformanceObserver(l => l.getEntries().forEach(e => {
  if (e.hadRecentInput) return;
  window.__ls.push({t: Math.round(e.startTime), v: +e.value.toFixed(4),
    nodos: (e.sources || []).map(s => { const n = s.node; if (!n || !n.closest) return '?';
      const tid = n.closest('[data-testid]'); return (n.tagName || '#') + '[' + (tid ? tid.dataset.testid : '') + '] '
        + (n.textContent || '').trim().slice(0, 30) + ' dy=' + Math.round(s.currentRect.y - s.previousRect.y)
        + ' dh=' + Math.round(s.currentRect.height - s.previousRect.height); })});
})).observe({type: 'layout-shift', buffered: true});
"""
LEER = r"""JSON.stringify({ls: window.__ls,
  fuentes: performance.getEntriesByType('resource').filter(r => /woff2?|fonts\.g|\.css/.test(r.name))
    .map(r => [r.name.split('/').pop().split('?')[0].slice(0, 40), Math.round(r.responseEnd)])})"""


async def main():
    perfil = tempfile.mkdtemp()
    proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9338", f"--user-data-dir={perfil}",
                             "--no-first-run", "--window-size=1350,940", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9338/json").read())
                ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
                break
            except Exception:  # noqa: BLE001
                await asyncio.sleep(0.2)
        ws = await websockets.connect(ws_url, max_size=None)
        c = CDP(ws)
        await c.send("Page.enable")
        await c.send("Page.addScriptToEvaluateOnNewDocument", source=OBSERVADOR)
        await c.send("Page.navigate", url=URL)
        await c.drenar(12)
        d = json.loads(await c.js(LEER))
        print("CLS total:", round(sum(x["v"] for x in d["ls"]), 4))
        for x in d["ls"]:
            print(f"  {x['t']:>6} ms  {x['v']:.4f}  {x['nodos'][:3]}")
        print("fuentes/css (fin de descarga, ms):", d["fuentes"])
        await c.send("Page.navigate", url="about:blank")
        await c.drenar(1.5)
        await ws.close()
    finally:
        proc.kill()
        proc.wait()
        time.sleep(0.5)
        shutil.rmtree(perfil, ignore_errors=True)


asyncio.run(main())
