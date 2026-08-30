from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import UserPayload, get_current_user
from src.infrastructure.observability.trace_logger import get_trace_events

router = APIRouter(prefix="/runs", tags=["Observability"])


@router.get("/{correlation_id}", status_code=status.HTTP_200_OK)
async def get_run_trace_events(
    correlation_id: UUID,
    current_user: UserPayload = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Retrieve ordered execution trace log events for a given workflow correlation_id."""
    events = get_trace_events(correlation_id)
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No trace events found for correlation_id '{correlation_id}'.",
        )
    return events
