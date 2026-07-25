"""Conexión a SQLite y schema.

Decisiones de diseño:

  * Usamos `sqlite3` de la stdlib (sin SQLAlchemy) para minimizar dependencias.
  * Modo WAL: permite lectores concurrentes mientras un proceso escribe.
    Importante para Streamlit, que mantiene la DB abierta en sesiones.
  * El saldo de Caja NO se almacena. Se calcula como acumulado:
        saldo_inicial + SUM(ingresos - pasivos) ORDER BY fecha, id
    Así la app es siempre auto-consistente: no hay forma de que la DB tenga
    un Caja "stale" porque no existe la columna.
  * El schema es idempotente: `init_db()` se puede correr N veces sin perder
    datos. Si una migración futura agrega columnas, lo manejamos con `ALTER TABLE`
    condicional (todavía no es necesario).
"""

from __future__ import annotations

import os
import sqlite3
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from core.auth.current_user import require_current_user_id

DEFAULT_DB_PATH = Path("data/finanzas.db")
BACKUP_DIR = Path("data/backups")


# ---------- Schema ----------

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS transacciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT NOT NULL,                    -- ISO 'YYYY-MM-DD'
    pasivos     REAL NOT NULL DEFAULT 0,          -- egresos (positivo); negativo = devolución
    ingresos    REAL NOT NULL DEFAULT 0,
    motivo      TEXT NOT NULL,
    comentario  TEXT,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transacciones_fecha
    ON transacciones(fecha);

CREATE INDEX IF NOT EXISTS idx_transacciones_motivo
    ON transacciones(motivo);

CREATE TABLE IF NOT EXISTS categorias (
    motivo  TEXT PRIMARY KEY,
    grupo   TEXT NOT NULL
        CHECK (grupo IN (
            'Ingreso',
            'Gasto Fijo',
            'Gasto Variable',
            'Inversion',
            'Flujo Capital',
            'Saldo Inicial',
            'Sin categorizar'
        ))
);

CREATE TABLE IF NOT EXISTS presupuesto (
    motivo         TEXT NOT NULL,
    anio           INTEGER NOT NULL,
    mes            INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    monto_previsto REAL NOT NULL,
    PRIMARY KEY (motivo, anio, mes)
);

CREATE TABLE IF NOT EXISTS configuracion (
    clave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);

-- Multi-usuario: por ahora hay un único usuario "local" con id=1.
-- En Fase 3, login con Streamlit-Authenticator setea current_user_id.
CREATE TABLE IF NOT EXISTS usuarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT UNIQUE NOT NULL,
    password_hash  TEXT,                          -- NULL hasta Fase 3
    fullname       TEXT,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


# Tablas que en Fase 3 van a filtrarse por current_user_id.
_USER_SCOPED_TABLES = ("transacciones", "categorias", "presupuesto", "configuracion")


