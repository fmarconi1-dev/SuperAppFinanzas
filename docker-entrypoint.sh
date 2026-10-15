#!/bin/sh
# Entrypoint: siembra la base en el volumen la primera vez (o si quedó vacía),
# usando seed_finanzas.db si existe en la imagen. Después arranca la API,
# nginx y Streamlit (desde la Fase A, ADR-0008).
#
# Es idempotente y seguro de dejar permanentemente:
#   - Sólo siembra si hay un seed Y la base del volumen no existe o tiene 0 txns.
#   - Si no hay seed (deploy normal), no hace nada y arranca la app.

SEED=/app/seed_finanzas.db
DB=/app/data/finanzas.db

needs_seed() {
  [ ! -f "$DB" ] && return 0
  count=$(python -c "import sqlite3;print(sqlite3.connect('$DB').execute('SELECT COUNT(*) FROM transacciones').fetchone()[0])" 2>/dev/null || echo 0)
  [ "$count" = "0" ] && return 0
  return 1
}

if [ -f "$SEED" ] && needs_seed; then
  echo "[entrypoint] Sembrando base inicial desde seed_finanzas.db..."
  cp "$SEED" "$DB"
  rm -f "$DB-wal" "$DB-shm"
  echo "[entrypoint] Listo."
fi

# API de WhatsApp (Fase A, ADR-0008) en 127.0.0.1:8000. Corre en segundo
# plano y, si se cae, se relanza: el health check de Fly mira Streamlit, así
# que una API muerta no la ve nadie más.
(
  while true; do
    python /app/api.py
    echo "[entrypoint] La API terminó (código $?); la relanzo en 2 s."
    sleep 2
  done
) &

# Esperar a que la API escuche (importa pandas: tarda unos segundos) ANTES
# de abrir nginx. Si un webhook despierta la máquina y nginx ya atiende pero
# la API no, Meta recibe 502 y reintenta más tarde; mientras tanto Franco, sin
# ✅, reenvía el gasto con otro id de mensaje, y el dedupe no lo puede frenar:
# gasto duplicado. Tope de 30 s: si no levanta, se avisa y sigue igual, para
# que al menos Streamlit arranque.
i=0
until curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "[entrypoint] La API no respondió en 30 s; sigo sin esperarla."
    break
  fi
  sleep 1
done

# nginx reparte el 8501 (el puerto de fly.toml): /api/ → API, / → Streamlit.
# Se demoniza solo. Si no arranca, se corta acá: sin nginx no hay app.
nginx || { echo "[entrypoint] nginx no arrancó"; exit 1; }

# Streamlit en 127.0.0.1:8502 (STREAMLIT_SERVER_* del Dockerfile).
exec streamlit run app.py
