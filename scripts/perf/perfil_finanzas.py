"""Dónde se va el tiempo de un render de Finanzas (cProfile, modo bare)."""
import cProfile
import os
import pstats
import shutil
import sys
import tempfile
from pathlib import Path

REPO, BASE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(REPO))
os.chdir(REPO)
tmp = Path(tempfile.mkdtemp())
for suf in ("", "-wal", "-shm"):
    if Path(str(BASE) + suf).exists():
        shutil.copy(str(BASE) + suf, str(tmp / "b.db") + suf)
os.environ["DB_PATH"] = str(tmp / "b.db")
os.environ.pop("APPS_SCRIPT_URL", None)

import logging  # noqa: E402
logging.disable(logging.WARNING)
import streamlit as st  # noqa: E402
from core.context import set_current_user_id  # noqa: E402
from places.finanzas import home  # noqa: E402

st.session_state["logged_in"] = True
st.session_state["current_user_id"] = 1
set_current_user_id(1)
from core import workspaces_ui  # noqa: E402
from core.db import connect  # noqa: E402
with connect() as conn:  # igual que app.py
    workspaces_ui.activar_desde_sesion(conn)
home.render()  # calentar imports

pr = cProfile.Profile()
pr.enable()
home.render()
pr.disable()
st_ = pstats.Stats(pr)
total = sum(v[3] for k, v in st_.stats.items() if k[2] == "render" and "finanzas" in k[0] and k[0].endswith("home.py"))
print("render total (cumtime home.render) ms:", round(total * 1000))

# funciones del repo, por tiempo acumulado
filas = []
for (f, ln, fn), (cc, nc, tt, ct, _) in st_.stats.items():
    if str(REPO).replace("\\", "/").lower() in f.replace("\\", "/").lower() and ".venv" not in f:
        filas.append((ct, nc, f.split("SuperAppFinanzas")[-1], ln, fn))
for ct, nc, f, ln, fn in sorted(filas, reverse=True)[:30]:
    print(f"{ct*1000:8.1f} ms  x{nc:<4} {f}:{ln} {fn}")

print("\n--- librerías (tottime agregado por paquete) ---")
agg = {}
for (f, ln, fn), (cc, nc, tt, ct, _) in st_.stats.items():
    fl = f.replace("\\", "/")
    for pkg in ("plotly", "pandas", "streamlit", "numpy", "sqlite3", "json", "narwhals"):
        if f"/{pkg}/" in fl or (pkg == "sqlite3" and "sqlite3" in fn):
            agg[pkg] = agg.get(pkg, 0) + tt
            break
    else:
        if fl.startswith("~") and "sqlite3" in fn:
            agg["sqlite3(C)"] = agg.get("sqlite3(C)", 0) + tt
for k, v in sorted(agg.items(), key=lambda x: -x[1]):
    print(f"{k:12} {v*1000:8.1f} ms")
print("\n--- builtins más pesados ---")
b = [(tt, nc, fn) for (f, ln, fn), (cc, nc, tt, ct, _) in st_.stats.items() if f == "~"]
for tt, nc, fn in sorted(b, reverse=True)[:8]:
    print(f"{tt*1000:8.1f} ms x{nc} {fn}")
