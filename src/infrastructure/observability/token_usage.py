"""Per-request LLM token and cost accounting sink (FR-9).

Appends one JSON record per LLM call to ``token_usage.json`` at the repository
root, correlatable via the ambient correlation id from the system logger.
"""

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.infrastructure.observability.system_logger import (
    _correlation_id_ctx,
    emit_system_log,
)

logger = logging.getLogger(__name__)
_lock = threading.Lock()

# Rough USD per 1M tokens by provider family. Local Ollama is $0.
_PRICING_PER_1M = {
    "ollama": 0.0,
    "openrouter": 0.0,  # free-tier models used in this deployment
}


def _ambient_correlation_id() -> str | None:
    """Read the ambient correlation id from the system-logger context var."""
    value = _correlation_id_ctx.get()
    return str(value) if value else None


def _default_path() -> Path:
    configured = os.environ.get("TOKEN_USAGE_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "token_usage.json"


def estimate_tokens(text: str) -> int:
    """Estimate token count from character length (~4 chars/token heuristic)."""
    return max(1, (len(text) + 3) // 4)


def estimate_cost_usd(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Return estimated USD cost for a call using the static pricing table."""
    rate = _PRICING_PER_1M.get(provider.lower(), 0.0)
    total = prompt_tokens + completion_tokens
    return round(rate * total / 1_000_000, 8)


def record_token_usage(
    *,
    provider: str,
    model: str,
    operation: str,
    prompt: str = "",
    completion: str = "",
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    correlation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one token/cost usage record and emit a system-log event.

    :param provider: Provider name (``ollama`` / ``openrouter``).
    :param model: Concrete model identifier.
    :param operation: ``complete`` | ``stream`` | ``call_tool`` | ``embed``.
    :param prompt: Raw prompt text used for estimation when token counts missing.
    :param completion: Raw completion text used for estimation when missing.
    :param prompt_tokens: Provider-reported prompt tokens when available.
    :param completion_tokens: Provider-reported completion tokens when available.
    :param correlation_id: Optional override; defaults to ambient correlation id.
    :param metadata: Extra JSON-serializable fields (agent, claim_id, etc.).
    """
    resolved_cid = correlation_id or _ambient_correlation_id()
    p_tokens = prompt_tokens if prompt_tokens is not None else estimate_tokens(prompt)
    c_tokens = (
        completion_tokens if completion_tokens is not None else estimate_tokens(completion)
    )
    cost = estimate_cost_usd(provider, p_tokens, c_tokens)
    entry = {
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "provider": provider,
        "model": model,
        "operation": operation,
        "prompt_tokens": p_tokens,
        "completion_tokens": c_tokens,
        "total_tokens": p_tokens + c_tokens,
        "cost_usd": cost,
        "correlation_id": resolved_cid,
        "metadata": metadata or {},
    }

    path = _default_path()
    with _lock:
        try:
            data: dict[str, Any]
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                data = loaded if isinstance(loaded, dict) and isinstance(loaded.get("entries"), list) else {"entries": []}
            except (OSError, ValueError):
                data = {"entries": []}
            data["entries"].append(entry)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".token_usage.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception as exc:
            logger.warning("Failed to write token usage record: %s", exc)

    emit_system_log(
        "usage",
        "token_accounted",
        {
            "provider": provider,
            "model": model,
            "operation": operation,
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "total_tokens": p_tokens + c_tokens,
            "cost_usd": cost,
            **(metadata or {}),
        },
        correlation_id=resolved_cid,
    )
    return entry


def load_token_usage() -> list[dict[str, Any]]:
    """Return all persisted token usage entries (empty list if missing/corrupt)."""
    path = _default_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data["entries"]
    except (OSError, ValueError):
        pass
    return []


def summarize_token_usage(entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Aggregate token/cost totals overall and by provider/correlation_id."""
    rows = entries if entries is not None else load_token_usage()
    by_provider: dict[str, dict[str, Any]] = {}
    by_correlation: dict[str, dict[str, Any]] = {}
    total_prompt = total_completion = total_cost = 0
    for r in rows:
        pt = int(r.get("prompt_tokens") or 0)
        ct = int(r.get("completion_tokens") or 0)
        cost = float(r.get("cost_usd") or 0.0)
        total_prompt += pt
        total_completion += ct
        total_cost += cost
        prov = r.get("provider") or "unknown"
        slot = by_provider.setdefault(
            prov, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0, "calls": 0}
        )
        slot["prompt_tokens"] += pt
        slot["completion_tokens"] += ct
        slot["total_tokens"] += pt + ct
        slot["cost_usd"] = round(slot["cost_usd"] + cost, 8)
        slot["calls"] += 1
        cid = r.get("correlation_id")
        if cid:
            cslot = by_correlation.setdefault(
                str(cid),
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0, "calls": 0},
            )
            cslot["prompt_tokens"] += pt
            cslot["completion_tokens"] += ct
            cslot["total_tokens"] += pt + ct
            cslot["cost_usd"] = round(cslot["cost_usd"] + cost, 8)
            cslot["calls"] += 1
    return {
        "total_calls": len(rows),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_prompt + total_completion,
        "total_cost_usd": round(total_cost, 8),
        "by_provider": by_provider,
        "by_correlation_id": by_correlation,
    }
