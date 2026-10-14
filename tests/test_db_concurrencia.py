"""Que dos accesos simultáneos a la base no maten la app.

**El incidente (4/8/2026, producción).** Franco cargó un ajuste de tenencia y la
app murió entera con `sqlite3.OperationalError: database is locked`, con el
traceback apuntando a `init_db() -> _migrate()`. Tres defectos que se sumaron:

1. **`init_db()` corría en cada rerun de Streamlit**, o sea en cada click: el
   schema entero y las 13 migraciones, pidiendo el lock de escritura para hacer
   `ALTER TABLE` y `CREATE INDEX` que ya estaban hechos.
2. **`connect()` no configuraba `busy_timeout`**, así que ante un lock tomado
   SQLite fallaba en vez de esperar.
3. **el backup se sacaba con la conexión de escritura ya abierta**, lo que
   alargaba la ventana en la que todo esto podía chocar.

Guardar un dato no puede depender de que dos operaciones no se pisen.
"""

from __future__ import annotations

import ast
import sqlite3
import threading
from pathlib import Path

import pytest

from core.db import connect, init_db

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ruta(tmp_path, monkeypatch):
    p = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(p))
    init_db(p)
    return p


# ---------------------------------------------------------------------------
# 1. La conexión espera en vez de fallar
# ---------------------------------------------------------------------------

def test_connect_configura_busy_timeout(ruta):
    """Sin esto, un lock tomado por otra conexión es un error, no una espera."""
    conn = connect(ruta)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
    finally:
        conn.close()


def test_una_escritura_espera_a_la_otra_en_vez_de_reventar(ruta):
    """El corazón del incidente: dos escrituras concurrentes.

    Una conexión toma el lock de escritura y lo suelta a los 0,3 s. La otra
    tiene que **esperar y escribir**, no morir con `database is locked`.
    """
    lenta = connect(ruta)
    lenta.execute("BEGIN IMMEDIATE")
    lenta.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) "
        "VALUES (1, 'franco', 'Franco')"
    )

    resultado: dict = {}

    def escribir():
        otra = connect(ruta)
        try:
            otra.execute(
                "INSERT OR IGNORE INTO usuarios (id, username, fullname) "
                "VALUES (2, 'otro', 'Otro')"
            )
            resultado["ok"] = True
        except sqlite3.OperationalError as exc:
            resultado["error"] = str(exc)
        finally:
            otra.close()

    hilo = threading.Thread(target=escribir)
    hilo.start()
    threading.Event().wait(0.3)
    lenta.execute("COMMIT")
    hilo.join(timeout=15)
    lenta.close()

    assert "error" not in resultado, (
        f"la segunda escritura no esperó el lock: {resultado.get('error')}"
    )
    assert resultado.get("ok") is True


def test_migrar_mientras_otro_escribe_no_rompe(ruta):
    """La forma exacta del crash: el rerun corría las migraciones mientras
    otra conexión tenía la base tomada."""
    ocupada = connect(ruta)
    ocupada.execute("BEGIN IMMEDIATE")
    ocupada.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, fullname) "
        "VALUES (1, 'franco', 'Franco')"
    )

    fallo: dict = {}

    def migrar():
        try:
            init_db(ruta)
        except sqlite3.OperationalError as exc:
            fallo["error"] = str(exc)

    hilo = threading.Thread(target=migrar)
    hilo.start()
    threading.Event().wait(0.3)
    ocupada.execute("COMMIT")
    hilo.join(timeout=20)
    ocupada.close()

    assert "error" not in fallo, f"init_db murió con otra escritura viva: {fallo}"


# ---------------------------------------------------------------------------
# 2. Las migraciones corren una vez por proceso, no por click
# ---------------------------------------------------------------------------

def test_init_db_no_se_llama_en_cada_rerun():
    """`main()` se ejecuta entera en **cada** interacción de Streamlit. Si
    `init_db()` cuelga de ahí, cada click reejecuta las 13 migraciones y pide
    el lock de escritura sin necesidad.

    Se exige que la llamada esté detrás de una función cacheada por proceso.
    """
    arbol = ast.parse((RAIZ / "app.py").read_text(encoding="utf-8"))

    directas = [
        f for f in ast.walk(arbol)
        if isinstance(f, ast.FunctionDef) and f.name == "main"
        for n in ast.walk(f)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "init_db"
    ]
    assert not directas, (
        "main() llama init_db() directamente: eso corre las migraciones en "
        "cada rerun de Streamlit. Ponelo detrás de una función con "
        "@st.cache_resource."
    )

    cacheadas = [
        f for f in ast.walk(arbol)
        if isinstance(f, ast.FunctionDef)
        and any(
            isinstance(n, ast.Call) and getattr(n.func, "id", "") == "init_db"
            for n in ast.walk(f)
        )
        and any(
            "cache_resource" in ast.dump(d) for d in f.decorator_list
        )
    ]
    assert cacheadas, "nadie inicializa la DB detrás de @st.cache_resource"


# ---------------------------------------------------------------------------
# 3. El backup no se saca con la conexión de escritura abierta
# ---------------------------------------------------------------------------

def test_el_backup_no_va_dentro_de_una_conexion_abierta():
    """Copiar la base entera teniéndola ya tomada alarga la ventana de
    colisión. `backup_db()` va **antes** del `with connect()`, no adentro.

    El patrón nació en la vista de Cartera (retirada el 14/10/2026,
    ADR-0007). Ahora se revisa **todo `places/`**: mirar una lista fija de
    archivos fue la trampa 32 — hasta el 22/9/2026 el test miraba solo
    `view.py` y pasaba sin revisar nada.
    """
    fuentes = sorted(p for p in (RAIZ / "places").rglob("*.py")
                     if "__pycache__" not in p.parts)

    culpables = []
    llamadas_vistas = 0
    for fuente in fuentes:
        arbol = ast.parse(fuente.read_text(encoding="utf-8"))
        llamadas_vistas += sum(
            1 for n in ast.walk(arbol)
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "backup_db")
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.With):
                continue
            abre_conexion = any(
                isinstance(item.context_expr, ast.Call)
                and getattr(item.context_expr.func, "id", "") == "connect"
                for item in nodo.items
            )
            if not abre_conexion:
                continue
            for hijo in ast.walk(nodo):
                if (isinstance(hijo, ast.Call)
                        and getattr(hijo.func, "id", "") == "backup_db"):
                    culpables.append(f"{fuente.name}:{hijo.lineno}")

    # Si esto da 0, el test se quedó mirando archivos donde ya no está el
    # código: que falle en vez de pasar en blanco.
    assert llamadas_vistas > 0, "no encontré ningún backup_db(): ¿se mudó?"
    assert not culpables, (
        f"backup_db() se llama dentro de un `with connect()` en {culpables}. "
        f"Sacalo afuera: copiar la base con la conexión de escritura abierta "
        f"fue el `database is locked` del 4/8/2026."
    )
