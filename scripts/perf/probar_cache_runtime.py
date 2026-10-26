"""Prueba en el runtime real: la caché no muestra números viejos.

Uso: python probar_cache_runtime.py <url_con_token> <base.db_que_usa_la_app> <repo>
Abre el Inicio, escribe un gasto desde **otro proceso** (como el bot), recarga y
compara "Gastos del mes". Recargar abre otra sesión, y la caché de Streamlit es
de todo el proceso: si la invalidación fallara, se vería el número viejo.
"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probar_runtime import CHROME, CDP  # noqa: E402

import json  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import urllib.request  # noqa: E402

import websockets  # noqa: E402

URL, DB, REPO = sys.argv[1], sys.argv[2], sys.argv[3]
LEER = r"""(() => {
  const t = document.body.innerText.split(String.fromCharCode(10)).map(x => x.trim()).filter(Boolean);
  const i = t.findIndex(x => x.toLowerCase().startsWith('gastos de'));
  return i < 0 ? 'sin métrica' : t.slice(i, i + 2).join(' ');
})()"""


def gasto_desde_otro_proceso(monto: int) -> None:
    codigo = (
        "import sys, datetime\n"
        f"sys.path.insert(0, {REPO!r})\n"
        "from core import db as core_db\n"
        "from core.context import set_current_user_id\n"
        "from core.db import connect\n"
        "from places.finanzas.core.transactions import insertar_sin_backup\n"
        "set_current_user_id(1)\n"
        "with connect() as c:\n"
        f"    insertar_sin_backup(c, datetime.date.today(), 'Compras', pasivos={monto}, user_id=1)\n"
    )
    subprocess.run([sys.executable, "-c", codigo], cwd=REPO, check=True, env={**os.environ, "DB_PATH": DB})


async def main():
    perfil = tempfile.mkdtemp()
    proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9336", f"--user-data-dir={perfil}",
                             "--no-first-run", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9336/json").read())
                ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
                break
            except Exception:  # noqa: BLE001
                await asyncio.sleep(0.2)
        ws = await websockets.connect(ws_url, max_size=None)
        c = CDP(ws)
        await c.send("Page.enable")
        await c.send("Page.navigate", url=URL)
        await c.drenar(10)
        print("antes:   ", await c.js(LEER))
        await c.send("Page.navigate", url=URL)
        await c.drenar(8)
        print("recarga sin cambios:", await c.js(LEER))
        gasto_desde_otro_proceso(50_000)
        await c.send("Page.navigate", url=URL)
        await c.drenar(8)
        print("después de un gasto de $50.000 desde otro proceso:", await c.js(LEER))
        await c.send("Page.navigate", url="about:blank")
        await c.drenar(1.5)
        await ws.close()
    finally:
        proc.kill()
        proc.wait()
        time.sleep(0.5)
        shutil.rmtree(perfil, ignore_errors=True)


asyncio.run(main())
