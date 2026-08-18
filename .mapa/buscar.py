#!/usr/bin/env python3
"""
buscar.py — Consulta el indice sin abrir archivos del proyecto.

Reemplaza el ciclo grep → read → grep. Devuelve ubicaciones exactas
(archivo:linea), el contexto de la bitacora de esa carpeta y los archivos
vecinos, en una salida de decenas de lineas en vez de miles.

Uso:
    python3 .mapa/buscar.py "tir"                 # simbolos, archivos, pistas
    python3 .mapa/buscar.py "bcra" --todo         # incluye fuentes y config
    python3 .mapa/buscar.py --archivo src/x.py    # vecindario de un archivo
    python3 .mapa/buscar.py --carpeta src/datos   # inventario de una carpeta
    python3 .mapa/buscar.py --leer                # que abrir primero (top del mapa)
"""

import argparse
import json
import sys
from pathlib import Path


def cargar(ruta_hint=None):
    aqui = Path(__file__).resolve().parent
    candidatos = []
    if ruta_hint:
        candidatos.append(Path(ruta_hint).expanduser().resolve())
    candidatos += [aqui / "mapa.json", aqui / ".mapa" / "mapa.json",
                   Path.cwd() / ".mapa" / "mapa.json"]
    for p in candidatos:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    sys.exit("No se encontro mapa.json. Corre indexar.py primero.")


def puntuar(nombre, q):
    n, q = nombre.lower(), q.lower()
    if n == q:
        return 100
    if n.startswith(q) or n.endswith(q):
        return 60
    if q in n:
        return 40
    # fragmentos: "fetch bcra" matchea fetch_bcra
    partes = [p for p in q.replace("_", " ").replace("-", " ").split() if p]
    if partes and all(p in n for p in partes):
        return 30
    return 0


def buscar(m, q, todo=False, limite=12):
    L = []

    # simbolos
    hits = []
    for a in m["archivos"]:
        for s in a["simbolos"]:
            p = puntuar(s["nombre"], q)
            if p:
                hits.append((p, a, s))
    hits.sort(key=lambda x: (-x[0], x[1]["ruta"]))
    if hits:
        L.append(f"SIMBOLOS ({len(hits)})")
        for _, a, s in hits[:limite]:
            firma = f"({s['firma']})" if s["tipo"] == "funcion" else \
                    (f" [{s['firma']}]" if s["firma"] else "")
            doc = f"  — {s['doc']}" if s.get("doc") else ""
            L.append(f"  {a['ruta']}:{s['linea']}  {s['tipo']} {s['nombre']}{firma}{doc}")
        if len(hits) > limite:
            L.append(f"  … {len(hits) - limite} mas")
        L.append("")

    # archivos por ruta
    arch = [a for a in m["archivos"] if q.lower() in a["ruta"].lower()]
    if arch:
        L.append(f"ARCHIVOS ({len(arch)})")
        for a in sorted(arch, key=lambda x: -x["loc"])[:limite]:
            L.append(f"  {a['ruta']}  {a['loc']} LOC, {len(a['simbolos'])} simbolos, "
                     f"lo usan {len(a['importado_por'])}")
        L.append("")

    # pistas de bitacoras
    pistas = []
    for c, i in m["carpetas"].items():
        for p in i["pistas"]:
            if q.lower() in p.lower():
                pistas.append((c, p))
        if i.get("resumen") and q.lower() in i["resumen"].lower():
            pistas.append((c, i["resumen"]))
    if pistas:
        L.append("BITACORAS")
        for c, p in pistas[:limite]:
            L.append(f"  {c}/  {p}")
        L.append("")

    # fuentes y config
    fuentes = [f for f in m["fuentes_externas"] if q.lower() in f["host"].lower()]
    envs = {k: v for k, v in m["variables_entorno"].items() if q.lower() in k.lower()}
    if fuentes or envs or todo:
        for f in fuentes:
            L.append(f"FUENTE {f['host']}")
            for a in f["archivos"][:8]:
                L.append(f"  {a}")
            if f["rutas"]:
                L.append(f"  rutas: {', '.join(f['rutas'][:5])}")
            L.append("")
        for k, archivos in envs.items():
            L.append(f"CONFIG {k}")
            for a in archivos[:8]:
                L.append(f"  {a}")
            L.append("")

    if not L:
        return (f"Sin resultados para '{q}'.\n"
                "Probá un fragmento mas corto, o revisá si el indice esta al dia: "
                "python3 .mapa/buscar.py --leer")
    return "\n".join(L).rstrip()