def _migrate(conn: sqlite3.Connection) -> None:
    """Migraciones idempotentes. Se corren después de crear el schema base.

    Migraciones actuales:
      M1 (Fase 2): user_id en tablas de datos + usuario local.
      M2 (Fase 2b): columna `subcategoria` en `categorias` para jerarquía
                    macro/sub (ej: Inversion → Ahorro vs Activos financieros).
      M3–M8.5 (Fase 3/D2): reclasificaciones + scope por user_id y luego por
                    workspace_id (grupo familiar) — ver bloques abajo.
      M9 (Fase 3a): tablas de cartera nativa (aditivas, scope por user_id).
      M10 (Fase 3a): foto de tenencia del broker (los movimientos no alcanzan
                    para reconstruir la cartera: ver comentario del bloque).
    """
    cur = conn.cursor()
    cur.execute("BEGIN")
    try:
        # M1: user_id.
        for tabla in _USER_SCOPED_TABLES:
            cols = [
                r["name"] for r in cur.execute(f"PRAGMA table_info({tabla})")
            ]
            if "user_id" not in cols:
                cur.execute(
                    f"ALTER TABLE {tabla} ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"
                )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{tabla}_user ON {tabla}(user_id)"
            )
        cur.execute(
            "INSERT OR IGNORE INTO usuarios (id, username, fullname) "
            "VALUES (1, 'local', 'Usuario local')"
        )

        # M2: subcategoria en categorias.
        cat_cols = [r["name"] for r in cur.execute("PRAGMA table_info(categorias)")]
        if "subcategoria" not in cat_cols:
            cur.execute("ALTER TABLE categorias ADD COLUMN subcategoria TEXT")

        # M3: reclasificación de Fase 2b.
        #   * Compra Divisa: "Gasto Variable" → "Inversion / Ahorro y Resguardo".
        #   * Venta divisa: "Ingreso" sin subcat → "Ingreso / Desahorro".
        cur.execute(
            "UPDATE categorias SET grupo = 'Inversion', subcategoria = 'Ahorro y Resguardo' "
            "WHERE motivo = 'Compra Divisa' AND grupo = 'Gasto Variable'"
        )
        cur.execute(
            "UPDATE categorias SET subcategoria = 'Desahorro' "
            "WHERE motivo = 'Venta divisa' AND grupo = 'Ingreso' AND "
            "      (subcategoria IS NULL OR subcategoria = '')"
        )

        # M4 (Fase 3): PKs compuestas con user_id en categorias, presupuesto y
        # configuracion. SQLite no permite alterar PK, así que recreamos cada
        # tabla preservando los datos.
        def _pk_has_user_id(table: str) -> bool:
            info = cur.execute(f"PRAGMA table_info({table})").fetchall()
            return any(r["name"] == "user_id" and r["pk"] > 0 for r in info)

        def _es_post_d2(table: str) -> bool:
            """True si la tabla ya pasó por M8 (PK por workspace). M4 no debe
            tocarla: re-ejecutarse descartaría la columna workspace_id.
            (Incidente de producción 2026-07-17: M4 se re-disparó post-M8 y
            desvinculó todas las filas de sus workspaces.)"""
            info = cur.execute(f"PRAGMA table_info({table})").fetchall()
            return any(r["name"] == "workspace_id" for r in info)

        if not _pk_has_user_id("categorias") and not _es_post_d2("categorias"):
            cur.execute("""
                CREATE TABLE categorias_new (
                    motivo        TEXT NOT NULL,
                    grupo         TEXT NOT NULL CHECK (grupo IN (
                        'Ingreso', 'Gasto Fijo', 'Gasto Variable', 'Inversion',
                        'Flujo Capital', 'Saldo Inicial', 'Sin categorizar'
                    )),
                    subcategoria  TEXT,
                    user_id       INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (motivo, user_id)
                )
            """)
            cur.execute(
                "INSERT INTO categorias_new (motivo, grupo, subcategoria, user_id) "
                "SELECT motivo, grupo, subcategoria, user_id FROM categorias"
            )
            cur.execute("DROP TABLE categorias")
            cur.execute("ALTER TABLE categorias_new RENAME TO categorias")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_categorias_user ON categorias(user_id)"
            )

        if not _pk_has_user_id("presupuesto") and not _es_post_d2("presupuesto"):
            cur.execute("""
                CREATE TABLE presupuesto_new (
                    motivo         TEXT NOT NULL,
                    anio           INTEGER NOT NULL,
                    mes            INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
                    monto_previsto REAL NOT NULL,
                    user_id        INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (motivo, anio, mes, user_id)
                )
            """)
            cur.execute(
                "INSERT INTO presupuesto_new (motivo, anio, mes, monto_previsto, user_id) "
                "SELECT motivo, anio, mes, monto_previsto, user_id FROM presupuesto"
            )
            cur.execute("DROP TABLE presupuesto")
            cur.execute("ALTER TABLE presupuesto_new RENAME TO presupuesto")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_presupuesto_user ON presupuesto(user_id)"
            )

        if not _pk_has_user_id("configuracion") and not _es_post_d2("configuracion"):
            cur.execute("""
                CREATE TABLE configuracion_new (
                    clave   TEXT NOT NULL,
                    valor   TEXT NOT NULL,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (clave, user_id)
                )
            """)
            cur.execute(
                "INSERT INTO configuracion_new (clave, valor, user_id) "
                "SELECT clave, valor, user_id FROM configuracion"
            )
            cur.execute("DROP TABLE configuracion")
            cur.execute("ALTER TABLE configuracion_new RENAME TO configuracion")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_configuracion_user ON configuracion(user_id)"
            )

        # M5 (premortem #3, F5/R6): quitar el DEFAULT 1 de user_id en TODAS
        # las tablas de datos. Con DEFAULT 1, cualquier INSERT futuro que
        # olvide el user_id (un callback sin contextvar, un script, el
        # chatbot) deposita datos SILENCIOSAMENTE en la cuenta id=1 (Franco).
        # Sin default, ese INSERT lanza IntegrityError: falla ruidoso > fuga
        # silenciosa. SQLite no permite alterar el default → rebuild.
        def _user_id_con_default(table: str) -> bool:
            info = cur.execute(f"PRAGMA table_info({table})").fetchall()
            return any(
                r["name"] == "user_id" and r["dflt_value"] is not None
                for r in info
            )

        if _user_id_con_default("transacciones"):
            cur.execute("""
                CREATE TABLE transacciones_m5 (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha       TEXT NOT NULL,
                    pasivos     REAL NOT NULL DEFAULT 0,
                    ingresos    REAL NOT NULL DEFAULT 0,
                    motivo      TEXT NOT NULL,
                    comentario  TEXT,
                    creado_en   TEXT NOT NULL DEFAULT (datetime('now')),
                    user_id     INTEGER NOT NULL
                )
            """)
            cur.execute(
                "INSERT INTO transacciones_m5 "
                "(id, fecha, pasivos, ingresos, motivo, comentario, creado_en, user_id) "
                "SELECT id, fecha, pasivos, ingresos, motivo, comentario, creado_en, user_id "
                "FROM transacciones"
            )
            cur.execute("DROP TABLE transacciones")
            cur.execute("ALTER TABLE transacciones_m5 RENAME TO transacciones")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_transacciones_fecha ON transacciones(fecha)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_transacciones_motivo ON transacciones(motivo)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_transacciones_user ON transacciones(user_id)"
            )

        if _user_id_con_default("categorias"):
            cur.execute("""
                CREATE TABLE categorias_m5 (
                    motivo        TEXT NOT NULL,
                    grupo         TEXT NOT NULL CHECK (grupo IN (
                        'Ingreso', 'Gasto Fijo', 'Gasto Variable', 'Inversion',
                        'Flujo Capital', 'Saldo Inicial', 'Sin categorizar'
                    )),
                    subcategoria  TEXT,
                    user_id       INTEGER NOT NULL,
                    PRIMARY KEY (motivo, user_id)
                )
            """)
            cur.execute(
                "INSERT INTO categorias_m5 (motivo, grupo, subcategoria, user_id) "
                "SELECT motivo, grupo, subcategoria, user_id FROM categorias"
            )
            cur.execute("DROP TABLE categorias")
            cur.execute("ALTER TABLE categorias_m5 RENAME TO categorias")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_categorias_user ON categorias(user_id)"
            )

        if _user_id_con_default("presupuesto"):
            cur.execute("""
                CREATE TABLE presupuesto_m5 (
                    motivo         TEXT NOT NULL,
                    anio           INTEGER NOT NULL,
                    mes            INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
                    monto_previsto REAL NOT NULL,
                    user_id        INTEGER NOT NULL,
                    PRIMARY KEY (motivo, anio, mes, user_id)
                )
            """)
            cur.execute(
                "INSERT INTO presupuesto_m5 (motivo, anio, mes, monto_previsto, user_id) "
                "SELECT motivo, anio, mes, monto_previsto, user_id FROM presupuesto"
            )
            cur.execute("DROP TABLE presupuesto")
            cur.execute("ALTER TABLE presupuesto_m5 RENAME TO presupuesto")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_presupuesto_user ON presupuesto(user_id)"
            )

        if _user_id_con_default("configuracion"):
            cur.execute("""
                CREATE TABLE configuracion_m5 (
                    clave   TEXT NOT NULL,
                    valor   TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    PRIMARY KEY (clave, user_id)
                )
            """)
            cur.execute(
                "INSERT INTO configuracion_m5 (clave, valor, user_id) "
                "SELECT clave, valor, user_id FROM configuracion"
            )
            cur.execute("DROP TABLE configuracion")
            cur.execute("ALTER TABLE configuracion_m5 RENAME TO configuracion")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_configuracion_user ON configuracion(user_id)"
            )

        # ============================================================
        # M6 (premortem #5, SHADOW): infraestructura para workspaces.
        # ============================================================
        # Modelo: cada usuario tiene un workspace personal (kind='personal')
        # creado automáticamente acá. Puede tener además uno o más workspaces
        # familiares (kind='familiar') compartidos con otros usuarios vía
        # código de invitación.
        #
        # Esta migración SOLO agrega infraestructura (tablas + columnas +
        # backfill). Las queries del `core/` siguen filtrando por `user_id`
        # — el cutover a `workspace_id` viene en M7. Esto permite deployar el
        # cambio sin tocar comportamiento y validar que la data quedó bien
        # antes del cutover.
        #
        # Invariante de la migración (verificada en tests/test_premortem5.py):
        #   ∀ usuario u, ∀ tabla T ∈ {transacciones, categorias, presupuesto,
        #                              configuracion}:
        #     COUNT(T WHERE user_id = u) ==
        #     COUNT(T WHERE workspace_id = workspace_personal_de(u))

        # 6.1: tablas nuevas.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('personal', 'familiar')),
                nombre TEXT NOT NULL,
                invitation_code_hash TEXT,
                saldo_inicial REAL NOT NULL DEFAULT 0,
                fondo_usd REAL NOT NULL DEFAULT 0,
                creado_en TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin' CHECK(role IN ('admin', 'viewer')),
                member_label TEXT NOT NULL,
                joined_en TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (workspace_id, user_id),
                UNIQUE (workspace_id, member_label),
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_members_user ON workspace_members(user_id)"
        )

        # 6.2: columna workspace_id (nullable durante shadow) en las 4 tablas.
        for tabla in ("transacciones", "categorias", "presupuesto", "configuracion"):
            cols = [r["name"] for r in cur.execute(f"PRAGMA table_info({tabla})")]
            if "workspace_id" not in cols:
                cur.execute(
                    f"ALTER TABLE {tabla} ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{tabla}_workspace ON {tabla}(workspace_id)"
                )

        # 6.3: columna creado_por_member_label en transacciones (auditoría
        # cosmética: dentro de un workspace familiar, qué miembro la cargó).
        trans_cols = [r["name"] for r in cur.execute("PRAGMA table_info(transacciones)")]
        if "creado_por_member_label" not in trans_cols:
            cur.execute("ALTER TABLE transacciones ADD COLUMN creado_por_member_label TEXT")

        # 6.4: backfill — por cada usuario sin workspace personal, crear uno
        # con el saldo + fondo USD actuales, y asociarlo como admin con
        # member_label = fullname (o username si no hay fullname).
        usuarios_sin_personal = cur.execute("""
            SELECT u.id, u.username, u.fullname
            FROM usuarios u
            WHERE NOT EXISTS (
                SELECT 1 FROM workspace_members wm
                JOIN workspaces w ON w.id = wm.workspace_id
                WHERE wm.user_id = u.id AND w.kind = 'personal'
            )
        """).fetchall()

        for u in usuarios_sin_personal:
            row_saldo = cur.execute(
                "SELECT valor FROM configuracion "
                "WHERE clave = 'saldo_inicial_caja' AND user_id = ?",
                (u["id"],),
            ).fetchone()
            row_fondo = cur.execute(
                "SELECT valor FROM configuracion "
                "WHERE clave = 'fondo_emergencia_usd' AND user_id = ?",
                (u["id"],),
            ).fetchone()
            try:
                saldo = float(row_saldo["valor"]) if row_saldo else 0.0
            except (ValueError, TypeError):
                saldo = 0.0
            try:
                fondo = float(row_fondo["valor"]) if row_fondo else 0.0
            except (ValueError, TypeError):
                fondo = 0.0

            nombre_ws = f"Personal de {u['fullname'] or u['username']}"
            cur.execute(
                "INSERT INTO workspaces (kind, nombre, saldo_inicial, fondo_usd) "
                "VALUES ('personal', ?, ?, ?)",
                (nombre_ws, saldo, fondo),
            )
            ws_id = cur.lastrowid
            member_label = u["fullname"] or u["username"]
            cur.execute(
                "INSERT INTO workspace_members "
                "(workspace_id, user_id, role, member_label) "
                "VALUES (?, ?, 'admin', ?)",
                (ws_id, u["id"], member_label),
            )

            for tabla in ("transacciones", "categorias", "presupuesto", "configuracion"):
                cur.execute(
                    f"UPDATE {tabla} SET workspace_id = ? "
                    f"WHERE user_id = ? AND workspace_id IS NULL",
                    (ws_id, u["id"]),
                )

        # ============================================================
        # M7: subcategorías canonical para los motivos default.
        # ============================================================
        # Backfill idempotente: solo actualiza filas con subcategoria NULL
        # o vacía. NO pisa subcategorías puestas manualmente por el usuario.
        # Cubre los motivos que vienen en `DEFAULT_CATEGORIAS_NEW_USER` y
        # `DEFAULT_CATEGORIAS` de `core/categorizer.py`.
        _default_subcats = {
            "Haberes Fundación":  "Sueldo",
            "Haberes SBT":        "Sueldo",
            "Haberes UCEMA":      "Sueldo",
            "Sueldo":             "Sueldo",
            "Otros ingresos":     "Otros",
            "Venta divisa":       "Desahorro",
            "Retiro Inversiones": "Desahorro",
            "Auto":               "Movilidad",
            "Transportes":        "Movilidad",
            "Expensas":           "Hogar",
            "Servicios":          "Hogar",
            "Impuestos":          "Impuestos",
            "Pago tarjeta":       "Financiero",
            "Compras":            "Consumo",
            "Supermercado":       "Consumo",
            "Salidas":            "Ocio",
            "Viajes":             "Ocio",
            "Inversiones":        "Activos financieros",
            "Compra Divisa":      "Ahorro y Resguardo",
        }
        for motivo, subcat in _default_subcats.items():
            cur.execute(
                "UPDATE categorias SET subcategoria = ? "
                "WHERE motivo = ? "
                "AND (subcategoria IS NULL OR subcategoria = '')",
                (subcat, motivo),
            )

        # ============================================================
        # M8 (D2 cutover): PKs con scope de workspace.
        # ============================================================
        # El modelo D2 permite que un mismo usuario tenga el mismo motivo /
        # presupuesto / clave de config en su workspace personal Y en uno
        # familiar. Las PKs multi-usuario de M5 — (motivo, user_id), etc. —
        # lo impedían. Se reconstruyen las 3 tablas (patrón de M5) con PK
        # por workspace. `user_id` se conserva como autor de la fila.
        # Idempotente: solo si la PK vieja sigue vigente. Corre después del
        # backfill M6, así todas las filas ya tienen workspace_id.

        # --- M8.5: reparación de filas desvinculadas -----------------
        # Si alguna fila del dominio quedó con workspace_id NULL (incidente
        # del 2026-07-17: M4 re-disparada post-M8 descartó la columna), se
        # re-vincula al workspace personal de su usuario. Si en el medio la
        # app escribió una fila duplicada scoped (defaults de onboarding),
        # gana la fila ORIGINAL (la NULL: trae los datos históricos reales).
        # Idempotente: sin filas NULL no hace nada.
        personales = {
            r["user_id"]: r["ws"]
            for r in cur.execute("""
                SELECT wm.user_id AS user_id, w.id AS ws
                FROM workspace_members wm
                JOIN workspaces w ON w.id = wm.workspace_id
                WHERE w.kind = 'personal'
            """)
        }
        for uid_rep, ws_rep in personales.items():
            # configuracion: borrar el duplicado scoped, conservar el original.
            cur.execute("""
                DELETE FROM configuracion WHERE workspace_id = ? AND clave IN (
                    SELECT clave FROM configuracion
                    WHERE user_id = ? AND workspace_id IS NULL
                )""", (ws_rep, uid_rep))
            # categorias: ídem por motivo.
            cur.execute("""
                DELETE FROM categorias WHERE workspace_id = ? AND motivo IN (
                    SELECT motivo FROM categorias
                    WHERE user_id = ? AND workspace_id IS NULL
                )""", (ws_rep, uid_rep))
            # presupuesto: ídem por (motivo, anio, mes).
            cur.execute("""
                DELETE FROM presupuesto AS p WHERE p.workspace_id = ? AND EXISTS (
                    SELECT 1 FROM presupuesto q
                    WHERE q.user_id = ? AND q.workspace_id IS NULL
                      AND q.motivo = p.motivo AND q.anio = p.anio AND q.mes = p.mes
                )""", (ws_rep, uid_rep))
            for tabla in ("transacciones", "categorias", "presupuesto", "configuracion"):
                cur.execute(
                    f"UPDATE {tabla} SET workspace_id = ? "
                    f"WHERE user_id = ? AND workspace_id IS NULL",
                    (ws_rep, uid_rep),
                )

        def _sql_de(tabla: str) -> str:
            row = cur.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (tabla,),
            ).fetchone()
            return (row["sql"] or "") if row else ""

        if "workspace_id" not in _sql_de("categorias").split("PRIMARY KEY")[-1]:
            cur.execute("""
                CREATE TABLE categorias_m8 (
                    motivo        TEXT NOT NULL,
                    grupo         TEXT NOT NULL CHECK (grupo IN (
                        'Ingreso', 'Gasto Fijo', 'Gasto Variable', 'Inversion',
                        'Flujo Capital', 'Saldo Inicial', 'Sin categorizar'
                    )),
                    subcategoria  TEXT,
                    user_id       INTEGER NOT NULL,
                    workspace_id  INTEGER REFERENCES workspaces(id),
                    PRIMARY KEY (motivo, workspace_id)
                )
            """)
            cur.execute(
                "INSERT INTO categorias_m8 (motivo, grupo, subcategoria, user_id, workspace_id) "
                "SELECT motivo, grupo, subcategoria, user_id, workspace_id FROM categorias"
            )
            cur.execute("DROP TABLE categorias")
            cur.execute("ALTER TABLE categorias_m8 RENAME TO categorias")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_categorias_user ON categorias(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_categorias_workspace ON categorias(workspace_id)")

        if "workspace_id" not in _sql_de("presupuesto").split("PRIMARY KEY")[-1]:
            cur.execute("""
                CREATE TABLE presupuesto_m8 (
                    motivo         TEXT NOT NULL,
                    anio           INTEGER NOT NULL,
                    mes            INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
                    monto_previsto REAL NOT NULL,
                    user_id        INTEGER NOT NULL,
                    workspace_id   INTEGER REFERENCES workspaces(id),
                    PRIMARY KEY (motivo, anio, mes, workspace_id)
                )
            """)
            cur.execute(
                "INSERT INTO presupuesto_m8 (motivo, anio, mes, monto_previsto, user_id, workspace_id) "
                "SELECT motivo, anio, mes, monto_previsto, user_id, workspace_id FROM presupuesto"
            )
            cur.execute("DROP TABLE presupuesto")
            cur.execute("ALTER TABLE presupuesto_m8 RENAME TO presupuesto")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_presupuesto_user ON presupuesto(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_presupuesto_workspace ON presupuesto(workspace_id)")

        if "workspace_id" not in _sql_de("configuracion").split("PRIMARY KEY")[-1]:
            cur.execute("""
                CREATE TABLE configuracion_m8 (
                    clave        TEXT NOT NULL,
                    valor        TEXT NOT NULL,
                    user_id      INTEGER NOT NULL,
                    workspace_id INTEGER REFERENCES workspaces(id),
                    PRIMARY KEY (clave, workspace_id)
                )
            """)
            cur.execute(
                "INSERT INTO configuracion_m8 (clave, valor, user_id, workspace_id) "
                "SELECT clave, valor, user_id, workspace_id FROM configuracion"
            )
            cur.execute("DROP TABLE configuracion")
            cur.execute("ALTER TABLE configuracion_m8 RENAME TO configuracion")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_configuracion_user ON configuracion(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_configuracion_workspace ON configuracion(workspace_id)")

        # ============================================================
        # M9 (Fase 3a): Cartera nativa — tablas propias, scope por usuario.
        # ============================================================
        # La cartera de inversiones es PERSONAL de cada usuario (no se comparte
        # como los gastos familiares del modelo D2): se scopea por `user_id`,
        # no por `workspace_id`. Hoy solo la usa Franco; el esquema es
        # generalizable a otros usuarios sin cambios.
        #
        # Estas 3 tablas son ADITIVAS: `CREATE TABLE IF NOT EXISTS` idempotente,
        # no tocan ninguna tabla de finanzas ni de workspaces → migración de
        # bajo riesgo (a diferencia de M4–M8, que reconstruían tablas).
        #
        #   * cartera_instrumentos  — mapa de tickers (equivalente a Config!G:N
        #     del Excel): base ↔ variante USD, categoría de activo, panel de
        #     precios, moneda de cotización, divisor.
        #   * cartera_movimientos   — un movimiento parseado por fila (salida
        #     del parser de `places/inversiones/cartera/parser.py`). `tc_mep`
        #     queda NULL hasta que market_data (paso 3) congele el MEP histórico
        #     de cada fecha. `hash_dedupe` + UNIQUE hace idempotente la carga
        #     recurrente (re-importar el mismo export no duplica).
        #   * cartera_precios_cache — precios de valuación (auto + override),
        #     con fecha y fuente; base para "precio automático con caché".
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_instrumentos (
                ticker            TEXT NOT NULL,
                user_id           INTEGER NOT NULL,
                ticker_usd        TEXT,
                descripcion       TEXT,
                categoria_activo  TEXT,
                panel_precio      TEXT,
                moneda_cotiz      TEXT NOT NULL DEFAULT 'ARS',
                divisor_usd       REAL,
                activo            INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (ticker, user_id)
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cartera_instr_user "
            "ON cartera_instrumentos(user_id)"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_movimientos (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL,
                fecha_concertacion  TEXT NOT NULL,
                fecha_liquidacion   TEXT,
                categoria           TEXT NOT NULL,
                descripcion         TEXT NOT NULL,
                monto               REAL NOT NULL DEFAULT 0,
                cantidad            REAL NOT NULL DEFAULT 0,
                precio              REAL NOT NULL DEFAULT 0,
                moneda              TEXT NOT NULL,
                ticker_crudo        TEXT,
                ticker_base         TEXT,
                operacion_original  TEXT,
                formato             TEXT,
                es_instrumento      INTEGER NOT NULL DEFAULT 0,
                es_espejo           INTEGER NOT NULL DEFAULT 0,
                es_saldo_inicial    INTEGER NOT NULL DEFAULT 0,
                precio_normalizado  REAL,
                tc_mep              REAL,
                hash_dedupe         TEXT NOT NULL,
                creado_en           TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (user_id, hash_dedupe)
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cartera_mov_user "
            "ON cartera_movimientos(user_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cartera_mov_ticker "
            "ON cartera_movimientos(user_id, ticker_base)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cartera_mov_fecha "
            "ON cartera_movimientos(fecha_concertacion)"
        )
        # ============================================================
        # M10 (Fase 3a): foto de tenencia del broker.
        # ============================================================
        # El export de movimientos NO alcanza para reconstruir la cartera:
        #   * ajustes de ratio de CEDEAR (SPY) no generan movimiento;
        #   * pagarés/cheques ("Compra cheque") traen el monto pero NO la
        #     cantidad — en la cartera de Franco eso era el 35% del total.
        # Por eso se guarda la tenencia informada por el broker: los
        # movimientos aportan el histórico (costos, aportes, rendimiento) y
        # esta tabla la foto actual (cantidades y precios de referencia).
        # La diferencia entre ambas ES la reconciliación contra el custodio.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_tenencia (
                user_id          INTEGER NOT NULL,
                fecha_valuacion  TEXT NOT NULL,
                ticker           TEXT NOT NULL,
                nombre           TEXT,
                cantidad         REAL NOT NULL DEFAULT 0,
                precio           REAL,
                moneda           TEXT NOT NULL DEFAULT 'ARS',
                tipo_activo      TEXT,
                costo_ppc        REAL,
                PRIMARY KEY (user_id, fecha_valuacion, ticker)
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cartera_tenencia_user "
            "ON cartera_tenencia(user_id, fecha_valuacion)"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_tenencia_meta (
                user_id          INTEGER NOT NULL,
                fecha_valuacion  TEXT NOT NULL,
                mep              REAL,
                ccl              REAL,
                efectivo_ars     REAL NOT NULL DEFAULT 0,
                efectivo_usd     REAL NOT NULL DEFAULT 0,
                importado_en     TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, fecha_valuacion)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_precios_cache (
                ticker          TEXT NOT NULL,
                fecha           TEXT NOT NULL,
                precio          REAL NOT NULL,
                moneda          TEXT NOT NULL DEFAULT 'ARS',
                fuente          TEXT,
                es_override     INTEGER NOT NULL DEFAULT 0,
                actualizado_en  TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (ticker, fecha, moneda)
            )
        """)

        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise


# ============================================================
#  Conexión y init
# ============================================================

def get_db_path() -> Path:
    """Ruta a la DB activa: respeta `DB_PATH` (env) o usa el default."""
    return Path(os.environ.get("DB_PATH", str(DEFAULT_DB_PATH)))


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Abrir una conexión SQLite con row_factory, WAL y FKs activos.

    `isolation_level=None` deshabilita el autocommit implícito del driver:
    así los `BEGIN`/`COMMIT`/`ROLLBACK` que escribimos en el código (ej.
    `core/ingest.py`, `_migrate()`) funcionan tal como están escritos. Sin
    esto, el driver intercala transacciones implícitas y rompe el control
    manual.
    """
    path = Path(db_path) if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Crear schema base si no existe + correr migraciones idempotentes."""
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


def _resolve_user_id(user_id: Optional[int]) -> int:
    """Resuelve user_id explícito o lo lee del contextvar."""
    return user_id if user_id is not None else require_current_user_id()


def set_config(
    conn: sqlite3.Connection,
    clave: str,
    valor: str,
    user_id: Optional[int] = None,
    workspace_id: Optional[int] = None,
) -> None:
    """UPSERT en `configuracion` con scope de workspace (D2).

    `workspace_id` explícito manda; si no, se resuelve del contexto activo
    (fallback: workspace personal del usuario). `user_id` queda como autor.

    NO hace commit — eso queda a cargo del caller. Importante para no romper
    transacciones externas (caso típico: `core/ingest.py` que hace BEGIN/COMMIT
    explícito alrededor del bulk insert + set_config).
    El context manager de `connect()` y los `with conn:` commitean al salir.
    """
    from core.workspaces import resolve_workspace_id  # import diferido (evita ciclos)

    uid = _resolve_user_id(user_id)
    wid = workspace_id if workspace_id is not None else resolve_workspace_id(conn, uid)
    conn.execute(
        "INSERT INTO configuracion (clave, valor, user_id, workspace_id) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(clave, workspace_id) DO UPDATE SET valor = excluded.valor",
        (clave, str(valor), uid, wid),
    )


def get_config(
    conn: sqlite3.Connection,
    clave: str,
    default: str = "",
    user_id: Optional[int] = None,
    workspace_id: Optional[int] = None,
) -> str:
    """Lee `clave` en el workspace activo. Devuelve `default` si no existe."""
    from core.workspaces import resolve_workspace_id  # import diferido (evita ciclos)

    wid = workspace_id if workspace_id is not None else resolve_workspace_id(
        conn, _resolve_user_id(user_id)
    )
    row = conn.execute(
        "SELECT valor FROM configuracion WHERE clave = ? AND workspace_id = ?",
        (clave, wid),
    ).fetchone()
    return row["valor"] if row else default


def backup_db(
    conn: Optional[sqlite3.Connection] = None, db_path: Optional[Path] = None
) -> Path:
    """Copia online de la DB a `BACKUP_DIR/finanzas-YYYYMMDD-HHMMSS.db`.

    `conn` es OPCIONAL: los call sites de core/ (transactions, budget,
    categorias) llaman `backup_db()` sin argumentos y acá se abre una
    conexión propia a la DB activa.

    Regresión 2/7/2026: al reconstruir este módulo tras la corrupción de
    OneDrive, la firma quedó exigiendo `conn` y TODA escritura en producción
    crasheaba con TypeError (y sin backup). Cubierto por
    tests/test_backup_regresion.py — no volver a hacer `conn` obligatorio.
    """
    backup_dir = BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"finanzas-{ts}.db"
    conn_propia = conn is None
    if conn_propia:
        conn = sqlite3.connect(db_path if db_path is not None else get_db_path())
    backup_conn = sqlite3.connect(dest)
    try:
        conn.backup(backup_conn)
    finally:
        backup_conn.close()
        if conn_propia:
            conn.close()
    retention = int(os.environ.get("BACKUP_RETENTION", "30"))
    _purge_old_backups(retention_days=retention, keep_recent=10)
    return dest


def _purge_old_backups(
    retention_days: int = 30, keep_recent: int = 10
) -> None:
    """Conserva el ULTIMO backup de cada dia dentro de retention_days +
    los keep_recent absolutamente mas recientes.

    Usa el `BACKUP_DIR` del módulo (monkeypatcheable por los tests).
    """
    backup_dir = BACKUP_DIR
    if not backup_dir.exists():
        return
    files = sorted(backup_dir.glob("finanzas-*.db"), key=lambda p: p.name)
    if not files:
        return

    def _fecha_de(p: Path) -> Optional[str]:
        stem = p.stem
        partes = stem.split("-")
        if len(partes) < 3:
            return None
        return partes[1]

    a_preservar = set(files[-keep_recent:])
    hoy = datetime.now().date()
    ventana = {
        (hoy - timedelta(days=i)).strftime("%Y%m%d")
        for i in range(retention_days + 1)
    }
    por_dia = {}
    for p in files:
        fecha = _fecha_de(p)
        if fecha is None or fecha not in ventana:
            continue
        prev = por_dia.get(fecha)
        if prev is None or p.name > prev.name:
            por_dia[fecha] = p
    a_preservar.update(por_dia.values())

    for p in files:
        if p not in a_preservar:
            try:
                p.unlink()
            except OSError:
                pass
