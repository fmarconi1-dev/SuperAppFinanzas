#!/usr/bin/env python3
"""
indexar.py — Construye el indice vivo de UN proyecto.

Escanea el repo, resuelve las relaciones internas (que archivo importa a cual,
que archivos se tocan juntos segun git, donde esta definido cada simbolo), lee
las BITACORA.md de cada carpeta y ensambla MAPA.md: un unico archivo chico que
alcanza para saber donde buscar cualquier cosa sin abrir el repo.

El JSON puede ser enorme; no importa, lo lee un script. Al contexto solo entra
MAPA.md.

Solo stdlib. Python 3.9+.

Uso:
    python3 indexar.py /ruta/al/repo              # indexa y reescribe MAPA.md
    python3 indexar.py . --estructura             # ademas, diagnostico de estructura
    python3 indexar.py . --solo-json              # sin tocar MAPA.md
    python3 indexar.py . --frescura               # solo reporta que esta desactualizado
"""

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

IGNORAR_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", ".next", ".nuxt", ".cache", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "site-packages", ".idea", ".vscode", "vendor",
    "coverage", ".tox", "htmlcov", ".terraform", ".mapa",
}
IGNORAR_ARCHIVOS = {"*.pyc", "*.pyo", "*.so", "*.dylib", "*.dll", "*.class", "*.o",
                    "*.a", "*.zip", "*.tar.gz", "*.png", "*.jpg", "*.jpeg", "*.gif",
                    "*.pdf", "*.xlsx", "*.xls", "*.db", "*.sqlite", "*.sqlite3",
                    "*.parquet", "*.lock", "*.min.js", "*.map"}
LENGUAJES = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".go": "go", ".rs": "rust", ".java": "java",
    ".kt": "kotlin", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
    ".rb": "ruby", ".php": "php", ".cs": "csharp", ".swift": "swift", ".r": "r",
    ".R": "r", ".jl": "julia", ".sh": "bash", ".bash": "bash", ".ps1": "powershell",
    ".sql": "sql", ".html": "html", ".css": "css", ".scss": "scss", ".yml": "yaml",
    ".yaml": "yaml", ".toml": "toml", ".json": "json", ".md": "markdown",
    ".ipynb": "notebook", ".tf": "terraform",
}
CODIGO = {"python", "javascript", "typescript", "go", "rust", "java", "kotlin",
          "c", "cpp", "ruby", "php", "csharp", "swift", "r", "julia", "bash", "sql"}
STDLIB = {
    "os", "sys", "re", "json", "time", "datetime", "pathlib", "typing", "math",
    "logging", "collections", "itertools", "functools", "subprocess", "argparse",
    "random", "csv", "io", "shutil", "glob", "traceback", "warnings", "copy",
    "hashlib", "base64", "uuid", "tempfile", "textwrap", "dataclasses", "enum",
    "abc", "asyncio", "threading", "unittest", "string", "pickle", "urllib",
    "http", "socket", "struct", "zlib", "gzip", "decimal", "statistics", "sqlite3",
}
HOSTS_RUIDO = {
    "github.com", "raw.githubusercontent.com", "w3.org", "schemas.xmlsoap.org",
    "localhost", "127.0.0.1", "example.com", "python.org", "docs.python.org",
    "pypi.org", "npmjs.com", "stackoverflow.com", "json-schema.org",
    "opensource.org", "creativecommons.org", "fonts.googleapis.com",
    "cdn.jsdelivr.net", "unpkg.com",
}
MAX_BYTES = 1_500_000
GRANDE = 500          # LOC a partir de las cuales un archivo se marca
MAX_LINEAS_MAPA = 260  # presupuesto de contexto del MAPA.md

RE_URL = re.compile(r"""https?://([A-Za-z0-9._~-]+\.[A-Za-z]{2,})(/[^\s'"`)\]>,;]*)?""")
RE_ENV = re.compile(
    r"""(?:os\.environ(?:\.get)?\(\s*|os\.getenv\(\s*|os\.environ\[\s*)['"]([A-Z0-9_]{2,})['"]"""
    r"""|process\.env\.([A-Z0-9_]{2,})|\$\{\{\s*(?:secrets|vars)\.([A-Z0-9_]{2,})\s*\}\}""")
RE_JS_SIMBOLO = re.compile(
    r"""^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)"""
    r"""|^\s*export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="""
    r"""|^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"""
    r"""|^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(""", re.M)
