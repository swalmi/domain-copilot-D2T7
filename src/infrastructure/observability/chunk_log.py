"""Append-only chunk observability log written to the repository root.

Each successful ingestion run appends one entry to ``chunk_log.json`` containing
the run metadata plus every chunk actually persisted (with its full text), so a
human or script can inspect exactly what entered the knowledge base.

Safety properties:
- Appends are performed atomically (temp file + rename) under a process lock,
  so concurrent uploads cannot corrupt or interleave the file.
- The writer never raises into the ingestion pipeline: a failure is logged as a
  warning and ignored, so observability is strictly best-effort.
- The path is configurable via ``CHUNK_LOG_PATH`` (defaults to the repo root).
"""

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _default_path() -> Path:
    configured = os.environ.get("CHUNK_LOG_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "chunk_log.json"


def _read_existing(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"runs": []}
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        return {"runs": []}
    return data


def append_chunk_log(run_metadata: dict[str, Any], chunks: list[dict[str, Any]]) -> None:
    """Append an ingestion run to the chunk log file.

    :param run_metadata: Correlation id, document id/filename, policy lineage,
        status, counters — merged into the run entry.
    :param chunks: Chunk dicts (chunk_id, section, page, chunk_type,
        content_hash, text) for chunks actually persisted this run.
    """
    with _lock:
        try:
            path = _default_path()
            run: dict[str, Any] = {
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "chunks": chunks,
                **run_metadata,
            }
            data = _read_existing(path)
            data["runs"].append(run)

            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), prefix=".chunk_log.", suffix=".tmp"
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
        except Exception as exc:  # observability must never break ingestion
            logger.warning("Failed to append chunk log: %s", exc)