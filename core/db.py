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
    datos. Las migraciones de esquema detectan su propio estado (columnas,
    PKs) y las **reparaciones de datos únicas** se marcan con
    `PRAGMA user_version` (ver `_NIVEL_REPARACIONES`).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from core.context import require_current_user_id

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

#: Nivel de las **reparaciones de datos únicas** (M3, M7 y M8.5), guardado en
#: `PRAGMA user_version`. No son migraciones de esquema: son `UPDATE`/`DELETE`
#: sobre filas, y hasta el 22/9/2026 corrían **en cada arranque** —o sea en
#: cada deploy y cada vez que Fly despertaba la máquina—:
#:
#: * M3 volvía a pasar "Compra Divisa" a Inversión aunque el usuario la
#:   hubiera reclasificado a propósito;
#: * M7 volvía a llenar subcategorías vaciadas a propósito;
#: * M8.5, la reparación del incidente del 17/7, **borraba** la fila correcta
#:   de un espacio si aparecía otra huérfana (`workspace_id NULL`) y la mandaba
#:   al espacio personal aunque fuera del familiar.
#:
#: Es la misma lección del incidente de M4: el guard de una migración vieja
#: tiene que seguir siendo correcto frente al esquema **y los datos** de hoy.
#: Con `user_version >= 1` ya no corren. `user_version` es del header de
#: SQLite: no es una tabla ni una migración nueva (M16 quedó liberada por
#: ADR-0009). Si hace falta otra reparación única, sube a 2.
_NIVEL_REPARACIONES = 1


