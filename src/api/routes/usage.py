from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from src.api.deps import UserPayload, require_role
from src.infrastructure.observability.token_usage import (
    load_token_usage,
    summarize_token_usage,
)

router = APIRouter(prefix="/usage", tags=["Observability"])


@router.get("", status_code=status.HTTP_200_OK)
async def get_usage_summary(
    correlation_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=5000),
    current_user: UserPayload = Depends(require_role("corp")),
) -> dict[str, Any]:
    """Return token/cost accounting totals plus recent usage entries (FR-9)."""
    entries = load_token_usage()
    if correlation_id is not None:
        cid = str(correlation_id)
        entries = [e for e in entries if str(e.get("correlation_id")) == cid]
    recent = entries[-limit:]
    summary = summarize_token_usage(entries)
    return {
        "summary": summary,
        "entries": recent,
        "filtered_by_correlation_id": str(correlation_id) if correlation_id else None,
    }


@router.get("/summary", status_code=status.HTTP_200_OK)
async def get_usage_totals(
    current_user: UserPayload = Depends(require_role("corp")),
) -> dict[str, Any]:
    """Return aggregate token/cost totals without the per-call entry list."""
    return summarize_token_usage()
