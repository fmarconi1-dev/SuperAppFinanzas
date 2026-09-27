"""Login, contraseñas y alta de cuentas.

**Por qué existe (27/9/2026).** Era la parte menos cubierta del repo —`auth.py`
29%, `login.py` 21%— y la más sensible: es lo único que separa tus datos de
cualquiera que encuentre la URL. Cubre la lógica pura y, con `AppTest`, la
pantalla tal como se usa.

Un caso merece nombre propio: la migración M1 crea un usuario `local` (id 1 en
una base nueva) **sin contraseña**. No puede poder entrar con ninguna.
"""

from __future__ import annotations

import pytest

from core import db as core_db
from core.auth import auth
from core.auth.auth import (
    LOCKOUT_SECONDS,
    LOCKOUT_THRESHOLD,
    LOCKOUT_WINDOW,
    authenticate,
    clear_failed_logins,
    create_user,
    get_user,
    hash_password,
    register_failed_login,
    seconds_until_unlock,
    set_password,
    verify_password,
)
from core.db import connect, init_db


@pytest.fixture(autouse=True)
def _sin_bloqueos():
    """El rate-limit vive en memoria del proceso: cada test arranca limpio."""
    auth._failed_logins.clear()
    yield
    auth._failed_logins.clear()


@pytest.fixture()
def ruta(tmp_path, monkeypatch):
    r = tmp_path / "finanzas.db"
    monkeypatch.setenv("DB_PATH", str(r))
    monkeypatch.setattr(core_db, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.delenv("SIGNUP_CODE", raising=False)
    init_db(r)
    return r


@pytest.fixture()
def conn(ruta):
    c = connect(ruta)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Hash
# ---------------------------------------------------------------------------

def test_el_hash_verifica_y_no_guarda_la_contrasena():
    h = hash_password("clave-secreta")
    assert "clave-secreta" not in h
    assert verify_password("clave-secreta", h)
    assert not verify_password("otra", h)


def test_dos_hashes_de_la_misma_clave_son_distintos():
    """bcrypt con sal: dos usuarios con la misma clave no se delatan."""
    assert hash_password("igual123") != hash_password("igual123")


@pytest.mark.parametrize("plain,hashed", [
    ("", "$2b$12$algo"), ("x", ""), ("x", None), ("x", "no-es-un-hash-bcrypt"),
])
def test_verificar_contra_algo_roto_es_false_y_no_explota(plain, hashed):
    assert verify_password(plain, hashed) is False


def test_no_se_hashea_una_clave_vacia():
    with pytest.raises(ValueError):
        hash_password("")


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

def test_crear_y_autenticar(conn):
    uid = create_user(conn, "  ana  ", "clave123", "Ana")
    user = authenticate(conn, "ana", "clave123")
    assert user == {"id": uid, "username": "ana", "fullname": "Ana"}
    assert "password_hash" not in user            # nunca sale del módulo


@pytest.mark.parametrize("usuario,clave", [("", "clave123"), ("   ", "clave123"),
                                           ("ana", "corta")])
def test_crear_rechaza_datos_invalidos(conn, usuario, clave):
    with pytest.raises(ValueError):
        create_user(conn, usuario, clave)


def test_no_se_puede_crear_dos_veces_el_mismo_usuario(conn):
    create_user(conn, "ana", "clave123")
    with pytest.raises(ValueError, match="ya existe"):
        create_user(conn, "ana", "otra-clave")


def test_clave_incorrecta_o_usuario_inexistente_da_none(conn):
    create_user(conn, "ana", "clave123")
    assert authenticate(conn, "ana", "incorrecta") is None
    assert authenticate(conn, "nadie", "clave123") is None


@pytest.mark.parametrize("clave", ["", "local", "admin", "123456"])
def test_el_usuario_local_de_m1_no_puede_entrar(conn, clave):
    """M1 crea `local` sin contraseña (password_hash NULL). Con ninguna clave."""
    local = get_user(conn, "local")
    assert local is not None and local["password_hash"] is None
    assert authenticate(conn, "local", clave) is None


def test_cambiar_la_clave(conn):
    uid = create_user(conn, "ana", "clave123")
    set_password(conn, uid, "nueva-clave")
    assert authenticate(conn, "ana", "clave123") is None
    assert authenticate(conn, "ana", "nueva-clave") is not None


def test_cambiar_la_clave_valida(conn):
    uid = create_user(conn, "ana", "clave123")
    with pytest.raises(ValueError):
        set_password(conn, uid, "corta")
    with pytest.raises(LookupError):
        set_password(conn, 99999, "valida123")


# ---------------------------------------------------------------------------
# Rate limit (premortem #3): 5 fallos en 15 min -> 5 min de bloqueo
# ---------------------------------------------------------------------------

def _fallar(n: int, usuario: str = "ana", desde: float = 1000.0) -> float:
    for i in range(n):
        register_failed_login(usuario, now=desde + i)
    return desde + n - 1


def test_bloquea_al_quinto_fallo_y_no_antes():
    t = _fallar(LOCKOUT_THRESHOLD - 1)
    assert seconds_until_unlock("ana", now=t) == 0
    t = _fallar(1, desde=t + 1)
    assert seconds_until_unlock("ana", now=t) > 0


def test_el_bloqueo_se_levanta_solo():
    t = _fallar(LOCKOUT_THRESHOLD)
    assert seconds_until_unlock("ana", now=t + LOCKOUT_SECONDS - 10) > 0
    assert seconds_until_unlock("ana", now=t + LOCKOUT_SECONDS + 1) == 0


def test_fallos_viejos_no_cuentan():
    """Solo cuentan los de la ventana: cuatro fallos de ayer no son deuda."""
    _fallar(LOCKOUT_THRESHOLD - 1, desde=0.0)
    t = LOCKOUT_WINDOW + 100.0
    register_failed_login("ana", now=t)
    assert seconds_until_unlock("ana", now=t) == 0


def test_el_bloqueo_no_se_esquiva_cambiando_mayusculas_ni_espacios():
    t = 1000.0
    for i, variante in enumerate(["ana", "ANA", " Ana ", "aNa", "ana"]):
        register_failed_login(variante, now=t + i)
    assert seconds_until_unlock("ANA", now=t + 5) > 0


def test_un_login_bueno_limpia_los_fallos():
    t = _fallar(LOCKOUT_THRESHOLD)
    clear_failed_logins("Ana")
    assert seconds_until_unlock("ana", now=t) == 0


def test_el_bloqueo_es_por_usuario():
    t = _fallar(LOCKOUT_THRESHOLD, usuario="ana")
    assert seconds_until_unlock("beto", now=t) == 0


# ---------------------------------------------------------------------------
# La pantalla (AppTest)
# ---------------------------------------------------------------------------

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _pantalla_login():
    from core.auth import login
    login.render()


def _login(usuario: str, clave: str) -> AppTest:
    at = AppTest.from_function(_pantalla_login, default_timeout=30)
    at.run()
    at.text_input(key="login_username").input(usuario)
    at.text_input(key="login_password").input(clave)
    at.button[0].click()
    at.run()
    return at


def test_la_pantalla_deja_entrar_con_la_clave_correcta(conn):
    uid = create_user(conn, "ana", "clave123", "Ana")
    conn.commit()
    at = _login("ana", "clave123")
    assert not at.exception
    assert at.session_state["logged_in"] is True
    assert at.session_state["current_user_id"] == uid


def test_la_pantalla_rechaza_la_clave_incorrecta(conn):
    create_user(conn, "ana", "clave123")
    conn.commit()
    at = _login("ana", "incorrecta")
    assert "logged_in" not in at.session_state
    assert any("incorrectos" in e.value for e in at.error)


def test_la_pantalla_bloquea_despues_de_cinco_fallos_aunque_la_clave_sea_buena(conn):
    create_user(conn, "ana", "clave123")
    conn.commit()
    for _ in range(LOCKOUT_THRESHOLD):
        _login("ana", "incorrecta")
    at = _login("ana", "clave123")
    assert "logged_in" not in at.session_state
    assert any("Demasiados intentos" in e.value for e in at.error)


def test_sin_signup_code_no_hay_alta_de_cuentas(ruta):
    at = AppTest.from_function(_pantalla_login, default_timeout=30)
    at.run()
    assert not at.tabs                        # solo el login, sin pestaña de alta
    assert any("deshabilitado" in c.value for c in at.caption)


def test_el_alta_exige_el_codigo_de_invitacion(ruta, monkeypatch):
    monkeypatch.setenv("SIGNUP_CODE", "codigo-secreto")

    def alta(codigo: str) -> AppTest:
        at = AppTest.from_function(_pantalla_login, default_timeout=30)
        at.run()
        at.text_input(key="signup_fullname").input("Beto")
        at.text_input(key="signup_username").input("beto")
        at.text_input(key="signup_password").input("clave123")
        at.text_input(key="signup_password2").input("clave123")
        at.text_input(key="signup_code").input(codigo)
        at.button[1].click()                  # "Crear cuenta" (el 0 es "Entrar")
        at.run()
        return at

    at = alta("adivinando")
    assert any("invitación incorrecto" in e.value for e in at.error)
    with connect(ruta) as c:
        assert get_user(c, "beto") is None

    at = alta("codigo-secreto")
    assert not at.exception
    assert at.session_state["logged_in"] is True
    with connect(ruta) as c:
        assert get_user(c, "beto") is not None
