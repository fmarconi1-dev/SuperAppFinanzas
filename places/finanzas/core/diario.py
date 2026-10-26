"""Libro Diario: movimientos individuales con saldo acumulado, filtrado por usuario."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

import pandas as pd

from places.finanzas.core.categorizer import grupos_efectivos
from core.context import require_current_user_id
from places.finanzas.core.metrics import (
    load_categorias_full,
    load_transactions,
    saldo_inicial,
)


def libro_diario(
    conn: sqlite3.Connection,
    dias: int = 7,
    user_id: Optional[int] = None,
) -> pd.DataFrame:
    """Movimientos de los últimos `dias` días del usuario activo, con saldo de Caja."""
    uid = user_id if user_id is not None else require_current_user_id()

    df_all = load_transactions(conn, user_id=uid)
    if df_all.empty:
        return pd.DataFrame(columns=[
            "id", "fecha", "motivo", "grupo", "subcategoria",
            "pasivos", "ingresos", "caja_despues", "comentario",
        ])

    df_all = df_all.sort_values(["fecha", "id"]).reset_index(drop=True)
    df_all["caja_despues"] = (
        saldo_inicial(conn, user_id=uid)
        + (df_all["ingresos"] - df_all["pasivos"]).cumsum()
    )

    hoy = pd.Timestamp(date.today())
    desde = hoy - pd.Timedelta(days=int(dias) - 1)
    df_filt = df_all[df_all["fecha"] >= desde].copy()

    # El saldo necesita toda la historia (cumsum, arriba); el grupo, solo las
    # filas que se muestran. Antes se clasificaban todas, fila a fila con
    # `iterrows`, para mostrar 7 días: ~180 ms (frente 4 de rendimiento).
    cats_full = load_categorias_full(conn, user_id=uid)
    df_filt["grupo"], df_filt["subcategoria"] = grupos_efectivos(
        df_filt["motivo"], df_filt["pasivos"], df_filt["ingresos"], cats_full
    )

    return (
        df_filt.sort_values(["fecha", "id"], ascending=[False, False])
        .reset_index(drop=True)
    )
