"""Prueba en el runtime real (Chrome por CDP): fragmentos, pestañas y Excel diferido.

Uso: python probar_runtime.py <url_con_token>
No guarda nada en disco: la descarga se deniega y el tamaño se lee con fetch.
"""
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = sys.argv[1].replace("/?s=", "/finanzas?s=") if len(sys.argv) > 1 else ""


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

    async def drenar(self, s):
        fin = time.time() + s
        while time.time() < fin:
            try:
                m = await asyncio.wait_for(self.ws.recv(), timeout=max(0.05, fin - time.time()))
            except asyncio.TimeoutError:
                break
            self.eventos.append(json.loads(m))

    async def js(self, expr):
        r = await self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value", r)

    def frames_desde(self, n):
        return [e for e in self.eventos[n:] if e.get("method") == "Network.webSocketFrameReceived"]


CLICK_TEXTO = """((sel, txt) => {
  const el = [...document.querySelectorAll(sel)].find(e => e.innerText.trim() === txt);
  if (!el) return 'no encontrado: ' + txt;
  el.click(); return 'ok';
})"""


async def main():
    perfil = tempfile.mkdtemp()
    proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9334", f"--user-data-dir={perfil}",
                             "--no-first-run", "--window-size=1350,940", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9334/json").read())
                ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
                break
            except Exception:  # noqa: BLE001
                await asyncio.sleep(0.2)
        ws = await websockets.connect(ws_url, max_size=None)
        c = CDP(ws)
        await c.send("Network.enable")
        await c.send("Page.enable")
        await c.send("Browser.setDownloadBehavior", behavior="deny")
        await c.send("Page.navigate", url=URL)
        await c.drenar(12)
        print("carga: frames", len(c.frames_desde(0)))

        # 1) "Agrupar por" → Subcategoría (fragmento sin base)
        n = len(c.eventos)
        print("agrupar:", await c.js(CLICK_TEXTO + "('button', 'Subcategoría')"))
        await c.drenar(4)
        print("  frames", len(c.frames_desde(n)))

        # 2) Medias móviles: abrir "Ajustes" y sacar el chip de 90 (fragmento que lee la base)
        async def click_en(expr_rect):
            r = await c.js(expr_rect)
            if not isinstance(r, dict):
                return r
            for t in ("mousePressed", "mouseReleased"):
                await c.send("Input.dispatchMouseEvent", type=t, x=r["x"], y=r["y"], button="left", clickCount=1)
            return "ok"
        rect = """(f => { const el = f(); if (!el) return 'no está';
            el.scrollIntoView({block: 'center'}); const r = el.getBoundingClientRect();
            return {x: r.x + r.width / 2, y: r.y + r.height / 2}; })"""
        print("ajustes:", await click_en(rect + "(() => [...document.querySelectorAll('button')].find(b => b.innerText.includes('Ajustes')))"))
        await c.drenar(1.5)
        n = len(c.eventos)
        print("media 90 fuera:", await click_en(rect + """(() => {
            const chip = [...document.querySelectorAll('[data-baseweb="tag"]')].find(t => t.innerText.trim().startsWith('90'));
            return chip && chip.querySelector('[role="presentation"]'); })"""))
        await c.drenar(4)
        print("  frames", len(c.frames_desde(n)))
        print("  chips ahora:", await c.js("[...document.querySelectorAll('[data-baseweb=tag]')].map(t=>t.innerText.trim()).join('|')"))
        print("  leyenda del gráfico:", await c.js("[...document.querySelectorAll('.legendtext')].map(t=>t.textContent).slice(0,4).join('|')"))
        await c.send("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        await c.drenar(1)

        # 3) Pestaña Configuración y descarga del Excel
        n = len(c.eventos)
        print("pestaña:", await c.js(CLICK_TEXTO + "('[role=\"tab\"]', 'settingsConfiguración')") )
        await c.drenar(1)
        txt_tabs = await c.js("[...document.querySelectorAll('[role=\"tab\"]')].map(t=>t.innerText.trim()).join('|')")
        print("  tabs:", txt_tabs)
        if "ok" != await c.js(CLICK_TEXTO + "('[role=\"tab\"]', 'settingsConfiguración')"):
            print("  click por índice:", await c.js("(() => { const t = document.querySelectorAll('[role=\"tab\"]')[4]; t.click(); return t.innerText; })()"))
        await c.drenar(5)
        print("  frames", len(c.frames_desde(n)), "| subtítulos:",
              await c.js("[...document.querySelectorAll('h3')].map(h=>h.innerText.trim()).slice(0,4).join('|')"))
        n = len(c.eventos)
        print("descargar:", await c.js(CLICK_TEXTO + "('button', '📥 Descargar snapshot Excel')"))
        await c.drenar(8)
        media = [e for e in c.eventos[n:] if e.get("method") == "Network.responseReceived"
                 and "/media/" in e["params"]["response"]["url"]]
        for e in media:
            r = e["params"]["response"]
            print("  respuesta", r["status"], r["mimeType"], r["url"].split("/")[-1][:60])
            largo = await c.js(f"fetch({json.dumps(r['url'])}).then(x => x.arrayBuffer()).then(b => b.byteLength)")
            print("  bytes por fetch:", largo)
        if not media:
            otros = [e["params"]["request"]["url"][-60:] for e in c.eventos[n:] if e.get("method") == "Network.requestWillBeSent"]
            print("  sin /media/. requests:", otros[:6])
        await c.send("Page.navigate", url="about:blank")
        await c.drenar(1.5)
        await ws.close()
    finally:
        proc.kill()
        proc.wait()
        time.sleep(0.5)
        shutil.rmtree(perfil, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
