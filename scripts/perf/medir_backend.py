"""Línea base de backend: SQL por pantalla, reruns y funciones críticas.

Uso: python medir_backend.py <repo> <base.db> <salida.json>
Mide sobre una COPIA de la base (las escrituras no tocan el original).
"""
import json
import os
import re
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

REPO, BASE, SALIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(REPO))
os.chdir(REPO)
tmp = Path(tempfile.mkdtemp())
for suf in ("", "-wal", "-shm"):
    if Path(str(BASE) + suf).exists():
        shutil.copy(str(BASE) + suf, str(tmp / "b.db") + suf)
os.environ["DB_PATH"] = str(tmp / "b.db")
for k in ("APPS_SCRIPT_URL", "GEMINI_API_KEY", "SESSION_SECRET"):
    os.environ.pop(k, None)

# ---------- instrumentación de SQLite ----------
REG = {"conns": 0, "q": [], "ejemplos": {}}  # q: (sql_normalizado, segundos)


def _norm(sql):
    s = re.sub(r"\s+", " ", sql).strip()
    return re.sub(r"\b\d+\b", "N", s)[:160]


_orig = sqlite3.connect


def _connect(*a, **k):
    REG["conns"] += 1
    c = _orig(*a, **k)
    c.set_trace_callback(REG["q"].append if False else (lambda sql: REG["q"].append(sql)))
    return c


sqlite3.connect = _connect


def reset():
    REG["conns"] = 0
    REG["q"] = []


def _replay(sql):
    t = time.perf_counter()
    try:
        with _orig(os.environ["DB_PATH"]) as c:
            t = time.perf_counter()
            c.execute(sql).fetchall()
    except Exception:  # noqa: BLE001
        return 0.0
    return time.perf_counter() - t


def resumen_sql(top=8):
    qs = [q for q in REG["q"] if isinstance(q, str)]
    agg = defaultdict(lambda: [0, 0.0])
    for q in qs:
        k = _norm(q)
        agg[k][0] += 1
        if q.lstrip().upper().startswith(("SELECT", "WITH")):
            agg[k][1] += _replay(q)
    pragmas = sum(c for k, (c, _) in agg.items() if k.upper().startswith("PRAGMA"))
    total = sum(s for _, s in agg.values())
    filas = sorted(agg.items(), key=lambda kv: -kv[1][1])[:top]
    repetidas = sorted(((k, c) for k, (c, _) in agg.items()
                        if c > 1 and not k.upper().startswith("PRAGMA")), key=lambda x: -x[1])[:8]
    ejemplo = {}
    for q in qs:
        ejemplo.setdefault(_norm(q), q)
    REG["ejemplos"].update(ejemplo)
    return {
        "conexiones": REG["conns"], "sentencias": len(qs), "pragmas": pragmas,
        "sql_ms_reproducido": round(total * 1000, 1),
        "top_por_tiempo": [{"sql": k, "veces": c, "ms": round(s * 1000, 2)} for k, (c, s) in filas],
        "repetidas": [{"sql": k, "veces": c} for k, c in repetidas],
    }


def medir(fn, n=5):
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t) * 1000)
    return {"mediana_ms": round(statistics.median(ts), 1), "min_ms": round(min(ts), 1),
            "max_ms": round(max(ts), 1), "n": n}


out = {}

# ---------- pantallas (AppTest corre el script de verdad, sin navegador) ----------
from streamlit.testing.v1 import AppTest  # noqa: E402
import streamlit as st  # noqa: E402


def _sesion(at):
    at.session_state["logged_in"] = True
    at.session_state["current_user_id"] = 1
    at.session_state["current_username"] = "franco"
    at.session_state["current_user_fullname"] = "Franco"


def _finanzas():
    import streamlit as st
    from core.context import set_current_user_id
    from places.finanzas import home
    from core import workspaces_ui
    from core.db import connect
    set_current_user_id(st.session_state["current_user_id"])
    with connect() as conn:  # igual que app.py: workspace activo al contextvar
        workspaces_ui.activar_desde_sesion(conn)
    home.render()


def _contar_elementos(at):
    n = 0
    pila = [at._tree]
    while pila:
        x = pila.pop()
        n += 1
        hijos = getattr(x, "children", None)
        if isinstance(hijos, dict):
            pila.extend(hijos.values())
    return n


# Finanzas se mide pestaña por pestaña: desde el frente 1 (21/10/2026) corre
# solo la abierta. Con el código de la línea base la clave no hace nada y cada
# entrada vale lo mismo (las cinco juntas), así que el delta es comparable.
ETIQUETAS = [":material/dashboard: Dashboard", ":material/add_circle: Transacciones",
             ":material/menu_book: Diario", ":material/target: Mensual",
             ":material/settings: Configuración"]
casos = [("shell_app_py_inicio", lambda: AppTest.from_file("app.py", default_timeout=120), None),
         ("finanzas_5_pestanas", lambda: AppTest.from_function(_finanzas, default_timeout=120), None)]
