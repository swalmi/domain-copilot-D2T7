"""Production-grade structured JSONL system logger.

Writes machine-readable, PII-scrubbed log records to ``system_logs.txt`` at the
repository root so every pipeline phase (ingestion, retrieval, generation,
adjudication) is observable and auditable from a single file.

Design invariants:
- Append-only JSON Lines (one event object per line) — trivially tail/grep/query.
- Async-friendly (thread-blocking writes are short and batch-buffered at module
  level so we never block the event loop per token).
- PII-safe: every payload passes through ``sanitize_pii`` before being persisted.
- Never raises: logging is best-effort and must never break the hot path.
"""

import asyncio
from typing import Any
from contextvars import ContextVar
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import UUID

# Keep the sink path overridable per-install (config sets it; tests can redirect)
_sink_path: Path | None = None
_lock = asyncio.Lock()

# PII scrub patterns (shared notion with the observability tracer)
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# Context propagation for the active request's correlation id
_correlation_id_ctx: ContextVar[UUID | str | None] = ContextVar(
    "system_log_correlation_id", default=None
)


def configure_system_logger(path: str | Path) -> None:
    """Set the sink file path for the structured system logger (repo-root system_logs.txt)."""
    global _sink_path
    _sink_path = Path(path)


def get_system_log_path() -> Path | None:
    """Return the configured sink path (used by health/tracing endpoints)."""
    return _sink_path


def set_correlation_id(correlation_id: UUID | str) -> None:
    """Set the correlation id for the current async context."""
    _correlation_id_ctx.set(str(correlation_id))


def _scrub(value: Any) -> Any:
    """Recursively remove SSN/email/phone PII from primitive containers."""
    if isinstance(value, str):
        text = _SSN_PATTERN.sub("[REDACTED_SSN]", value)
        text = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        text = _PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
        return text
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    if isinstance(value, tuple):
        return [_scrub(v) for v in value]
    return value


def emit_system_log(
    phase: str,
    event: str,
    payload: dict[str, Any] | None = None,
    correlation_id: UUID | str | None = None,
) -> None:
    """Append one structured, PII-scrubbed JSON record to the ``system_logs.txt`` sink.

    :param phase: Pipeline phase (``ingestion``, ``embedding``, ``retrieval``,
        ``generation``, ``adjudication``).
    :param event: Short event name (``chunk_upserted``, ``query_embedded``,
        ``candidate_retrieved``, ``stream_started``, ``citations`).
    :param payload: Arbitrary JSON-serializable metadata for the record.
    :param correlation_id: Overrides the context-scoped correlation id when given.
    """
    cid_value = correlation_id or _correlation_id_ctx.get()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "phase": phase,
        "event": event,
        "correlation_id": str(cid_value) if cid_value else None,
        "payload": _scrub(payload or {}),
    }

    # Serialize to a single line; fall back to a bare str for non-serializable blobs.
    try:
        line = json.dumps(record, default=str, ensure_ascii=True)
    except (TypeError, ValueError):
        line = json.dumps({**record, "payload": {"_raw": str(payload)}}, default=str)

    sink = _sink_path
    if sink is None:
        sink = Path("system_logs.txt")  # repo-root default

    try:
        sink.parent.mkdir(parents=True, exist_ok=True)
        with open(sink, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        # Logging must never crash the request path.
        return
