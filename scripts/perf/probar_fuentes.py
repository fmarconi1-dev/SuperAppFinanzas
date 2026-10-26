"""Qué fuentes baja la app y con cuál se dibuja cada cosa (Chrome por CDP).

Uso: python probar_fuentes.py <url_con_token> <salida.png>
Perfil nuevo (caché fría). Lista los archivos de fuentes bajados, las fuentes
que el navegador terminó usando y la familia calculada de cada elemento clave,
y saca una captura para mirarla.
"""
import asyncio
import base64
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

URL, PNG = sys.argv[1], sys.argv[2]

LEER = r"""(async () => {
  await document.fonts.ready;
  const fam = sel => { const e = document.querySelector(sel); return e ? getComputedStyle(e).fontFamily.slice(0, 50) : '—'; };
  const res = performance.getEntriesByType('resource')
    .filter(r => /woff2?|ttf|fonts\.g/.test(r.name))
    .map(r => [r.name.replace(location.origin, '').split('?')[0].slice(-55), Math.round(r.decodedBodySize / 1024)]);
  const cargadas = [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/"/g, '') + ' ' + f.weight);
  return JSON.stringify({
    archivos: res, kb: res.reduce((s, r) => s + r[1], 0),
    usadas: [...new Set(cargadas)].sort(),
    h1: fam('h1'), texto: fam('[data-testid="stMarkdownContainer"] p'),
    metrica: fam('[data-testid="stMetricValue"]'), boton: fam('button'),
    // Elementos con texto visible cuya fuente efectiva es Source Sans (la de Streamlit)
    con_source_sans: [...document.querySelectorAll('body *')].filter(e =>
        e.childNodes.length && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())
        && getComputedStyle(e).fontFamily.replace(/"/g, '').trim().startsWith('Source Sans'))
      .slice(0, 8).map(e => e.tagName + '[' + (e.closest('[data-testid]')?.dataset.testid || '') + '] ' + e.textContent.trim().slice(0, 25)),
  });
})()"""


async def main():
    perfil = tempfile.mkdtemp()
    proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9337", f"--user-data-dir={perfil}",
                             "--no-first-run", "--window-size=1350,940", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9337/json").read())
                ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
                break
            except Exception:  # noqa: BLE001
                await asyncio.sleep(0.2)
        ws = await websockets.connect(ws_url, max_size=None)
        c = CDP(ws)
        await c.send("Page.enable")
        await c.send("Page.navigate", url=URL)
        await c.drenar(12)
        print(json.dumps(json.loads(await c.js(LEER)), ensure_ascii=False, indent=1))
        foto = await c.send("Page.captureScreenshot", format="png")
        Path(PNG).write_bytes(base64.b64decode(foto["data"]))
        await c.send("Page.navigate", url="about:blank")
        await c.drenar(1.5)
        await ws.close()
    finally:
        proc.kill()
        proc.wait()
        time.sleep(0.5)
        shutil.rmtree(perfil, ignore_errors=True)


asyncio.run(main())
