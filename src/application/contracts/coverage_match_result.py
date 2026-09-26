from datetime import date
from typing import Literal

from pydantic import BaseModel

from src.domain.entities.policy import CitedChunk


class CoverageMatchResult(BaseModel):
    """Structured result contract for coverage analysis agent evaluations."""

    policy_id: str
    version_effective_date: date
    applicable_coverage_sections: list[CitedChunk]
    confidence: Literal["matched", "no_match", "ambiguous"]
    policy_resolution: str = "unresolved"
    policy_number_matched: bool = False