RE_JS_IMPORT = re.compile(r"""(?:from\s+|require\(\s*|import\(\s*)['"]([^'"]+)['"]""")
RE_CRON = re.compile(r"""cron:\s*['"]([^'"]+)['"]""")
RE_HUELLA = re.compile(r"<!--\s*huella:\s*(\S+)\s*-->")
RE_RESUMEN = re.compile(r"^\s*(?:\*\*)?Resumen(?:\*\*)?:\s*(.+)$", re.M | re.I)
RE_BUSCAR = re.compile(r"^##+\s*Buscar ac[aá] si.*$", re.M | re.I)


# ---------------------------------------------------------------- utilidades

def cargar_gitignore(raiz):
    pats = []
    gi = raiz / ".gitignore"
    if gi.exists():
        for l in gi.read_text(errors="ignore").splitlines():
            l = l.split("#")[0].strip()
            if l and not l.startswith("!"):
                pats.append(l.rstrip("/"))
    return pats


def ignorado(rel, pats):
    partes = Path(rel).parts
    if any(p in IGNORAR_DIRS for p in partes):
        return True
    nombre = Path(rel).name
    if any(fnmatch.fnmatch(nombre, p) for p in IGNORAR_ARCHIVOS):
        return True
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(nombre, p)
               or rel.startswith(p + "/") for p in pats)


def leer(p):
    try:
        if p.stat().st_size > MAX_BYTES:
            return None
        return p.read_text(encoding="utf-8", errors="ignore")
    except (OSError, ValueError):
        return None


def git(raiz, *args, timeout=20):
    try:
        r = subprocess.run(["git", "-C", str(raiz), *args], capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------------------------------------------------------------- extractores

def extraer_python(texto):
    simbolos, imports, rel_imports = [], set(), []
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return simbolos, imports, rel_imports, False
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            simbolos.append({"nombre": n.name, "tipo": "funcion", "linea": n.lineno,
                             "firma": ", ".join(a.arg for a in n.args.args),
                             "doc": (ast.get_docstring(n) or "").split("\n")[0][:100] or None})
        elif isinstance(n, ast.ClassDef):
            simbolos.append({"nombre": n.name, "tipo": "clase", "linea": n.lineno,
                             "firma": ", ".join(m.name for m in n.body
                                                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))[:120],
                             "doc": (ast.get_docstring(n) or "").split("\n")[0][:100] or None})
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            for a in n.names:
                imports.add(a.name)
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                rel_imports.append((n.level, n.module or ""))
            elif n.module:
                imports.add(n.module)
    return simbolos, imports, rel_imports, ("__main__" in texto and "if __name__" in texto)


def extraer_js(texto):
    simbolos, imports, rel = [], set(), []
    vistos = set()
    for m in RE_JS_SIMBOLO.finditer(texto):
        n = next((g for g in m.groups() if g), None)
        if n and n not in vistos:
            vistos.add(n)
            tipo = "export" if m.group(1) or m.group(2) else "funcion"
            simbolos.append({"nombre": n, "tipo": tipo,
                             "linea": texto[:m.start()].count("\n") + 1,
                             "firma": "", "doc": None})
    for m in RE_JS_IMPORT.finditer(texto):
        esp = m.group(1)
        if esp.startswith("."):
            rel.append(esp)
        else:
            partes = esp.split("/")
            imports.add("/".join(partes[:2]) if esp.startswith("@") else partes[0])
    return simbolos, imports, rel, False


def extraer_urls(texto):
    out = defaultdict(set)
    for m in RE_URL.finditer(texto):
        h = m.group(1).lower()
        if h.startswith("www."):
            h = h[4:]
        if h in HOSTS_RUIDO:
            continue
        out[h].add((m.group(2) or "/").split("?")[0][:70])
    return out


def extraer_env(texto):
    return {g for t in RE_ENV.findall(texto) for g in t if g}


# ---------------------------------------------------------------- bitacoras

def parsear_bitacora(texto):
    """Extrae de una BITACORA.md lo que se eleva al MAPA.md."""
    huella = RE_HUELLA.search(texto)
    resumen = RE_RESUMEN.search(texto)
    pistas = []
    m = RE_BUSCAR.search(texto)
    if m:
        resto = texto[m.end():]
        corte = re.search(r"^##+\s", resto, re.M)
        bloque = resto[:corte.start()] if corte else resto
        for l in bloque.splitlines():
            l = l.strip()
            if l.startswith(("-", "*")):
                pistas.append(l.lstrip("-* ").strip())
    return {
        "huella_declarada": huella.group(1) if huella else None,
        "resumen": resumen.group(1).strip() if resumen else None,
        "pistas": pistas,
    }


