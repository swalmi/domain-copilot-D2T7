from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from src.domain.entities.policy import CitedChunk


class AdjudicationDraft(BaseModel):
    """Structured result contract for claim adjudication recommendation drafts."""

    recommendation: Literal["approve", "deny", "partial"]
    calculated_payout: Decimal
    reasoning_text: str
    citations: list[CitedChunk]
    confidence: Literal["high", "medium", "low"]
