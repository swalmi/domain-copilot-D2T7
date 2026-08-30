from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from src.domain.entities.policy import CitedChunk


class Adjudication(BaseModel):
    """Represents the automated or manual adjudication decision for a claim."""

    id: UUID
    claim_id: UUID
    recommendation: Literal["approve", "deny", "partial"]
    calculated_payout: Decimal
    citations: list[CitedChunk]
    confidence: Literal["high", "medium", "low"]
    status: Literal["pending_approval", "approved", "rejected", "edited"]
