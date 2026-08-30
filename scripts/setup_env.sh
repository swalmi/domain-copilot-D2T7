#!/usr/bin/env bash
# Reproducible environment setup for this project.
# Creates a local venv at .venv and installs pinned packages from requirements.lock.

set -euo pipefail
PYTHON=${PYTHON:-python3}
VENV_DIR=.venv
LOCKFILE=requirements.lock

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON" >&2
  exit 2
fi

if [ ! -f "$LOCKFILE" ]; then
  echo "Lockfile $LOCKFILE not found. Run from repo root." >&2
  exit 2
fi

echo "Creating virtualenv in $VENV_DIR..."
$PYTHON -m venv "$VENV_DIR"

echo "Activating venv and upgrading pip/tools..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel

echo "Installing pinned packages from $LOCKFILE..."
python -m pip install -r "$LOCKFILE"

echo "Done. To use the environment:"
echo "  source $VENV_DIR/bin/activate"
echo "Run the inspector (fast strategy by default):"
echo "  python scripts/inspect_unstructured.py /path/to/file.pdf"

echo "Notes:"
echo "- This lockfile pins exact versions. If you need newer dependencies, update" \
     "requirements.txt and regenerate a lockfile after testing."
echo "- The unstructured hi_res strategy may download heavy models from Hugging Face." \
     "Set HF_TOKEN in your environment to increase rate limits if needed."
