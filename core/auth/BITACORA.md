# core/auth/

<!-- huella: b67eb9b40a25 -->

Resumen: Autenticación compartida: usuarios con bcrypt, pantalla de login/signup y tokens de sesión firmados. (Los contextvars de usuario/workspace viven en `core/context.py`.)

## Buscar acá si

- login, signup, contraseñas, código de registro (`SIGNUP_CODE`)
- "me pide loguearme en cada refresh" → tokens firmados en la URL (`session_tokens.py`, `SESSION_SECRET`)
- necesitás saber quién es el usuario o workspace actual desde lógica sin Streamlit → **no es acá**: `core/context.py` (las fachadas `current_user.py`/`current_workspace.py` se borraron el 22/9/2026)
- el botón de logout

## Qué hay acá

- `auth.py` — bcrypt + helpers contra la tabla `usuarios`.
- `login.py` — pantalla de login/signup + botón de logout.
- `session_tokens.py` — HMAC-SHA256; el token viaja como query param.

## Trampas

- `login.py` importa `core.db`. Por eso `core.db` no puede importar nada de `core/auth` (el ciclo que cortó `core/context.py` el 27/8).
- **Carpeta con poca red de tests** (22/9/2026): `auth.py` 29% y `login.py` 21% de cobertura. Un cambio acá se prueba a mano o se le escribe el test primero (pendiente en `MEJORAS.md`).
- Sin `SESSION_SECRET` configurado no hay persistencia de sesión entre refreshes (opcional por diseño; ver `.env.example`).

## Estado

- **Funciona:** en producción desde Fase 1.

## Proximo paso

—
