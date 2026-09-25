import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

logger = __import__("logging").getLogger(__name__)

_lock = threading.Lock()


def _default_dir() -> Path:
    configured = os.environ.get("DOCUMENT_CHUNKS_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "chunks"


def _default_path(document_id: UUID) -> Path:
    return _default_dir() / f"{document_id}.json"


def _read_existing(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"runs": []}


def write_document_chunks(document_id: UUID, metadata: dict[str, Any], chunks: list[dict[str, Any]]) -> None:
    """Write a per-document JSON file containing all chunks and metadata.

    :param document_id: The document UUID (used as the filename).
    :param metadata: Document metadata (filename, policy_id, policy_type,
        version, effective_date, status, chunks_count, inserted_count, ...).
    :param chunks: List of chunk dicts with chunk_id, section, page,
        chunk_type, content_hash, text.
    """
    with _lock:
        try:
            path = _default_path(document_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "document_id": str(document_id),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                **metadata,
                "chunks": chunks,
            }
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), prefix=".chunks.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(entry, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, path)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as exc:
            logger.warning("Failed to write document chunks file: %s", exc)


def delete_document_chunks(document_id: UUID) -> None:
    """Delete the JSON file for a document when it is removed."""
    with _lock:
        try:
            path = _default_path(document_id)
            if path.exists():
                path.unlink()
        except Exception as exc:
            logger.warning("Failed to delete document chunks file: %s", exc)
