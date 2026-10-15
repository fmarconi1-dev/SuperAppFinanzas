"""Contenedor de la Fase A (ADR-0008): nginx + API + Streamlit en un puerto.

No hay Docker en la PC de Franco, así que esto revisa los archivos como
texto: que el entrypoint no pierda el seed, que la API se relance, que nginx
reparta bien el 8501 y que `fly.toml` no haya cambiado de puerto. El
contenedor de verdad se prueba en el deploy (ver `docs/DEPLOY.md`).
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _t(nombre: str) -> str:
    return (RAIZ / nombre).read_text(encoding="utf-8")


def test_entrypoint_conserva_el_seed_y_termina_en_streamlit():
    t = _t("docker-entrypoint.sh")
    assert "needs_seed()" in t and 'cp "$SEED" "$DB"' in t
    lineas = [l.strip() for l in t.splitlines() if l.strip() and not l.strip().startswith("#")]
    assert lineas[-1] == "exec streamlit run app.py"


def test_entrypoint_relanza_la_api_y_arranca_nginx_antes_que_streamlit():
    t = _t("docker-entrypoint.sh")
    assert "while true" in t and "python /app/api.py" in t and ") &" in t
    assert t.index("python /app/api.py") < t.index("\nnginx") < t.index("exec streamlit")
    assert "exit 1" in t  # sin nginx no hay app: corta en vez de seguir a ciegas


def test_entrypoint_espera_a_la_api_antes_de_abrir_nginx():
    """Si nginx atiende antes que la API, un webhook de arranque en frío recibe
    502, Franco reenvía y el reintento de Meta duplica el gasto."""
    t = _t("docker-entrypoint.sh")
    espera = t.index("until curl -fsS http://127.0.0.1:8000/api/health")
    assert t.index("python /app/api.py") < espera < t.index("\nnginx")
    assert "-ge 30" in t  # con tope: no puede trabar el arranque de Streamlit


def test_nginx_reparte_el_8501():
    t = _t("deploy/nginx.conf")
    assert "listen 8501" in t
    assert "location /api/" in t and "proxy_pass http://127.0.0.1:8000" in t
    assert "location /" in t and "proxy_pass http://127.0.0.1:8502" in t


def test_nginx_no_corta_el_websocket_de_streamlit():
    t = _t("deploy/nginx.conf")
    assert "proxy_set_header Upgrade $http_upgrade" in t
    assert "proxy_set_header Connection $connection_upgrade" in t
    assert "proxy_http_version 1.1" in t
    assert "proxy_read_timeout 86400s" in t


def test_nginx_no_loguea_query_strings():
    t = _t("deploy/nginx.conf")
    assert "$uri" in t and "$request " not in t and '$request"' not in t


def test_dockerfile_instala_nginx_y_copia_la_api():
    t = _t("Dockerfile")
    assert "nginx" in t.split("apt-get install", 1)[1].split("\n", 1)[0]
    assert "rm -f /etc/nginx/sites-enabled/default" in t
    assert "api.py" in t and "COPY deploy/nginx.conf /etc/nginx/conf.d/superapp.conf" in t
    assert "STREAMLIT_SERVER_PORT=8502" in t and "STREAMLIT_SERVER_ADDRESS=127.0.0.1" in t
    assert "EXPOSE 8501" in t and "localhost:8501/_stcore/health" in t


def test_fly_toml_sigue_en_el_8501():
    t = _t("fly.toml")
    assert "internal_port = 8501" in t and 'path = "/_stcore/health"' in t


def test_dockerignore_no_deja_afuera_lo_nuevo():
    ignorados = {l.strip() for l in _t(".dockerignore").splitlines()}
    assert not {"deploy/", "deploy", "api.py", "core/api/"} & ignorados
