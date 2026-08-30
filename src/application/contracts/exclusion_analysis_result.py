from decimal import Decimal

from pydantic import BaseModel

from src.domain.entities.policy import CitedChunk


class ExclusionAnalysisResult(BaseModel):
    """Structured result contract for exclusion analysis and policy limit evaluation."""

    exclusions_found: list[CitedChunk]
    deductible_applied: Decimal
    policy_limit: Decimal
    calculated_payout: Decimal
    anomaly_flags: list[str]
