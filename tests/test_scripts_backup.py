"""Invariantes del script de backup remoto.

**Qué puede y qué no puede cubrir este archivo.** `backup_remoto.ps1` es
PowerShell y CI corre en Linux: no se puede ejecutar acá. Lo que sí se puede
verificar es su **estructura**, y eso alcanza para atajar los dos errores que
ya cometimos con él:

* la verificación se hacía con un `python -c` multilínea y **PowerShell se comía
  las comillas** (falló de verdad el 4/8/2026, Python moría con `SyntaxError`);
* el script despertaba la máquina con un simple request HTTP, y cuando eso no
  alcanzaba el `sftp` cortaba con *"app has no started VMs"* y **no se hacía el
  backup** (falló de verdad el 4/8/2026). Con `min_machines_running = 0`, la
  tarea programada de madrugada encuentra la máquina dormida **siempre**: ese
  es el camino normal del script, no la excepción.

Son chequeos de orden y de presencia. Si alguien reordena los pasos o saca la
verificación, se entera acá. **No reemplazan correrlo de verdad una vez.**
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_remoto.ps1"


@pytest.fixture(scope="module")
def texto() -> str:
    if not SCRIPT.exists():                      # pragma: no cover
        pytest.skip(f"no está {SCRIPT}")
    return SCRIPT.read_text(encoding="utf-8", errors="replace")


def _pos(texto: str, aguja: str) -> int:
    i = texto.find(aguja)
    assert i != -1, f"el script ya no contiene {aguja!r}"
    return i


def test_enciende_la_maquina_antes_de_bajar_la_db(texto):
    """El sftp necesita una máquina encendida. Si el arranque quedara después
    de la descarga, el backup fallaría siempre que la app esté dormida — que es
    justo cuando corre la tarea programada."""
    assert _pos(texto, "machines list") < _pos(texto, "sftp get")
    assert _pos(texto, "machine start") < _pos(texto, "sftp get")


def test_avisa_si_la_app_no_tiene_maquinas(texto):
    """Sin máquinas el problema es otro (falta desplegar) y el mensaje tiene
    que decirlo, no dejar un error de sftp críptico."""
    assert "no tiene ninguna maquina" in texto
    assert "fly deploy" in texto


def test_espera_al_health_antes_del_sftp(texto):
    """Encender la máquina no es lo mismo que estar lista: hay 30 s de
    `grace_period` en el arranque."""
    assert _pos(texto, "_stcore/health") < _pos(texto, "sftp get")


def test_verifica_la_copia_antes_de_darla_por_buena(texto):
    """Un archivo que existe no es un backup. La verificación va **después**
    de descargar y su resultado corta el script."""
    assert _pos(texto, "sftp get") < _pos(texto, "verificar_backup.py")
    assert "exit 1" in texto


def test_la_verificacion_vive_en_un_archivo_no_en_python_c(texto):
    """Regresión del 4/8/2026: PowerShell se come las comillas de un script
    multilínea pasado a `python -c` y Python recibe basura.

    Se miran solo las líneas ejecutables: los comentarios **sí** nombran
    `python -c`, justamente para contar por qué no se usa.
    """
    codigo = "\n".join(
        l for l in texto.splitlines() if not l.lstrip().startswith("#")
    )
    assert "verificar_backup.py" in codigo
    assert "python -c" not in codigo


def test_la_purga_nunca_se_lleva_las_ultimas_copias(texto):
    """Si el script dejó de correr hace meses, borrar la última copia buena
    por vieja sería el peor resultado posible."""
    assert "Select-Object -First 3" in texto


def test_el_verificador_existe_y_es_ejecutable_como_modulo():
    """El script lo invoca por ruta; si se renombra, el backup falla recién
    el día que se corre."""
    verificador = SCRIPT.parent / "verificar_backup.py"
    assert verificador.exists()
    from scripts.verificar_backup import verificar   # noqa: F401