def huella_carpeta(archivos_texto):
    """Hash del contenido de codigo de una carpeta. Cambia => la bitacora vencio."""
    h = hashlib.sha256()
    for ruta, texto in sorted(archivos_texto):
        h.update(ruta.encode())
        h.update(hashlib.sha256(texto.encode("utf-8", "ignore")).digest())
    return h.hexdigest()[:12]


# ---------------------------------------------------------------- co-cambio git

def co_cambios(raiz, max_commits=400, max_archivos=15):
    """Archivos que se modifican en el mismo commit. Acoplamiento real, no declarado."""
    salida = git(raiz, "log", f"-{max_commits}", "--name-only", "--format=%x00%H",
                 "--no-merges")
    if not salida:
        return {}, {}
    pares, toques = Counter(), Counter()
    for bloque in salida.split("\x00")[1:]:
        lineas = [l.strip() for l in bloque.splitlines()[1:] if l.strip()]
        archivos = [l for l in lineas if Path(l).suffix in LENGUAJES]
        if not 2 <= len(archivos) <= max_archivos:
            for a in archivos:
                toques[a] += 1
            continue
        for a in archivos:
            toques[a] += 1
        for i, a in enumerate(archivos):
            for b in archivos[i + 1:]:
                pares[tuple(sorted((a, b)))] += 1
    return pares, toques


# ---------------------------------------------------------------- resolucion interna

def construir_resolucion(archivos, raiz):
    """Mapea nombres de modulo a rutas del repo, para resolver imports internos."""
    por_modulo = {}
    for a in archivos:
        p = Path(a["ruta"])
        if a["lenguaje"] == "python":
            partes = list(p.with_suffix("").parts)
            if partes[-1] == "__init__":
                partes = partes[:-1]
            for i in range(len(partes)):
                por_modulo.setdefault(".".join(partes[i:]), a["ruta"])
        elif a["lenguaje"] in ("javascript", "typescript"):
            por_modulo.setdefault(str(p.with_suffix("")), a["ruta"])
            por_modulo.setdefault(p.stem, a["ruta"])
    return por_modulo


def resolver_imports(archivos, por_modulo):
    """Aristas archivo -> archivo dentro del repo."""
    aristas = defaultdict(set)
    externos = Counter()
    for a in archivos:
        origen = a["ruta"]
        for imp in a.get("_imports_crudos", []):
            destino = por_modulo.get(imp) or por_modulo.get(imp.split(".")[0])
            if destino and destino != origen:
                aristas[origen].add(destino)
            elif imp.split(".")[0] not in STDLIB:
                externos[imp.split(".")[0]] += 1
        for rel in a.get("_rel_crudos", []):
            base = Path(origen).parent
            if isinstance(rel, tuple):           # python: (nivel, modulo)
                nivel, mod = rel
                for _ in range(nivel - 1):
                    base = base.parent
                cand = str(base / mod.replace(".", "/")) if mod else str(base)
            else:                                 # js: './x'
                cand = os.path.normpath(str(base / rel))
            destino = por_modulo.get(cand) or por_modulo.get(cand.replace("/", "."))
            if destino and destino != origen:
                aristas[origen].add(destino)
    return aristas, externos


# ---------------------------------------------------------------- escaneo

