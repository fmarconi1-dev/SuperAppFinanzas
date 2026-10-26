"""Base sintética para medir: 1 usuario, ~4 años de movimientos (~5.000 filas)."""
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(sys.argv[1])
RUTA = Path(sys.argv[2])
sys.path.insert(0, str(REPO))
os.chdir(REPO)
os.environ["DB_PATH"] = str(RUTA)
if RUTA.exists():
    RUTA.unlink()

from core import db as core_db  # noqa: E402
core_db.BACKUP_DIR = RUTA.parent / "backups"
from core.db import connect, init_db  # noqa: E402
from places.finanzas.core.ingest import init_categorias, DEFAULT_CATEGORIAS  # noqa: E402
from places.finanzas.core.transactions import insertar_sin_backup  # noqa: E402

random.seed(42)
init_db(RUTA)
with connect(RUTA) as conn:
    conn.execute("UPDATE usuarios SET username='franco', fullname='Franco' WHERE id=1")
    init_categorias(conn, user_id=1)
    motivos = list(DEFAULT_CATEGORIAS)
    ingresos = [m for m in motivos if m.lower().startswith("haberes")] or motivos[:1]
    gastos = [m for m in motivos if m not in ingresos]
    hoy = date.today()
    d = hoy - timedelta(days=4 * 365)
    n = 0
    conn.execute("BEGIN")
    while d <= hoy:
        if d.day == 1:
            for m in ingresos:
                insertar_sin_backup(conn, d, m, ingresos=random.randint(500_000, 1_500_000), user_id=1)
                n += 1
        for _ in range(random.randint(1, 6)):
            insertar_sin_backup(conn, d, random.choice(gastos),
                                pasivos=random.randint(1_000, 150_000), user_id=1)
            n += 1
        d += timedelta(days=1)
    conn.execute("COMMIT")
print("filas", n, "tamaño KB", RUTA.stat().st_size // 1024)
