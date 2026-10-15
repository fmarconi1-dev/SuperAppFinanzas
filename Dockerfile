# syntax=docker/dockerfile:1.6
# Superapp de Finanzas — imagen de deploy (Fly.io). Adaptada del Dockerfile
# probado de Mis-Finanzas-App (radar-financiero).
FROM python:3.11-slim

WORKDIR /app

# nginx (Fase A, ADR-0008): reparte el puerto 8501 entre Streamlit y la API.
# El sitio `default` de Debian escucha en el 80 y no sirve: se borra.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl nginx \
    && rm -f /etc/nginx/sites-enabled/default \
    && rm -rf /var/lib/apt/lists/*

# Deps en su propia capa. Si existe requirements.lock, builds reproducibles.
COPY requirements.txt requirements.lock* ./
RUN if [ -f requirements.lock ]; then \
        pip install --no-cache-dir -r requirements.lock; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# Código (tests/ y docs/ quedan fuera vía .dockerignore).
COPY app.py api.py ./
COPY deploy/nginx.conf /etc/nginx/conf.d/superapp.conf
COPY core/ ./core/
COPY places/ ./places/
COPY scripts/ ./scripts/
COPY .streamlit/ ./.streamlit/
COPY assets/ ./assets/

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

# El volumen /app/data se monta para persistir la DB y los backups.
RUN mkdir -p /app/data/backups

# Streamlit ya no da la cara: escucha en 127.0.0.1:8502 y nginx lo publica en
# el 8501 (el puerto de `fly.toml`, que no cambia). El HEALTHCHECK de abajo
# sigue pegándole al 8501, así que prueba nginx y Streamlit juntos.
ENV STREAMLIT_SERVER_PORT=8502 \
    STREAMLIT_SERVER_ADDRESS=127.0.0.1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_RUN_ON_SAVE=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true \
    DB_PATH=/app/data/finanzas.db \
    PYTHONUNBUFFERED=1

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["/app/docker-entrypoint.sh"]