def _migrate(conn: sqlite3.Connection) -> None:
    """Migraciones idempotentes. Se corren después de crear el schema base.

    Migraciones actuales (el detalle y el porqué, en el comentario de cada
    bloque):
      M1  (Fase 2)  user_id en tablas de datos + usuario local.
      M2  (Fase 2b) columna `subcategoria` en `categorias`.
      M3            reclasificación de Compra/Venta divisa — **única**.
      M4  (Fase 3)  PKs con user_id (guard post-D2 desde el incidente 17/7).
      M5            sin DEFAULT en user_id (premortem #3) — guard post-D2.
      M6            workspaces + backfill (D2 shadow).
      M7            subcategorías de los motivos default — **única**.
      M8 / M8.5     PKs por workspace (D2) + reparación del 17/7 — M8.5 **única**.
      M9–M10 (3a)   cartera nativa + foto de tenencia del broker.
      M11 (3a)      tasa devengada para pagarés.
      M12 (3b)      caché de sectores.
      M13–M15 (4)   ajustes de tenencia, vencimientos a mano, cronogramas.
      M17 (A)       mensajes y estado del canal de WhatsApp (M16: reservada, ADR-0006).
      M18 (B)       cola de salida de WhatsApp (ventana de 24 h).
      M19–M20 (D)   lotes con su deshacer, y el bruto de los gastos con cuenta
                    (M16 queda liberada, ADR-0009).
      M21 (D)       conciliación: filas del banco, emparejamientos, reglas
                    aprendidas y saldos declarados.

    "Única" = reparación de datos que corre una sola vez por base, marcada con
    `PRAGMA user_version` (ver `_NIVEL_REPARACIONES`).
    """
    cur = conn.cursor()
    # BEGIN **IMMEDIATE**, no diferido. Con `BEGIN` a secas SQLite abre la
    # transacción en modo lectura y pide el lock de escritura recién en la
    # primera escritura — y en ese momento **no aplica `busy_timeout`**:
    # devuelve `SQLITE_BUSY` al instante, porque esperar con lecturas ya hechas
    # podría terminar en deadlock. Resultado: `database is locked` aunque la
    # conexión estuviera configurada para esperar 30 s.
    # Con `IMMEDIATE` el lock se toma al abrir, que es donde el timeout sí
    # cuenta, y la migración espera su turno en vez de matar la app.
    # (Incidente del 4/8/2026: se cargaba un ajuste y la app moría entera.)
    cur.execute("BEGIN IMMEDIATE")
    try:
        reparaciones_pendientes = (
            cur.execute("PRAGMA user_version").fetchone()[0] < _NIVEL_REPARACIONES
        )

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

        # M3: reclasificación de Fase 2b. **Única** (ver _NIVEL_REPARACIONES):
        # corrida en cada arranque, pisaba la reclasificación que hiciera el
        # usuario después.
        #   * Compra Divisa: "Gasto Variable" → "Inversion / Ahorro y Resguardo".
        #   * Venta divisa: "Ingreso" sin subcat → "Ingreso / Desahorro".
        if reparaciones_pendientes:
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
        # ⚠️ Guard post-D2 (22/9/2026): mismo patrón de falla que M4. El
        # rebuild de M5 no conoce `workspace_id` ni `creado_por_member_label`;
        # si algún día se re-disparara sobre una tabla post-M8, las
        # descartaría y desvincularía los datos como el 17/7.
        def _user_id_con_default(table: str) -> bool:
            info = cur.execute(f"PRAGMA table_info({table})").fetchall()
            return any(
                r["name"] == "user_id" and r["dflt_value"] is not None
                for r in info
            )

        if _user_id_con_default("transacciones") and not _es_post_d2("transacciones"):
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

        if _user_id_con_default("categorias") and not _es_post_d2("categorias"):
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

        if _user_id_con_default("presupuesto") and not _es_post_d2("presupuesto"):
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

        if _user_id_con_default("configuracion") and not _es_post_d2("configuracion"):
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
        # Backfill: solo actualiza filas con subcategoria NULL o vacía. NO
        # pisa subcategorías puestas manualmente por el usuario — pero sí
        # rellenaba las que el usuario **vació** a propósito, en cada
        # arranque. Por eso es **única** (ver _NIVEL_REPARACIONES): los
        # defaults de hoy (`DEFAULT_CATEGORIAS*` de `categorizer.py`) ya traen
        # la subcategoría puesta.
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
        for motivo, subcat in (_default_subcats.items()
                               if reparaciones_pendientes else ()):
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
        # **Única** (ver _NIVEL_REPARACIONES): la regla "gana la NULL" era
        # cierta para el incidente del 17/7, no como regla permanente. Una fila
        # NULL que aparezca hoy es un bug nuevo, no un dato histórico: borrar
        # por ella la fila buena del espacio sería repetir el incidente.
        personales = {
            r["user_id"]: r["ws"]
            for r in cur.execute("""
                SELECT wm.user_id AS user_id, w.id AS ws
                FROM workspace_members wm
                JOIN workspaces w ON w.id = wm.workspace_id
                WHERE w.kind = 'personal'
            """)
        } if reparaciones_pendientes else {}
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
        #     del parser de la cartera, retirada el 14/10/2026 — ADR-0007; la
        #     tabla queda con los datos, quieta). `tc_mep`
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

        # ============================================================
        # M11 (Fase 3a): tasa de devengamiento para instrumentos sin mercado.
        # ============================================================
        # Los pagarés/cheques de pago diferido no cotizan: rinden una tasa
        # pactada (el de Franco, 10% anual en USD). El "precio actual" que
        # informa el broker no refleja ese devengamiento — al 30/7/2026 daba
        # +7,7% en 24 días, o sea ~200% anualizado. Con la tasa guardada, la
        # app los valúa devengando desde la compra, que es lo correcto.
        cols_instr = [
            r["name"] for r in cur.execute("PRAGMA table_info(cartera_instrumentos)")
        ]
        if cols_instr and "tasa_anual_usd" not in cols_instr:
            cur.execute(
                "ALTER TABLE cartera_instrumentos ADD COLUMN tasa_anual_usd REAL"
            )

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

        # ============================================================
        # M12 (Fase 3b): caché de sector e industria por ticker.
        # ============================================================
        # El sector es un dato del mundo, no de la cartera: se resuelve una
        # vez por ticker y se guarda. Tabla aparte (y no una columna en
        # `cartera_instrumentos`) por dos motivos: los instrumentos se
        # re-escriben en cada import desde la hoja Config y pisarían el dato,
        # y así se replica el patrón ya probado de `cartera_precios_cache`
        # (fuente + `es_override`, donde el override manual gana siempre).
        # Sin `user_id`: que NVDA sea Technology no depende de quién la tenga.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_sectores (
                ticker          TEXT PRIMARY KEY,
                sector          TEXT,
                industria       TEXT,
                tipo            TEXT,
                nombre          TEXT,
                fuente          TEXT,
                es_override     INTEGER NOT NULL DEFAULT 0,
                actualizado_en  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # ============================================================
        # M13 (Fase 4): ajustes de tenencia que el broker no informa.
        # ============================================================
        # El export de movimientos no alcanza para reconstruir la cartera
        # (trampa #4): los splits y los ajustes de ratio de CEDEAR no generan
        # movimiento, y los papeles que ya tenías antes de que arranque el
        # registro no tienen compra. Sin esto el ledger cierra esas ventas
        # "descubiertas", sin costo, y el rendimiento sale disparatado.
        #
        # **Tabla aparte de `cartera_movimientos` a propósito.** Esa tabla es
        # lo que dice el broker; ésta es lo que vos sabés que el broker no
        # informa. Mezclarlas rompería el sentido de la reconciliación (su
        # diferencia *es* el chequeo) y los ajustes se perderían el día que
        # se borren los movimientos para reimportar de cero.
        #
        # `costo_ars` es el que manda la identidad contable: el capital
        # aportado suma este costo como depósito sintético, porque esa plata
        # entró a la cartera antes del registro. Costo 0 (un split, un cupón
        # gratis) no mueve capital y por eso no genera depósito.
        #
        # `estimado` marca los costos deducidos de memoria o despejados de un
        # rendimiento recordado. Un número estimado no se puede distinguir
        # después de uno verificado si no se guarda que lo era.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_ajustes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                fecha       TEXT NOT NULL,
                ticker      TEXT NOT NULL,
                tipo        TEXT NOT NULL,
                cantidad    REAL NOT NULL DEFAULT 0,
                costo_ars   REAL NOT NULL DEFAULT 0,
                costo_usd   REAL,
                estimado    INTEGER NOT NULL DEFAULT 0,
                nota        TEXT,
                creado_en   TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (user_id, fecha, ticker, tipo, cantidad, costo_ars)
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cartera_ajustes_user "
            "ON cartera_ajustes(user_id, ticker)"
        )

        # ============================================================
        # M14 (Fase 4): vencimientos fijados a mano.
        # ============================================================
        # La fecha de vencimiento se lee de la descripción del instrumento
        # ("Bono Tesoro Nacional Vto. 30/11/2029"), pero no todas la traen: el
        # pagaré no tiene descripción con fecha y algunos bonos dicen solo el
        # año. Esta tabla guarda las que se corrigen a mano.
        #
        # Tabla aparte y no una columna en `cartera_instrumentos` por el mismo
        # motivo que `cartera_sectores`: esa tabla se **re-escribe en cada
        # import** desde la hoja Config y pisaría el dato. Sin `user_id`: que
        # el AN29 venza el 30/11/2029 no depende de quién lo tenga.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_vencimientos (
                ticker          TEXT PRIMARY KEY,
                fecha           TEXT NOT NULL,
                fuente          TEXT,
                es_override     INTEGER NOT NULL DEFAULT 0,
                actualizado_en  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # ============================================================
        # M15 (Fase 4): cronogramas de pago de la renta fija.
        # ============================================================
        # Cada cupón y cada amortización de un bono, con su fecha. Es lo que
        # destraba el calendario de cobros, la TIR esperada y la duration.
        #
        # **La caché no es una optimización: es el uso correcto de la fuente.**
        # El plan gratuito de Docta da 15 requests por día, y alcanza porque un
        # cronograma es dato **estático** — el AE38 va a pagar lo mismo en las
        # mismas fechas el mes que viene que hoy. Se baja una vez por bono y
        # queda acá. Verificado el 5/8/2026: 34 flujos para el AE38.
        #
        # Los importes se guardan **por 100 nominales**, que es como los sirve
        # la API. Escalar a la tenencia real es una multiplicación al leer, y
        # así el mismo cronograma sirve aunque cambie la cantidad.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_cronogramas (
                ticker          TEXT NOT NULL,
                fecha_pago      TEXT NOT NULL,
                capital         REAL NOT NULL DEFAULT 0,
                interes         REAL NOT NULL DEFAULT 0,
                total           REAL NOT NULL DEFAULT 0,
                residual        REAL,
                PRIMARY KEY (ticker, fecha_pago)
            )
        """)
        # Estado por ticker, **incluida la caché negativa**: sin esto, un
        # instrumento que la fuente no tiene —el pagaré del MAV— se
        # consultaría en cada carga de la pantalla, para siempre, gastando la
        # cuota diaria a lo pavo. Es la misma lección de `cartera_sectores`.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cartera_cronogramas_meta (
                ticker          TEXT PRIMARY KEY,
                clase           TEXT,
                nominales_base  REAL NOT NULL DEFAULT 100,
                fuente          TEXT,
                n_flujos        INTEGER NOT NULL DEFAULT 0,
                actualizado_en  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # ============================================================
        # M17 (Fase A, ADR-0008): mensajes de WhatsApp.
        # ============================================================
        # (M16 estaba reservada para las cuentas de ADR-0006; ADR-0009 la liberó.)
        #
        # `whatsapp_mensajes` es el **dedupe**: Meta reintenta un webhook
        # hasta 7 días si no recibe 200 a tiempo (un arranque en frío de Fly
        # alcanza), y sin esto un gasto se cargaría dos veces. La PK es el id
        # que Meta le da al mensaje (wamid). También es lo que usa `deshacer`
        # para saber qué transacciones entraron por WhatsApp.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS whatsapp_mensajes (
                wamid           TEXT PRIMARY KEY,
                recibido_en     TEXT NOT NULL,
                remitente       TEXT NOT NULL,
                texto           TEXT,
                transaccion_id  INTEGER REFERENCES transacciones(id) ON DELETE SET NULL,
                resultado       TEXT NOT NULL DEFAULT 'recibido'
            )
        """)
        # Estado chico del canal, clave → valor: `ultimo_entrante` (la Fase B
        # lo usa para saber si la ventana de 24 h de Meta está abierta) y
        # `pendiente` (un gasto esperando un "sí" o un "no").
        cur.execute("""
            CREATE TABLE IF NOT EXISTS whatsapp_estado (
                clave           TEXT PRIMARY KEY,
                valor           TEXT NOT NULL,
                actualizado_en  TEXT NOT NULL
            )
        """)

        # ============================================================
        # M18 (Fase B, ADR-0008): cola de salida de WhatsApp.
        # ============================================================
        # Lo que el bot manda por su cuenta (los briefings de Gemini) solo es
        # gratis dentro de la ventana de 24 h desde el último mensaje de
        # Franco. Fuera de ella no hay camino gratis: el mensaje queda acá con
        # `enviado_en` NULL y sale cuando Franco vuelve a escribir.
        # `id_origen` (el id del mail en Gmail) es el dedupe: si el Apps
        # Script reintenta porque no le llegó la respuesta, no se duplica.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS whatsapp_salientes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo        TEXT NOT NULL,
                texto       TEXT NOT NULL,
                id_origen   TEXT UNIQUE,
                creado_en   TEXT NOT NULL,
                enviado_en  TEXT,
                error       TEXT
            )
        """)

        # ============================================================
        # M19 (Fase D, paso 2, ADR-0009): lotes.
        # ============================================================
        # (M16 quedó liberada: ADR-0009 reemplazó las cuentas de ADR-0006.)
        #
        # Un lote es una **propuesta** (varios gastos en un mensaje; después,
        # un extracto o un resumen) que se aplica entera o nada con el `ok` de
        # Franco, y que `deshacer` revierte entera. `lote_operaciones` guarda
        # cada fila tocada con cómo estaba **antes** y cómo quedó **después**:
        # deshacer solo procede si la fila sigue igual que la dejó el lote.
        # `fila_id` **no** es FK a propósito: con `foreign_keys = ON`, una FK
        # sin ON DELETE haría fallar el borrado de un gasto desde la app.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lotes (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL,
                user_id       INTEGER NOT NULL,
                origen        TEXT NOT NULL,
                estado        TEXT NOT NULL
                    CHECK (estado IN ('propuesto', 'aplicado', 'deshecho', 'descartado')),
                propuesta     TEXT NOT NULL,
                creado_en     TEXT NOT NULL,
                aplicado_en   TEXT,
                deshecho_en   TEXT
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_lotes_estado
                ON lotes(workspace_id, estado)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lote_operaciones (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                lote_id  INTEGER NOT NULL REFERENCES lotes(id) ON DELETE CASCADE,
                orden    INTEGER NOT NULL,
                tabla    TEXT NOT NULL,
                fila_id  INTEGER NOT NULL,
                accion   TEXT NOT NULL CHECK (accion IN ('insert', 'update')),
                antes    TEXT,
                despues  TEXT NOT NULL
            )
        """)

        # ============================================================
        # M20 (Fase D, paso 2, ADR-0009): el bruto de un gasto con cuenta.
        # ============================================================
        # "150000-25000*5" se carga como $25.000 (lo gastado de verdad), pero
        # la conciliación necesita los $150.000 que salieron en el momento
        # para reconocer las devoluciones. Tabla aparte y no columna en
        # `transacciones`: las migraciones viejas reconstruyen esa tabla con
        # listas de columnas fijas, y el export y el ingest la leen.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gasto_cuentas (
                transaccion_id  INTEGER PRIMARY KEY
                    REFERENCES transacciones(id) ON DELETE CASCADE,
                workspace_id    INTEGER NOT NULL,
                cuenta          TEXT NOT NULL,
                bruto           REAL NOT NULL
            )
        """)

        # ============================================================
        # M21 (Fase D, paso 4, ADR-0009): conciliación con el extracto.
        # ============================================================
        # `banco_filas`: cada movimiento de la caja de ahorro importado, en
        # **centavos**. La identidad (fecha + monto + saldo parcial) hace que
        # reimportar el mismo archivo no duplique nada; `orden` sigue la
        # cadena de saldos (sirve para ver si el extracto siguiente empalma).
        # Nunca se guardan CUIT, CBU ni números de cuenta: solo tipo y comercio.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS banco_filas (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL,
                orden         INTEGER NOT NULL,
                fecha         TEXT NOT NULL,
                monto         INTEGER NOT NULL,
                saldo         INTEGER NOT NULL,
                tipo          TEXT NOT NULL,
                comercio      TEXT,
                cotizacion    REAL,
                tratamiento   TEXT NOT NULL,
                estado        TEXT NOT NULL,
                UNIQUE (workspace_id, fecha, monto, saldo)
            )
        """)
        # Qué gasto corresponde a qué fila (o qué se decidió de un gasto que no
        # está en el banco). Las FK borran el vínculo si se borra el gasto o la
        # fila, así que borrar un gasto desde la app nunca se traba.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emparejamientos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id    INTEGER NOT NULL,
                transaccion_id  INTEGER REFERENCES transacciones(id) ON DELETE CASCADE,
                banco_fila_id   INTEGER REFERENCES banco_filas(id) ON DELETE CASCADE,
                rol             TEXT NOT NULL,
                era_efectivo    INTEGER NOT NULL DEFAULT 0,
                creado_en       TEXT NOT NULL
            )
        """)
        # Uno a uno: un gasto se empareja con una sola fila, y una fila con un
        # solo gasto. (Una devolución va a un gasto que ya puede tener pareja.)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_emparejamientos_gasto
                ON emparejamientos(transaccion_id)
                WHERE rol IN ('origen', 'mismo', 'arrastre', 'efectivo', 'tarjeta', 'reversion',
                              'anterior')
        """)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_emparejamientos_fila
                ON emparejamientos(banco_fila_id)
                WHERE rol IN ('mismo', 'arrastre', 'devolucion')
        """)
        # Lo que aprende de lo que Franco confirma: comercio → categoría, y
        # qué hacer con un tipo de movimiento que no conocía.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reglas_comercio (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL,
                tipo          TEXT NOT NULL,
                comercio      TEXT NOT NULL,
                motivo        TEXT NOT NULL,
                UNIQUE (workspace_id, tipo, comercio)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reglas_tipo (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL,
                tipo          TEXT NOT NULL,
                tratamiento   TEXT NOT NULL,
                UNIQUE (workspace_id, tipo)
            )
        """)
        # Los saldos que declara Franco (FIMA, efectivo) y el ancla de la caja,
        # en centavos y con fecha. Nunca van escritos en una migración.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS saldos_declarados (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL,
                parte         TEXT NOT NULL CHECK (parte IN ('caja', 'fima', 'efectivo')),
                fecha         TEXT NOT NULL,
                monto         INTEGER NOT NULL,
                declarado_en  TEXT NOT NULL
            )
        """)

        if reparaciones_pendientes:
            # Dentro de la transacción: si algo de arriba falla, el ROLLBACK
            # también deshace esta marca y las reparaciones se reintentan.
            cur.execute(f"PRAGMA user_version = {_NIVEL_REPARACIONES}")

        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise


# ============================================================
#  Conexión y init
# ============================================================

def es_tabla_faltante(exc: BaseException) -> bool:
    """True si `exc` es SQLite diciendo que una tabla no existe.

    Para los módulos que toleran una base sin cierta migración (tests con
    esquema recortado). **Solo eso**: hasta el 22/9/2026 esos módulos hacían
    ``except Exception``, que también tragaba un bug o una base bloqueada y
    los hacía pasar por "no hay ajustes" — y sin ajustes el capital aportado
    y la TIR cambian sin que nada avise (trampa 36).
    """
    return (isinstance(exc, sqlite3.OperationalError)
            and "no such table" in str(exc).lower())


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
    # `timeout` + `busy_timeout`: si otra conexión tiene el lock de escritura,
    # **esperar** en vez de fallar. El default de sqlite3 son 5 s solo para el
    # lock del driver y deja a SQLite sin `busy_timeout` propio, así que dos
    # escrituras simultáneas terminaban en `database is locked`. Pasó de verdad
    # el 4/8/2026: cargar un ajuste dispara un rerun de Streamlit que corría las
    # migraciones mientras el backup todavía tenía la base tomada, y la app
    # moría entera. 30 s es de sobra para cualquier escritura de esta app.
    conn = sqlite3.connect(path, isolation_level=None, timeout=30.0)
    conn.execute("PRAGMA busy_timeout = 30000")
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
