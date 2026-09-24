#!/bin/sh
set -e

echo "[entrypoint] Starting container"

# Wait for Postgres to accept connections (compose also gates on the healthcheck)
if [ -n "$DATABASE_URL" ]; then
    echo "[entrypoint] Waiting for Postgres ..."
    python3 - <<'PY'
import os
import socket
import time

url = os.environ.get("DATABASE_URL", "")
host_port = url.split("@")[-1].split("/")[0] if "@" in url else ""
if host_port:
    host, port = host_port.rsplit(":", 1)
    port = int(port)
    for i in range(60):
        try:
            with socket.create_connection((host, port), timeout=2):
                break
        except OSError:
            time.sleep(1)
    else:
        print("[entrypoint] Postgres not reachable after 60s, continuing anyway", file=__import__("sys").stderr)
PY
fi

echo "[entrypoint] Applying database migrations..."
alembic upgrade head
echo "[entrypoint] Migrations applied."

exec "$@"