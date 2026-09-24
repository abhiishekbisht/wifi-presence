#!/bin/bash
set -e

echo "=== Starting Wi-Fi Presence Estimation Service ==="

# Initialize SQLite database if needed
echo "[+] Ensuring database schema and initial seed data exist..."
python database/init_db.py

# Determine host, port, and worker counts
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

echo "[+] Configuration:"
echo "    Host: $HOST"
echo "    Port: $PORT"
echo "    Workers: $WORKERS"
echo "    Environment: ${ENVIRONMENT:-production}"
echo "    Log Level: $LOG_LEVEL"

# Run with Gunicorn + Uvicorn workers for production multi-core performance, or Uvicorn directly
if [ "$WORKERS" -gt 1 ]; then
    echo "[+] Launching Gunicorn with $WORKERS Uvicorn workers..."
    exec gunicorn backend.main:app \
        --workers "$WORKERS" \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind "$HOST:$PORT" \
        --log-level "$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')" \
        --access-logfile - \
        --error-logfile -
else
    echo "[+] Launching Uvicorn ASGI server..."
    exec uvicorn backend.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --log-level "$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')" \
        --proxy-headers \
        --forwarded-allow-ips "*"
fi