def indexar(ruta):
    raiz = Path(ruta).resolve()
    if not raiz.is_dir():
        sys.exit(f"No es un directorio: {raiz}")
    pats = cargar_gitignore(raiz)

    archivos = []
    textos_por_carpeta = defaultdict(list)
    bitacoras = {}
    hosts = defaultdict(lambda: defaultdict(set))   # host -> archivo -> rutas
    envs = defaultdict(set)                          # var -> archivos
    workflows = []
    entrypoints = []

    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in IGNORAR_DIRS
                       and (not d.startswith(".") or d == ".github")]
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            rel = str(p.relative_to(raiz))
            if ignorado(rel, pats):
                continue
            texto = leer(p)
            if texto is None:
                continue
            carpeta = str(Path(rel).parent) if Path(rel).parent != Path(".") else "."

            if fn.upper() == "BITACORA.MD":
                bitacoras[carpeta] = parsear_bitacora(texto)
                continue

            lenguaje = LENGUAJES.get(p.suffix, "otro")
            loc = texto.count("\n") + 1
            simbolos, imps, rels, es_ep = [], set(), [], False
            if lenguaje == "python":
                simbolos, imps, rels, es_ep = extraer_python(texto)
            elif lenguaje in ("javascript", "typescript"):
                simbolos, imps, rels, es_ep = extraer_js(texto)

            for h, rutas in extraer_urls(texto).items():
                hosts[h][rel] |= rutas
            for e in extraer_env(texto):
                envs[e].add(rel)

            if rel.startswith(".github/workflows"):
                workflows.append({
                    "archivo": rel,
                    "nombre": (re.search(r"^name:\s*(.+)$", texto, re.M) or [None, p.stem])[1].strip().strip("'\""),
                    "cron": RE_CRON.findall(texto),
                    "manual": "workflow_dispatch" in texto,
                })
            if es_ep or fn in ("main.py", "app.py", "index.js", "main.go", "run.py",
                               "manage.py", "cli.py", "bot.py", "server.py", "__main__.py"):
                entrypoints.append(rel)

            if lenguaje in CODIGO:
                textos_por_carpeta[carpeta].append((rel, texto))
            if lenguaje in CODIGO or lenguaje in ("yaml", "toml"):
                archivos.append({
                    "ruta": rel, "carpeta": carpeta, "lenguaje": lenguaje, "loc": loc,
                    "simbolos": simbolos,
                    "_imports_crudos": sorted(imps),
                    "_rel_crudos": rels,
                })

    # relaciones internas
    por_modulo = construir_resolucion(archivos, raiz)
    aristas, externos = resolver_imports(archivos, por_modulo)
    importado_por = defaultdict(set)
    for o, ds in aristas.items():
        for d in ds:
            importado_por[d].add(o)

    pares, toques = co_cambios(raiz)

    # carpetas
    carpetas = {}
    todas = sorted({a["carpeta"] for a in archivos} | set(bitacoras))
    for c in todas:
        propios = [a for a in archivos if a["carpeta"] == c]
        h = huella_carpeta(textos_por_carpeta.get(c, []))
        bit = bitacoras.get(c)
        estado = ("sin bitacora" if not bit else
                  "al dia" if bit["huella_declarada"] == h else
                  "desactualizada")
        carpetas[c] = {
            "archivos": len(propios),
            "loc": sum(a["loc"] for a in propios),
            "lenguajes": [l for l, _ in Counter(a["lenguaje"] for a in propios).most_common(3)],
            "huella": h,
            "estado_bitacora": estado,
            "resumen": (bit or {}).get("resumen"),
            "pistas": (bit or {}).get("pistas", []),
            "simbolos": sum(len(a["simbolos"]) for a in propios),
        }

    # acoplamiento entre carpetas
    entre_carpetas = Counter()
    dir_de = {a["ruta"]: a["carpeta"] for a in archivos}
    for o, ds in aristas.items():
        for d in ds:
            co, cd = dir_de.get(o), dir_de.get(d)
            if co and cd and co != cd:
                entre_carpetas[(co, cd)] += 1

    for a in archivos:
        a.pop("_imports_crudos", None)
        a.pop("_rel_crudos", None)
        a["importa"] = sorted(aristas.get(a["ruta"], []))
        a["importado_por"] = sorted(importado_por.get(a["ruta"], []))
        a["commits"] = toques.get(a["ruta"], 0)

    mapa = {
        "proyecto": raiz.name,
        "ruta": str(raiz),
        "indexado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "git": {
            "rama": git(raiz, "rev-parse", "--abbrev-ref", "HEAD").strip() or None,
            "ultimo_commit": git(raiz, "log", "-1", "--format=%cs %h %s").strip() or None,
            "sucio": bool([l for l in git(raiz, "status", "--porcelain").splitlines()
                           if ".mapa/" not in l and "MAPA.md" not in l]),
        },
        "tamano": {
            "archivos": len(archivos),
            "loc": sum(a["loc"] for a in archivos),
            "por_lenguaje": dict(Counter(
                {l: sum(a["loc"] for a in archivos if a["lenguaje"] == l)
                 for l in {a["lenguaje"] for a in archivos}}).most_common()),
        },
        "entrypoints": sorted(set(entrypoints)),
        "workflows": workflows,
        "carpetas": carpetas,
        "acoplamiento": [{"de": a, "a": b, "peso": n}
                         for (a, b), n in entre_carpetas.most_common()],
        "co_cambio": [{"a": a, "b": b, "veces": n}
                      for (a, b), n in pares.most_common(40) if n >= 3],
        "dependencias_externas": dict(externos.most_common(40)),
        "fuentes_externas": [
            {"host": h, "archivos": sorted(m), "rutas": sorted({r for rs in m.values() for r in rs})[:10]}
            for h, m in sorted(hosts.items(), key=lambda x: -len(x[1]))],
        "variables_entorno": {k: sorted(v) for k, v in sorted(envs.items())},
        "archivos": sorted(archivos, key=lambda a: -a["loc"]),
    }
    return mapa


# ---------------------------------------------------------------- diagnostico

def diagnostico(m):
    d = {"sin_bitacora": [], "bitacora_vencida": [], "huerfanos": [], "grandes": [],
         "ciclos": [], "co_cambio_disperso": [], "carpetas_infladas": []}
    for c, info in m["carpetas"].items():
        if info["archivos"] == 0:
            continue
        if info["estado_bitacora"] == "sin bitacora" and info["loc"] > 80:
            d["sin_bitacora"].append(c)
        elif info["estado_bitacora"] == "desactualizada":
            d["bitacora_vencida"].append(c)
        if info["archivos"] > 15:
            d["carpetas_infladas"].append((c, info["archivos"]))

    eps = set(m["entrypoints"])
    for a in m["archivos"]:
        if a["loc"] > GRANDE:
            d["grandes"].append((a["ruta"], a["loc"]))
        if (not a["importado_por"] and a["ruta"] not in eps
                and a["lenguaje"] in CODIGO and a["simbolos"]
                and "test" not in a["ruta"].lower()
                and not a["ruta"].startswith(".github")):
            d["huerfanos"].append(a["ruta"])

    pesos = {(x["de"], x["a"]): x["peso"] for x in m["acoplamiento"]}
    for (a, b), n in pesos.items():
        if (b, a) in pesos and a < b:
            d["ciclos"].append((a, b, n, pesos[(b, a)]))

    dir_de = {a["ruta"]: a["carpeta"] for a in m["archivos"]}
    for cc in m["co_cambio"]:
        ca, cb = dir_de.get(cc["a"]), dir_de.get(cc["b"])
        if ca and cb and ca != cb and cc["veces"] >= 4:
            d["co_cambio_disperso"].append((cc["a"], cc["b"], cc["veces"]))
    return d


def texto_diagnostico(d):
    L = ["## Diagnostico de estructura", ""]
    def bloque(titulo, items, fmt, nota=None):
        if not items:
            return
        L.append(f"**{titulo}**")
        if nota:
            L.append(f"_{nota}_")
        L.append("")
        for i in items[:12]:
            L.append("- " + fmt(i))
        L.append("")
    bloque("Carpetas sin bitacora", d["sin_bitacora"], lambda x: f"`{x}/`",
           "Cada una obliga a leer sus archivos para saber que hacen.")
    bloque("Bitacoras vencidas", d["bitacora_vencida"], lambda x: f"`{x}/`",
           "El codigo cambio desde que se escribieron. Refrescarlas o el mapa miente.")
    bloque("Archivos que nadie importa", d["huerfanos"], lambda x: f"`{x}`",
           "Codigo muerto, script suelto o entrypoint no declarado. Verificar cual.")
    bloque("Archivos grandes", d["grandes"], lambda x: f"`{x[0]}` ({x[1]} LOC)",
           "Candidatos a partir: encarecen cada lectura futura.")
    bloque("Ciclos entre carpetas", d["ciclos"],
           lambda x: f"`{x[0]}/` ↔ `{x[1]}/` ({x[2]} y {x[3]} imports)",
           "Se importan mutuamente: el limite entre ambas no esta bien trazado.")
    bloque("Cambian juntos pero viven separados", d["co_cambio_disperso"],
           lambda x: f"`{x[0]}` + `{x[1]}` ({x[2]} commits)",
           "Acoplamiento real que la estructura de carpetas no refleja.")
    bloque("Carpetas infladas", d["carpetas_infladas"], lambda x: f"`{x[0]}/` ({x[1]} archivos)",
           "Sin subdivision, obligan a escanear todo para encontrar algo.")
    if len(L) == 2:
        L.append("Sin hallazgos.")
        L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- MAPA.md

