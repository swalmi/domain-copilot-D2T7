from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ClaimStatus = Literal[
    "submitted",
    "processing",
    "report_ready",
    "pending_approval",
    "approved",
    "rejected",
    "refused",
    "cancelled",
    "failed",
]

PipelineStage = Literal[
    "understanding",
    "reading_policy",
    "matched",
    "not_matched",
    "building_report",
    "done",
]


class Claim(BaseModel):
    """Represents an insurance claim submitted for processing.

    Adjudication results (payout figures, recommendation) are written back onto
    the entity once the background Celery workflow finishes, so clients polling
    ``GET /claims/{id}`` receive the full report rather than the original record.
    """

    id: UUID
    policy_number: str
    date_of_loss: date
    incident_description: str
    claim_amount_requested: Decimal
    status: ClaimStatus = "submitted"

    user_id: UUID | None = None
    pipeline_stage: PipelineStage | None = None

    correlation_id: UUID | None = None
    celery_task_id: str | None = None

    calculated_payout: Decimal | None = None
    deductible_applied: Decimal | None = None
    policy_limit: Decimal | None = None
    recommendation: str | None = None
    reasoning_text: str | None = None
    citations: list[dict] | None = None
    error_message: str | None = None

    adjusted_payout: Decimal | None = None
    adjuster_notes: str | None = None
    admin_justification: str | None = None

    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )