"""Append-only claim adjudication observability log written to the repository root.

Each completed claim (successful or failed) appends one entry to ``claim_logs.json``
containing the full claim record plus the coverage match, exclusion analysis, and
adjudication draft with every chunk's text, so a human or script can inspect the
entire adjudication decision.

Safety properties:
- Appends are atomic (temp file + rename) under a process lock.
- The writer never raises into the adjudication pipeline: a failure is logged as
  a warning and ignored.
- The path is configurable via ``CLAIM_LOG_PATH`` (defaults to the repo root).
"""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _default_path() -> Path:
    configured = os.environ.get("CLAIM_LOG_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "claim_logs.json"


def _read_existing(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"claims": []}
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        return {"claims": []}
    return data


def append_claim_log(entry: dict[str, Any]) -> None:
    """Append a claim adjudication record to the claim log file.

    :param entry: Full claim data (claim fields, coverage match, exclusion analysis,
        draft, timestamps, status, error_message if failed).
    """
    with _lock:
        try:
            path = _default_path()
            data = _read_existing(path)
            data["claims"].append(entry)

            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), prefix=".claim_log.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, path)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as exc:  # observability must never break adjudication
            logger.warning("Failed to append claim log: %s", exc)