def generar_mapa(m):
    L = [f"# MAPA — {m['proyecto']}", ""]
    L.append("<!-- GENERADO por indexar.py. No editar: los cambios se pierden. -->")
    L.append("<!-- La prosa vive en las BITACORA.md de cada carpeta. -->")
    t = m["tamano"]
    git_i = m["git"]
    L.append(f"<!-- {m['indexado']} · {t['archivos']} archivos · {t['loc']:,} LOC -->")
    L.append("")

    L.append("## Como usar este archivo")
    L.append("")
    L.append("Es el unico archivo del proyecto que hace falta leer para empezar. Para "
             "ubicar algo concreto: `python3 .mapa/buscar.py \"<termino>\"` devuelve "
             "archivo y linea sin abrir nada. Recien despues abrir los archivos que "
             "salgan, y solo esos.")
    L.append("")
    if git_i.get("ultimo_commit"):
        sucio = " · **hay cambios sin commitear**" if git_i.get("sucio") else ""
        L.append(f"Rama `{git_i.get('rama')}` — ultimo commit: {git_i['ultimo_commit']}{sucio}")
        L.append("")

    # --- router
    L.append("## Donde buscar que")
    L.append("")
    filas = []
    for c, info in sorted(m["carpetas"].items()):
        for p in info["pistas"]:
            filas.append((p, c))
    if filas:
        L.append("| Si la consulta es sobre... | Ir a |")
        L.append("|---|---|")
        for pista, c in filas:
            L.append(f"| {pista} | `{c}/` |")
    else:
        L.append("_Sin pistas todavia: ninguna carpeta tiene seccion \"Buscar aca si\" "
                 "en su BITACORA.md. Es la seccion que hace util a este mapa._")
    L.append("")

    # --- carpetas
    L.append("## Carpetas")
    L.append("")
    L.append("| Carpeta | Que es | Arch. | LOC | Bitacora |")
    L.append("|---|---|---:|---:|---|")
    marca = {"al dia": "ok", "desactualizada": "**vencida**", "sin bitacora": "—"}
    for c, i in sorted(m["carpetas"].items(), key=lambda x: -x[1]["loc"]):
        if i["archivos"] == 0 and not i["resumen"]:
            continue
        L.append(f"| `{c}/` | {i['resumen'] or '_sin describir_'} | {i['archivos']} | "
                 f"{i['loc']:,} | {marca.get(i['estado_bitacora'], '—')} |")
    L.append("")

    # --- entradas
    if m["entrypoints"] or m["workflows"]:
        L.append("## Puntos de entrada")
        L.append("")
        for e in m["entrypoints"][:10]:
            L.append(f"- `{e}`")
        for w in m["workflows"]:
            disp = ", ".join(w["cron"]) if w["cron"] else ("manual" if w["manual"] else "push")
            L.append(f"- `{w['archivo']}` — {w['nombre']} ({disp})")
        L.append("")

    # --- nucleo
    centrales = sorted(m["archivos"], key=lambda a: (-len(a["importado_por"]), -a["loc"]))
    centrales = [a for a in centrales if a["importado_por"] or a["loc"] > 150][:12]
    if centrales:
        L.append("## Archivos centrales")
        L.append("")
        L.append("Ordenados por cuantos otros archivos dependen de ellos. Tocar uno de "
                 "arriba tiene mas radio de impacto.")
        L.append("")
        L.append("| Archivo | LOC | Lo usan | Simbolos |")
        L.append("|---|---:|---:|---|")
        for a in centrales:
            nombres = ", ".join(f"`{s['nombre']}`" for s in a["simbolos"][:4])
            L.append(f"| `{a['ruta']}` | {a['loc']} | {len(a['importado_por'])} | {nombres or '—'} |")
        L.append("")

    # --- flujo entre carpetas
    if m["acoplamiento"]:
        L.append("## Flujo interno")
        L.append("")
        for x in m["acoplamiento"][:12]:
            L.append(f"- `{x['de']}/` → `{x['a']}/` ({x['peso']})")
        L.append("")

    # --- co-cambio
    if m["co_cambio"]:
        L.append("## Se tocan juntos")
        L.append("")
        L.append("Segun el historial de git. Si vas a cambiar uno, mira el otro.")
        L.append("")
        for cc in m["co_cambio"][:10]:
            L.append(f"- `{cc['a']}` + `{cc['b']}` ({cc['veces']} commits)")
        L.append("")

    # --- fuentes y config
    if m["fuentes_externas"]:
        L.append("## Fuentes externas")
        L.append("")
        for f in m["fuentes_externas"][:12]:
            L.append(f"- `{f['host']}` — {', '.join(f'`{a}`' for a in f['archivos'][:3])}")
        L.append("")
    if m["variables_entorno"]:
        L.append("## Configuracion requerida")
        L.append("")
        for k, archivos in list(m["variables_entorno"].items())[:15]:
            L.append(f"- `{k}` — {', '.join(f'`{a}`' for a in archivos[:3])}")
        L.append("")

    # --- frescura
    venc = [c for c, i in m["carpetas"].items() if i["estado_bitacora"] == "desactualizada"]
    falt = [c for c, i in m["carpetas"].items()
            if i["estado_bitacora"] == "sin bitacora" and i["loc"] > 80]
    if venc or falt:
        L.append("## Frescura")
        L.append("")
        if venc:
            L.append(f"- Bitacoras vencidas: {', '.join(f'`{c}/`' for c in venc)}")
        if falt:
            L.append(f"- Carpetas sin bitacora: {', '.join(f'`{c}/`' for c in falt)}")
        L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Indice vivo de un proyecto")
    ap.add_argument("ruta", nargs="?", default=".")
    ap.add_argument("--estructura", action="store_true", help="diagnostico de estructura")
    ap.add_argument("--solo-json", action="store_true", help="no reescribir MAPA.md")
    ap.add_argument("--frescura", action="store_true", help="solo reportar desactualizados")
    ap.add_argument("--sellar", metavar="CARPETA",
                    help="estampa la huella actual en la BITACORA.md de esa carpeta "
                         "(usar SOLO despues de actualizarle el contenido)")
    args = ap.parse_args()

    m = indexar(args.ruta)
    raiz = Path(m["ruta"])

    if args.sellar:
        c = args.sellar.rstrip("/")
        info = m["carpetas"].get(c)
        if not info:
            sys.exit(f"Carpeta no indexada: {c}")
        bit = raiz / c / "BITACORA.md"
        if not bit.exists():
            sys.exit(f"No existe {bit}. Crear la bitacora primero.")
        texto = bit.read_text(encoding="utf-8")
        marca = f"<!-- huella: {info['huella']} -->"
        nuevo = (RE_HUELLA.sub(marca, texto) if RE_HUELLA.search(texto)
                 else re.sub(r"^(#\s.*\n)", r"\1\n" + marca + "\n", texto, count=1))
        bit.write_text(nuevo, encoding="utf-8")
        print(f"{c}/BITACORA.md sellada con huella {info['huella']}", file=sys.stderr)
        return

    destino = raiz / ".mapa"
    destino.mkdir(exist_ok=True)
    (destino / "mapa.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")

    # dejar buscar.py junto al indice para que el comando del MAPA funcione
    origen_buscar = Path(__file__).parent / "buscar.py"
    if origen_buscar.exists() and not (destino / "buscar.py").exists():
        (destino / "buscar.py").write_text(origen_buscar.read_text(), encoding="utf-8")

    if args.frescura:
        for c, i in sorted(m["carpetas"].items()):
            if i["estado_bitacora"] != "al dia" and i["loc"] > 80:
                print(f"{i['estado_bitacora']:16} {c}/  (huella actual {i['huella']})")
        return

    if not args.solo_json:
        texto = generar_mapa(m)
        (raiz / "MAPA.md").write_text(texto, encoding="utf-8")
        n = texto.count("\n")
        aviso = "  ← excede el presupuesto, podar secciones" if n > MAX_LINEAS_MAPA else ""
        print(f"MAPA.md: {n} lineas{aviso}", file=sys.stderr)

    print(f".mapa/mapa.json: {m['tamano']['archivos']} archivos, "
          f"{m['tamano']['loc']:,} LOC, {len(m['carpetas'])} carpetas", file=sys.stderr)

    if args.estructura:
        print(texto_diagnostico(diagnostico(m)))


if __name__ == "__main__":
    main()
