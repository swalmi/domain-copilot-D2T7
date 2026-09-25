#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-command local dev runner.
#   - Infra (Postgres, Redis, Ollama) run in Docker
#   - Backend runs from a local Python venv (fast reload, no image builds)
#   - Worker is NOT started here (run scripts/dev-worker.sh when needed)
#
# Usage:
#   ./scripts/dev.sh                 # default: host 0.0.0.0, port 8000
#   ./scripts/dev.sh --port 8001
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Console scripts (alembic, uvicorn) put .venv/bin on sys.path instead of the
# repo root, so make `src.*` importable without an editable install.
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python3}"

require() {
  command -v "$1" >/dev/null 2>&1 && return 0
  echo "ERROR: missing host dependency: $1" >&2
  return 1
}

require docker || { echo "Install Docker: https://docs.docker.com/get-docker/" >&2; exit 2; }
require "$PYTHON"
require curl

# Print a helpful warning (not fatal) for optional system packages.
for tool in tesseract pdftotext; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "WARNING: '$tool' not found on host."
    echo "         Document parsing uses it. Install via:"
    echo "           Ubuntu/Debian: sudo apt install $tool"
    echo "           Fedora:        sudo dnf install $tool"
  fi
done

# ---------------------------------------------------------------------------
# 1. Environment variable overrides for running FROM the host.
#    .env uses Docker hostnames (db, redis, ollama); rewrite them to localhost.
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  echo "No .env found. Copying .env.example -> .env"
  cp .env.example .env
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

DATABASE_URL="$(printf '%s' "$DATABASE_URL" | sed 's|@db:|@localhost:|')"
REDIS_URL="$(printf '%s' "$REDIS_URL" | sed 's|//redis:|//localhost:|')"
OLLAMA_BASE_URL="$(printf '%s' "$OLLAMA_BASE_URL" | sed 's|//ollama:|//localhost:|')"
export DATABASE_URL REDIS_URL OLLAMA_BASE_URL

# ---------------------------------------------------------------------------
# 2. Python venv + dependencies (idempotent via stamp file).
# ---------------------------------------------------------------------------
if [ ! -d .venv ]; then
  echo "[dev] Creating virtualenv (.venv)..."
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f .venv/.req-stamp ] || [ requirements.txt -nt .venv/.req-stamp ]; then
  echo "[dev] Installing Python dependencies (first run may take a while)..."
  python -m pip install -q --upgrade pip setuptools wheel
  # CPU-only torch avoids downloading the ~1.5GB CUDA stack on dev machines.
  python -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch
  python -m pip install -q -r requirements.txt
  # Installed separately: it pins onnxruntime<=1.19.2 which conflicts with
  # unstructured-inference (needs >=1.25). Works fine at runtime with newer onnxruntime.
  python -m pip install -q --no-deps langchain-unstructured==0.1.6
  touch .venv/.req-stamp
fi

# ---------------------------------------------------------------------------
# 3. Start infra containers (db, redis, ollama). Worker stays out by default.
# ---------------------------------------------------------------------------
echo "[dev] Starting infra (db, redis, ollama) via Docker..."
docker compose up -d db redis ollama

# ---------------------------------------------------------------------------
# 4. Wait for Postgres, then apply migrations automatically.
# ---------------------------------------------------------------------------
echo "[dev] Waiting for Postgres at localhost:5432 ..."
python - <<'PY'
import os, socket, sys
_, port = ("localhost", int(os.environ.get("DB_PORT", "5432")))
for _ in range(60):
    try:
        with socket.create_connection(("localhost", port), timeout=2):
            break
    except OSError:
        pass
else:
    sys.exit("ERROR: Postgres not reachable after 60s")
PY

echo "[dev] Applying DB migrations..."
alembic upgrade head

# ---------------------------------------------------------------------------
# 5. Run the backend.
# ---------------------------------------------------------------------------
echo "[dev] Starting backend on ${HOST}:${PORT} (Ctrl+C to stop)"
# Only watch application code: the repo root also holds .venv, node_modules and
# the runtime log sinks (workflow.log, system_logs.txt, token_usage.json), which
# the API writes on every request — watching those reloaded the app constantly.
exec uvicorn src.api.main:app --reload --reload-dir "$ROOT/src" --host "$HOST" --port "$PORT"