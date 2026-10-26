"""Arranque en frío: cada escenario en un proceso de Python nuevo, como después
de que Fly apaga la máquina (`min_machines_running = 0`).

Uso: python medir_arranque.py <repo_A> <repo_B> <base.db> <salida.json> [corridas]
Corre A y B intercalados (A, B, A, B…) para que la carga de la PC afecte a los
dos por igual. Mide sobre copias de la base; no toca el original.
"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

A, B, BASE, SALIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
N = int(sys.argv[5]) if len(sys.argv) > 5 else 5

# Cada escenario imprime una línea JSON con sus tiempos en ms. El tiempo de
# arrancar el intérprete y de importar Streamlit es igual en A y B: no se cuenta.
ESCENARIOS = {
    "api_import": """
import time; t = time.perf_counter()
import api
print(json.dumps({"ms": (time.perf_counter() - t) * 1000}))
""",
    "bot_primer_gasto": """
import time; t = time.perf_counter()
import api
from places.finanzas.core.comandos import procesar
t1 = time.perf_counter()
r = procesar(connect(), "3500, Compras", user_id=1)
fin = time.perf_counter()
# Un gasto de verdad (hasta el 26/10/2026 mandaba "café 3500", que el bot rechaza:
# medía un mensaje rechazado). Si no se cargó, la medición no vale.
assert "Cargado" in r.texto, r.texto
print(json.dumps({"ms": (fin - t) * 1000, "solo_mensaje_ms": (fin - t1) * 1000}))
""",
    "bot_primer_resumen": """
import time; t = time.perf_counter()
import api
from places.finanzas.core.comandos import procesar
t1 = time.perf_counter()
r = procesar(connect(), "resumen", user_id=1)
fin = time.perf_counter()
assert "Gastos" in r.texto or "gastos" in r.texto, r.texto
print(json.dumps({"ms": (fin - t) * 1000, "solo_mensaje_ms": (fin - t1) * 1000}))
""",
    "app_primer_inicio": """
from streamlit.testing.v1 import AppTest
import time
at = AppTest.from_file("app.py", default_timeout=120)
at.session_state["logged_in"] = True; at.session_state["current_user_id"] = 1
at.session_state["current_username"] = "franco"; at.session_state["current_user_fullname"] = "Franco"
t = time.perf_counter(); at.run()
assert not at.exception, [e.value for e in at.exception]
print(json.dumps({"ms": (time.perf_counter() - t) * 1000}))
""",
    "app_primer_finanzas": """
from streamlit.testing.v1 import AppTest
import time
def pantalla():
    import streamlit as st
    from core import workspaces_ui
    from core.context import set_current_user_id
    from core.db import connect
    from places.finanzas import home
    set_current_user_id(1)
    with connect() as c:
        workspaces_ui.activar_desde_sesion(c)
    home.render()
at = AppTest.from_function(pantalla, default_timeout=120)
at.session_state["logged_in"] = True; at.session_state["current_user_id"] = 1
t = time.perf_counter(); at.run()
assert not at.exception, [e.value for e in at.exception]
print(json.dumps({"ms": (time.perf_counter() - t) * 1000}))
""",
}

PREAMBULO = """
import json, logging, os, sys
logging.disable(logging.WARNING)
sys.path.insert(0, os.getcwd())
from core import db as core_db
core_db.BACKUP_DIR = __import__("pathlib").Path(os.environ["DB_PATH"]).parent / "backups"
from core.db import connect
from core.context import set_current_user_id
set_current_user_id(1)
"""


def correr(repo: Path, codigo: str) -> dict:
    tmp = Path(tempfile.mkdtemp())
    for suf in ("", "-wal", "-shm"):
        if Path(str(BASE) + suf).exists():
            shutil.copy(str(BASE) + suf, str(tmp / "b.db") + suf)
    env = {**os.environ, "DB_PATH": str(tmp / "b.db"), "PYTHONIOENCODING": "utf-8"}
    for k in ("APPS_SCRIPT_URL", "GEMINI_API_KEY", "SESSION_SECRET", "WHATSAPP_TOKEN"):
        env.pop(k, None)
    # A un archivo y no `-c`: AppTest.from_function necesita leer el código fuente.
    script = tmp / "escenario.py"
    script.write_text(PREAMBULO + codigo, encoding="utf-8")
    r = subprocess.run([sys.executable, str(script)], cwd=repo, env=env,
                       capture_output=True, text=True, timeout=300)
    shutil.rmtree(tmp, ignore_errors=True)
    lineas = [l for l in r.stdout.splitlines() if l.startswith("{")]
    if r.returncode or not lineas:
        raise RuntimeError(f"{repo.name}: {r.stderr[-800:]}")
    return json.loads(lineas[-1])


out = {}
for nombre, codigo in ESCENARIOS.items():
    res = {"A": [], "B": []}
    for _ in range(N):
        for lado, repo in (("A", A), ("B", B)):
            res[lado].append(correr(repo, codigo))
    fila = {}
    for lado in ("A", "B"):
        for k in res[lado][0]:
            fila[f"{lado}_{k}_mediana"] = round(statistics.median(x[k] for x in res[lado]), 1)
        fila[f"{lado}_ms_todas"] = [round(x["ms"]) for x in res[lado]]
    fila["delta_pct"] = round((fila["B_ms_mediana"] / fila["A_ms_mediana"] - 1) * 100, 1)
    out[nombre] = fila
    print(nombre, json.dumps(fila, ensure_ascii=False), flush=True)
SALIDA.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
