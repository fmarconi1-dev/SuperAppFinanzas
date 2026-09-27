# core/auth/

<!-- huella: e7866487f35c -->

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
- **Tests desde el 27/9/2026:** `tests/test_auth.py` (hash, alta, cambio de clave, rate-limit y la pantalla de login/alta con `AppTest`). Incluye que el usuario `local` que crea M1 **sin contraseña** no pueda entrar con ninguna.
- **El usuario distingue mayúsculas:** "Franco" no entra si la cuenta es "franco", y el celular pone la primera en mayúscula solo. El rate-limit, en cambio, no distingue (no se esquiva cambiando mayúsculas). Hacer el login insensible a mayúsculas es una propuesta abierta (en `MEJORAS.md`), no un cambio hecho: toca autenticación.
- Sin `SESSION_SECRET` configurado no hay persistencia de sesión entre refreshes (opcional por diseño; ver `.env.example`).

## Estado

- **Funciona:** en producción desde Fase 1.

## Proximo paso

—
