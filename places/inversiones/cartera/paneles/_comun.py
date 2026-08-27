"""Piezas compartidas por todos los paneles de Cartera: formato es-AR y la
KPI card del sistema Cosmic Slate.

Vive acá y no en `view.py` para que un panel pueda importarse **sin arrastrar
la vista entera**. Los nombres conservan el guion bajo del original: el split
del 27/8/2026 movió código, no lo renombró.
"""

from __future__ import annotations

#: Segundos de caché en memoria para los datos vivos (precios, MEP, series de
#: índices). Vive acá porque los decoradores `@st.cache_data` de varios paneles
#: lo necesitan y no puede quedar en `view.py`: sería un import al revés.
_TTL_PRECIOS = 300


def _fmt(n: float | None, dec: int = 2, prefijo: str = "") -> str:
    if n is None:
        return "—"
    s = f"{n:,.{dec}f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"{prefijo}{s}"


def _kpi_card(label: str, valor: str, contexto: str = "", tono: str = "") -> str:
    color = {
        "positivo": "var(--cs-positive)",
        "negativo": "var(--cs-negative)",
    }.get(tono, "var(--cs-text)")
    ctx = (
        f'<div style="font-size:12px;color:{color};margin-top:6px;'
        f'font-variant-numeric:tabular-nums;">{contexto}</div>'
        if contexto else ""
    )
    return f"""
    <div style="background:var(--cs-bg-1);border:1px solid var(--cs-border);
                border-radius:var(--cs-radius-md);padding:16px 18px;height:100%;">
      <div style="font-size:12px;color:var(--cs-text-mid);
                  text-transform:uppercase;letter-spacing:.04em;">{label}</div>
      <div style="font-size:28px;font-weight:700;color:var(--cs-text);
                  font-family:var(--cs-font-mono);font-variant-numeric:tabular-nums;
                  margin-top:8px;line-height:1.15;">{valor}</div>
      {ctx}
    </div>
    """