casos += [(f"finanzas/{e.split(': ')[1]}", lambda: AppTest.from_function(_finanzas, default_timeout=120), e)
          for e in ETIQUETAS]
def _escribir_gasto():
    from datetime import date as _date
    from core.context import set_current_user_id as _set_uid
    from core.db import connect as _connect
    from places.finanzas.core.transactions import insertar_sin_backup as _ins
    _set_uid(1)
    with _connect() as c:
        _ins(c, _date.today(), "Compras", pasivos=1, user_id=1)


pantallas = {}
for nombre, crear, pestana in casos:
    st.cache_data.clear()
    at = crear()
    _sesion(at)
    if pestana:
        at.session_state["finanzas_pestana"] = pestana
    reset()
    t = time.perf_counter()
    at.run()
    primera = (time.perf_counter() - t) * 1000
    sql1 = resumen_sql()
    errores = [str(e.value)[:200] for e in at.exception]
    # reruns "en vacío": lo que cuesta cualquier click que no cambia nada
    tiempos = []
    sql_rerun = None
    for i in range(5):
        reset()
        t = time.perf_counter()
        at.run()
        tiempos.append((time.perf_counter() - t) * 1000)
        if i == 4:
            sql_rerun = resumen_sql(top=5)
    # reruns justo después de una escritura (frente 3): el peor caso de una
    # caché, que tiene que recalcular. Escribe otra conexión, como el bot.
    tras_escritura = []
    for _ in range(5):
        _escribir_gasto()
        t = time.perf_counter()
        at.run()
        tras_escritura.append((time.perf_counter() - t) * 1000)
    pantallas[nombre] = {
        "rerun_tras_escritura_mediana_ms": round(statistics.median(tras_escritura), 1),
        "primer_render_ms": round(primera, 1),
        "rerun_mediana_ms": round(statistics.median(tiempos), 1),
        "rerun_min_max_ms": [round(min(tiempos), 1), round(max(tiempos), 1)],
        "elementos_en_arbol": _contar_elementos(at),
        "errores": errores,
        "sql_primer_render": sql1,
        "sql_por_rerun": {k: sql_rerun[k] for k in ("conexiones", "sentencias", "pragmas", "sql_ms_reproducido")},
        "sql_por_rerun_top": sql_rerun["top_por_tiempo"],
    }
out["pantallas"] = pantallas

# ---------- funciones críticas (las que usan las pantallas y el bot) ----------
from core.context import set_current_user_id  # noqa: E402
from core.db import connect  # noqa: E402
from places.finanzas.core import metrics  # noqa: E402
from places.finanzas.core.comandos import procesar  # noqa: E402
from places.inicio.core import resumen as rs  # noqa: E402

set_current_user_id(1)
funcs = {}
with connect() as conn:
    funcs["metrics.load_transactions"] = medir(lambda: metrics.load_transactions(conn, user_id=1))
    df = metrics.load_transactions(conn, user_id=1)
    cats = metrics.load_categorias_map(conn, user_id=1)
    funcs["metrics.compute_kpis"] = medir(lambda: metrics.compute_kpis(df, cats))
    funcs["metrics.saldo_cuenta_corriente"] = medir(lambda: metrics.saldo_cuenta_corriente(conn, user_id=1))
    funcs["inicio.resumen_del_mes"] = medir(lambda: rs.resumen_del_mes(conn, user_id=1, hoy=__import__("datetime").date.today()))
    reset()
    funcs["bot.procesar('resumen')"] = medir(lambda: procesar(conn, "resumen", user_id=1))
    reset()
    procesar(conn, "resumen", user_id=1)
    funcs["bot.procesar('resumen')"]["sql"] = {k: v for k, v in resumen_sql(3).items() if k != "repetidas"}
out["funciones"] = funcs
out["filas_transacciones"] = len(df)

# ---------- las consultas más pesadas, aisladas ----------
SQL_PESADAS = {}
for p in pantallas.values():
    for q in p["sql_primer_render"]["top_por_tiempo"][:4]:
        SQL_PESADAS.setdefault(q["sql"], q["ms"])
out["sql_pesadas_planes"] = []
with _orig(os.environ["DB_PATH"]) as c:
    for sql in list(SQL_PESADAS)[:6]:
        real = REG["ejemplos"].get(sql, "")
        try:
            plan = [r[3] for r in c.execute("EXPLAIN QUERY PLAN " + real)] if real.lstrip().upper().startswith("SELECT") else None
        except Exception as e:  # noqa: BLE001
            plan = f"no se pudo: {e}"
        out["sql_pesadas_planes"].append({"sql": sql, "ms_en_pantalla": SQL_PESADAS[sql], "plan": plan})
    out["indices"] = [r[0] for r in c.execute(
        "select name||' ON '||tbl_name from sqlite_master where type='index' and name not like 'sqlite_%'")]

SALIDA.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])
