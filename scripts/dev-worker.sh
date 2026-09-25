#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Run ONLY the Celery worker (for claim adjudication) from the venv.
# Start this in a second terminal whenever you need background task processing.
# Infra must already be up via: docker compose up -d db redis ollama
#
# Usage:
#   ./scripts/dev-worker.sh
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "No .venv found. Run ./scripts/dev.sh once first to create it."
  exit 2
fi
# shellcheck disable=SC1091
source .venv/bin/activate

set -a
# shellcheck disable=SC1091
source .env
set +a

# Rewrite Docker hostnames back to localhost for host-side processes.
DATABASE_URL="$(printf '%s' "$DATABASE_URL" | sed 's|@db:|@localhost:|')"
REDIS_URL="$(printf '%s' "$REDIS_URL" | sed 's|//redis:|//localhost:|')"
OLLAMA_BASE_URL="$(printf '%s' "$OLLAMA_BASE_URL" | sed 's|//ollama:|//localhost:|')"
export DATABASE_URL REDIS_URL OLLAMA_BASE_URL

exec celery -A src.infrastructure.tasks.celery_app:celery_app worker --loglevel=info "$@"