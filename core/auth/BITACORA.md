# core/auth/

<!-- huella: b1dff5d828c2 -->

Resumen: Autenticación compartida: usuarios con bcrypt, pantalla de login/signup, tokens de sesión firmados y los contextvars de usuario/workspace activos.

## Buscar acá si

- login, signup, contraseñas, código de registro (`SIGNUP_CODE`)
- "me pide loguearme en cada refresh" → tokens firmados en la URL (`session_tokens.py`, `SESSION_SECRET`)
- necesitás saber quién es el usuario o workspace actual desde lógica sin Streamlit → contextvars (`current_user.py`, `current_workspace.py`)
- el botón de logout

## Qué hay acá

- `auth.py` — bcrypt + helpers contra la tabla `usuarios`.
- `login.py` — pantalla de login/signup + botón de logout.
- `session_tokens.py` — HMAC-SHA256; el token viaja como query param.
- `current_user.py` / `current_workspace.py` — contextvars hoja, sin dependencias.

## Trampas

- `login.py` importa `core.db`: es la pata de vuelta del ciclo core↔core/auth. Los contextvars son hojas puras y no lo agravan.
- Sin `SESSION_SECRET` configurado no hay persistencia de sesión entre refreshes (opcional por diseño; ver `.env.example`).

## Estado

- **Funciona:** en producción desde Fase 1.

## Proximo paso

—
