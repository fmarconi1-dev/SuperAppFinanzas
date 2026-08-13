"""`.env.example` no puede tener credenciales reales.

**El agujero que cierra.** El pre-commit hook bloquea `.env`… pero tiene una
excepción explícita para `.env.example`, que **sí se commitea** — es la
plantilla que documenta qué variables existen. O sea que un secreto puesto ahí
por error **no lo frena nadie** y viaja a GitHub en el próximo push.

No es hipotético: el 5/8/2026 Franco preguntó, con las credenciales de Docta
Capital en la mano, si iban en `.env.example`. La respuesta correcta era no, y
esa respuesta no debería depender de que alguien la sepa.

**Qué revisa.** Que toda clave con pinta de secreto esté **vacía o comentada**.
Un valor de ejemplo inofensivo (`DB_PATH=./data/finanzas.db`) es legítimo y
pasa; `DOCTA_CLIENT_SECRET=a1b2c3...` no.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLANTILLA = Path(__file__).resolve().parents[1] / ".env.example"

#: Fragmentos que marcan una variable como sensible. Deliberadamente amplios:
#: es preferible un falso positivo (que obliga a comentar la línea) a un
#: secreto publicado.
SENSIBLES = ("SECRET", "TOKEN", "PASSWORD", "PASSWD", "APIKEY", "API_KEY",
             "CLIENT_ID", "CLIENT_SECRET", "PRIVATE", "CREDENTIAL", "CODE")


def _asignaciones(texto: str) -> list[tuple[str, str]]:
    """`[(clave, valor)]` de las líneas **no comentadas**."""
    out = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, _, valor = limpia.partition("=")
        out.append((clave.strip(), valor.strip()))
    return out


@pytest.fixture(scope="module")
def texto() -> str:
    if not PLANTILLA.exists():                   # pragma: no cover
        pytest.skip("no está .env.example")
    return PLANTILLA.read_text(encoding="utf-8")


def test_ninguna_clave_sensible_tiene_valor(texto):
    culpables = [
        f"{k}={v[:8]}…"
        for k, v in _asignaciones(texto)
        if v and any(s in k.upper() for s in SENSIBLES)
    ]
    assert not culpables, (
        f"`.env.example` **se commitea al repo** y tiene claves sensibles con "
        f"valor: {', '.join(culpables)}. Las credenciales reales van en `.env` "
        f"(ignorado por git) o en `fly secrets set`. Dejá la línea comentada "
        f"o con el valor vacío."
    )


def test_no_hay_nada_con_pinta_de_credencial(texto):
    """Además de las claves conocidas, cualquier valor largo y aleatorio."""
    sospechosos = [
        f"{k}={v[:8]}…"
        for k, v in _asignaciones(texto)
        # 24+ caracteres sin espacios ni barras: no es una ruta ni un número.
        if re.fullmatch(r"[A-Za-z0-9_\-\.]{24,}", v) and not v.startswith("./")
    ]
    assert not sospechosos, (
        f"valores con pinta de credencial en `.env.example`: "
        f"{', '.join(sospechosos)}"
    )


def test_la_plantilla_avisa_que_se_commitea(texto):
    """Que la advertencia esté escrita donde se la va a leer, no solo en un
    test que nadie abre cuando está apurado."""
    cabecera = texto[:1200].upper()
    assert "SE COMMITEA" in cabecera or "SE SUBE" in cabecera
    assert ".ENV" in cabecera and "FLY SECRETS" in texto.upper()


def test_git_ignora_el_env_pero_no_la_plantilla():
    """Si alguien 'arregla' el .gitignore y saca la excepción, la plantilla
    desaparece del repo y nadie sabe qué variables hacen falta."""
    gitignore = (PLANTILLA.parent / ".gitignore").read_text(encoding="utf-8")
    lineas = [l.strip() for l in gitignore.splitlines()]
    assert ".env" in lineas
    assert "!.env.example" in lineas
