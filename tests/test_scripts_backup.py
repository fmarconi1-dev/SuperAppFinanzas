"""Invariantes de los scripts de respaldo y restore.

**Qué puede y qué no puede cubrir este archivo.** Son PowerShell y CI corre en
Linux: no se pueden ejecutar acá. Lo que sí se puede verificar es su
**estructura**, y eso alcanza para atajar los errores que ya cometimos:

* la verificación se hacía con un `python -c` multilínea y **PowerShell se comía
  las comillas** (Python moría con `SyntaxError`, 4/8/2026);
* el backup despertaba la máquina con un request HTTP, y cuando eso no
  alcanzaba el `sftp` cortaba con *"app has no started VMs"* y **no se hacía el
  backup** (4/8/2026). Con `min_machines_running = 0` la tarea programada de
  madrugada encuentra la máquina dormida **siempre**;
* ⚠️ **el restore no podía funcionar**: hacía `fly scale count 0` —que no para
  la máquina, la **destruye**— y después intentaba entrar por `fly ssh` a una
  máquina inexistente. Nunca se detectó porque el ensayo end-to-end quedó
  siempre pendiente.

**No reemplazan correr los scripts de verdad una vez.**
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
BACKUP = SCRIPTS / "backup_remoto.ps1"
RESTORE = SCRIPTS / "restaurar_backup.ps1"
COMUN = SCRIPTS / "_fly_comun.ps1"


def _texto(p: Path) -> str:
    if not p.exists():                           # pragma: no cover
        pytest.skip(f"no está {p}")
    return p.read_text(encoding="utf-8", errors="replace")


def _codigo(p: Path) -> str:
    """El script sin comentarios: los comentarios nombran los anti-patrones."""
    return "\n".join(
        l for l in _texto(p).splitlines() if not l.lstrip().startswith("#")
    )


def _pos(texto: str, aguja: str) -> int:
    i = texto.find(aguja)
    assert i != -1, f"el script ya no contiene {aguja!r}"
    return i


# ---------------------------------------------------------------------------
# La máquina tiene que estar encendida antes de cualquier SSH
# ---------------------------------------------------------------------------

def test_el_helper_compartido_existe():
    """La lógica de encender la máquina vive en un solo lugar. Estuvo
    duplicada de hecho —solo en el backup— y por eso el restore quedó sin
    arreglar cuando se arregló el backup."""
    assert COMUN.exists()
    t = _texto(COMUN)
    assert "machines list" in t and "machine start" in t


@pytest.mark.parametrize("script", [BACKUP, RESTORE])
def test_enciende_la_maquina_antes_de_usar_ssh(script):
    """`fly ssh` necesita una máquina encendida. Si el arranque quedara después,
    fallaría siempre que la app esté dormida — que es cuando corre la tarea
    programada."""
    codigo = _codigo(script)
    assert _pos(codigo, "Start-AppFly") < _pos(codigo, "fly ssh")


@pytest.mark.parametrize("script", [BACKUP, RESTORE])
def test_carga_el_helper_compartido(script):
    assert "_fly_comun.ps1" in _codigo(script)


def test_avisa_si_la_app_no_tiene_maquinas():
    """Sin máquinas el problema es otro (falta desplegar) y el mensaje tiene
    que decirlo, no dejar un error de sftp críptico."""
    t = _texto(COMUN)
    assert "no tiene ninguna maquina" in t and "fly deploy" in t


# ---------------------------------------------------------------------------
# El backup
# ---------------------------------------------------------------------------

def test_verifica_la_copia_antes_de_darla_por_buena():
    """Un archivo que existe no es un backup."""
    codigo = _codigo(BACKUP)
    assert _pos(codigo, "sftp get") < _pos(codigo, "verificar_backup.py")
    assert "exit 1" in codigo


def test_la_verificacion_vive_en_un_archivo_no_en_python_c():
    """Regresión: PowerShell se come las comillas de un script multilínea
    pasado a `python -c`."""
    codigo = _codigo(BACKUP)
    assert "verificar_backup.py" in codigo
    assert "python -c" not in codigo


def test_la_purga_nunca_se_lleva_las_ultimas_copias():
    """Si el script dejó de correr hace meses, borrar la última copia buena
    por vieja sería el peor resultado posible."""
    assert "Select-Object -First 3" in _codigo(BACKUP)


def test_deja_bitacora_de_cada_corrida():
    """A las 3 de la mañana nadie mira la consola. Un backup que dejó de
    funcionar y no avisa da una sensación de protección que no existe."""
    codigo = _codigo(BACKUP)
    assert "backup.log" in codigo
    assert "Escribir-Log" in codigo


def test_registra_tambien_los_fallos_no_solo_los_exitos():
    """Si solo se anotan los OK, un log que se corta parece un log vacío."""
    codigo = _codigo(BACKUP)
    assert codigo.count('Escribir-Log "ERROR"') >= 2
    assert 'Escribir-Log "OK"' in codigo


# ---------------------------------------------------------------------------
# El restore — el que estaba roto
# ---------------------------------------------------------------------------

def test_el_restore_no_usa_scale_count():
    """⚠️ `fly scale count 0` **destruye** la máquina, no la para: después no
    se puede entrar por SSH para subir nada, y `scale count 1` tiene que crear
    una máquina nueva, que puede fallar (`cpu_overcommit_exceeded`). El
    restore quedaba colgado con la app caída y la base sin reemplazar."""
    codigo = _codigo(RESTORE)
    assert "scale count" not in codigo, (
        "el restore volvió a usar `fly scale count`: eso destruye la máquina "
        "y deja el restore a mitad de camino"
    )
    assert "machine restart" in codigo or "apps restart" in codigo


def test_el_restore_verifica_la_copia_antes_de_tocar_produccion():
    """Restaurar una copia rota encima de una base viva convierte un problema
    en un desastre."""
    codigo = _codigo(RESTORE)
    assert _pos(codigo, "verificar_backup.py") < _pos(codigo, "sftp get")


def test_el_restore_respalda_lo_que_hay_antes_de_pisarlo():
    """`pre-restore-*.db` es lo único que permite volver atrás."""
    codigo = _codigo(RESTORE)
    assert "pre-restore-" in codigo
    assert _pos(codigo, "pre-restore-") < _pos(codigo, "sftp shell")


def test_el_restore_sube_a_un_temporal_y_despues_hace_el_swap():
    """Subir directo sobre la base viva la deja inconsistente si algo corta a
    mitad de la transferencia."""
    codigo = _codigo(RESTORE)
    assert "restore-pendiente.db" in codigo
    assert _pos(codigo, "restore-pendiente.db") < _pos(codigo, "mv -f")


def test_el_restore_borra_el_diario_wal():
    """Si se reemplaza el .db sin borrar `-wal`/`-shm`, SQLite mezcla la base
    restaurada con el diario de la vieja y el resultado es una base corrupta."""
    codigo = _codigo(RESTORE)
    assert "finanzas.db-wal" in codigo and "finanzas.db-shm" in codigo
    assert _pos(codigo, "mv -f") < _pos(codigo, "restart")


def test_el_restore_no_hace_nada_sin_confirmar():
    """El default es el simulacro. Un script que pisa producción no puede
    tener el modo destructivo por defecto."""
    codigo = _codigo(RESTORE)
    assert "$Confirmar" in codigo
    assert _pos(codigo, "if (-not $Confirmar)") < _pos(codigo, "sftp get")


# ---------------------------------------------------------------------------
# Programar y monitorear
# ---------------------------------------------------------------------------

def test_hay_un_script_que_programa_la_tarea():
    """Un comando se corre; una guía de seis clicks se posterga semanas."""
    p = SCRIPTS / "programar_backup.ps1"
    assert p.exists()
    assert "Register-ScheduledTask" in _texto(p)


def test_la_tarea_corre_aunque_la_notebook_este_a_bateria():
    """Es el motivo más común de una tarea que 'está programada' y nunca
    corre: el default de Windows es no ejecutarla con batería."""
    t = _texto(SCRIPTS / "programar_backup.ps1")
    assert "AllowStartIfOnBatteries" in t
    assert "DontStopIfGoingOnBatteries" in t
    assert "StartWhenAvailable" in t, (
        "sin esto, el día que la PC estuvo apagada a esa hora no hay backup"
    )


def test_hay_un_script_que_responde_si_el_backup_viene_andando():
    p = SCRIPTS / "estado_backup.ps1"
    assert p.exists()
    t = _texto(p)
    assert "backup.log" in t
    assert "MaxDiasSinBackup" in t, (
        "el veredicto tiene que mirar la ANTIGÜEDAD de la última copia: diez "
        "copias de hace tres meses no protegen de nada"
    )


def test_el_verificador_existe_y_es_importable():
    assert (SCRIPTS / "verificar_backup.py").exists()
    from scripts.verificar_backup import verificar   # noqa: F401


# ---------------------------------------------------------------------------
# La configuración de deploy
# ---------------------------------------------------------------------------

def test_el_deploy_usa_la_estrategia_immediate():
    """Rolling pide **el doble de recursos** durante el cambio (2 GB de RAM),
    y la máquina no puede mudarse de host porque está atada al volumen. Falló
    dos veces el 4/8/2026, con los dos mensajes de la familia:
    `cpu_overcommit_exceeded` e `insufficient memory ... on the current host`.

    Con una sola máquina el solapamiento no compra nada: no hay alta
    disponibilidad que proteger.
    """
    fly = SCRIPTS.parent / "fly.toml"
    t = _texto(fly)
    assert "[deploy]" in t, "falta la sección [deploy] en fly.toml"
    assert 'strategy = "immediate"' in t, (
        "el deploy volvió a la estrategia rolling: con un volumen y una sola "
        "máquina, eso pide el doble de recursos en un host que no puede cambiar"
    )


def test_el_volumen_y_la_memoria_siguen_donde_los_esperamos():
    """Si alguien baja la memoria para 'que entre en el host', la cartera deja
    de poder valuarse: pandas necesita ese GB."""
    t = _texto(SCRIPTS.parent / "fly.toml")
    assert 'memory = "1gb"' in t
    assert 'source = "finanzas_data"' in t