def vecindario(m, ruta):
    idx = {a["ruta"]: a for a in m["archivos"]}
    a = idx.get(ruta) or next((v for k, v in idx.items() if k.endswith(ruta)), None)
    if not a:
        return f"No esta en el indice: {ruta}"
    L = [f"{a['ruta']}  ({a['lenguaje']}, {a['loc']} LOC, {a['commits']} commits)"]
    c = m["carpetas"].get(a["carpeta"], {})
    if c.get("resumen"):
        L.append(f"carpeta: {a['carpeta']}/ — {c['resumen']}")
    if c.get("estado_bitacora") == "desactualizada":
        L.append("AVISO: la bitacora de esta carpeta esta vencida.")
    L.append("")
    if a["simbolos"]:
        L.append("DEFINE")
        for s in a["simbolos"][:20]:
            L.append(f"  :{s['linea']}  {s['tipo']} {s['nombre']}")
        L.append("")
    if a["importa"]:
        L.append("IMPORTA")
        L += [f"  {r}" for r in a["importa"][:15]]
        L.append("")
    if a["importado_por"]:
        L.append("LO IMPORTAN")
        L += [f"  {r}" for r in a["importado_por"][:15]]
        L.append("")
    juntos = [cc for cc in m["co_cambio"] if a["ruta"] in (cc["a"], cc["b"])]
    if juntos:
        L.append("CAMBIA JUNTO CON")
        for cc in juntos[:8]:
            otro = cc["b"] if cc["a"] == a["ruta"] else cc["a"]
            L.append(f"  {otro}  ({cc['veces']} commits)")
        L.append("")
    return "\n".join(L).rstrip()


def carpeta(m, c):
    c = c.rstrip("/")
    info = m["carpetas"].get(c)
    if not info:
        cerca = [k for k in m["carpetas"] if c in k]
        return f"No indexada: {c}/" + (f"\n¿Quisiste decir? {', '.join(cerca[:5])}" if cerca else "")
    L = [f"{c}/  — {info['resumen'] or 'sin describir'}",
         f"{info['archivos']} archivos, {info['loc']:,} LOC, bitacora {info['estado_bitacora']}", ""]
    if info["pistas"]:
        L.append("BUSCAR ACA SI")
        L += [f"  {p}" for p in info["pistas"]]
        L.append("")
    L.append("ARCHIVOS")
    for a in sorted((a for a in m["archivos"] if a["carpeta"] == c),
                    key=lambda x: -x["loc"]):
        nombres = ", ".join(s["nombre"] for s in a["simbolos"][:6])
        L.append(f"  {a['ruta']}  ({a['loc']} LOC)  {nombres}")
    return "\n".join(L)


def por_donde_empezar(m):
    L = [f"{m['proyecto']} — {m['tamano']['archivos']} archivos, {m['tamano']['loc']:,} LOC",
         f"indexado {m['indexado']}", ""]
    if m["entrypoints"]:
        L.append("ENTRADAS: " + ", ".join(m["entrypoints"][:6]))
    centrales = sorted(m["archivos"], key=lambda a: (-len(a["importado_por"]), -a["loc"]))[:6]
    L.append("")
    L.append("ARCHIVOS CENTRALES (leer estos antes que ningun otro)")
    for a in centrales:
        L.append(f"  {a['ruta']}  {a['loc']} LOC, lo usan {len(a['importado_por'])}")
    venc = [c for c, i in m["carpetas"].items() if i["estado_bitacora"] != "al dia"
            and i["loc"] > 80]
    if venc:
        L.append("")
        L.append("AVISO — bitacoras vencidas o faltantes: " + ", ".join(venc))
        L.append("El mapa puede estar mintiendo sobre esas carpetas.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Consulta el indice del proyecto")
    ap.add_argument("termino", nargs="?")
    ap.add_argument("--archivo", "-a", help="vecindario de un archivo")
    ap.add_argument("--carpeta", "-c", help="inventario de una carpeta")
    ap.add_argument("--leer", action="store_true", help="por donde empezar")
    ap.add_argument("--todo", action="store_true", help="incluir fuentes y config")
    ap.add_argument("--mapa", help="ruta a mapa.json")
    args = ap.parse_args()

    m = cargar(args.mapa)
    if args.leer:
        print(por_donde_empezar(m))
    elif args.archivo:
        print(vecindario(m, args.archivo))
    elif args.carpeta:
        print(carpeta(m, args.carpeta))
    elif args.termino:
        print(buscar(m, args.termino, todo=args.todo))
    else:
        print(por_donde_empezar(m))


if __name__ == "__main__":
    main()
