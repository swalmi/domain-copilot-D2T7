#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Resilient local backend launcher for the memory-constrained D2T7 box.
#
# Unlike scripts/dev.sh it:
#   - runs uvicorn WITHOUT --reload (no mid-request restarts)
#   - caps glibc malloc arenas to keep Python RSS low (trim ~200-400MB)
#   - auto-restarts uvicorn if it dies (global OOM has killed it before),
#     so a transient 502/Bad Gateway self-heals in a few seconds
#
# Usage:  setsid nohup ./scripts/dev-resilient.sh >/tmp/opencode/backend.log 2>&1 &
# Stop:   pkill -f "uvicorn src.api.main:app"
# ---------------------------------------------------------------------------
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "ERROR: .venv missing (run scripts/dev.sh once)" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

export DATABASE_URL="$(printf '%s' "$DATABASE_URL" | sed 's|@db:|@localhost:|')"
export REDIS_URL="$(printf '%s' "$REDIS_URL" | sed 's|//redis:|//localhost:|')"
export OLLAMA_BASE_URL="$(printf '%s' "$OLLAMA_BASE_URL" | sed 's|//ollama:|//localhost:|')"
export OLLAMA_CHAT_MODEL="${OLLAMA_CHAT_MODEL:-llama3.2:1b}"

# Trim Python RSS: single malloc arena + pymalloc jemalloc-style fragmentation control.
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
export PYTHONMALLOC=malloc

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "[dev-resilient] Starting uvicorn on ${HOST}:${PORT} (auto-restart on exit)."
while true; do
  .venv/bin/uvicorn src.api.main:app --host "$HOST" --port "$PORT" >>"${BACKEND_LOG:-/tmp/opencode/backend.log}" 2>&1
  code=$?
  echo "[dev-resilient] uvicorn exited (${code}) at $(date -u +%Y-%m-%dT%H:%M:%SZ); restarting in 3s..."
  sleep 3
done