from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
import uuid

import pytest

from src.application.agents.adjudication_drafter import AdjudicationDrafter
from src.application.contracts.coverage_match_result import CoverageMatchResult
from src.application.contracts.exclusion_analysis_result import (
    ExclusionAnalysisResult,
)
from src.domain.entities.claim import Claim
from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.claim_repository import ClaimRepository
from src.domain.interfaces.llm_provider import LLMProvider


class InMemoryClaimRepository(ClaimRepository):
    """In-memory test implementation of ClaimRepository."""

    def __init__(self) -> None:
        self.claims: dict[uuid.UUID, Claim] = {}

    async def save(self, claim: Claim) -> None:
        self.claims[claim.id] = claim

    async def get_by_id(self, claim_id: uuid.UUID) -> Claim | None:
        return self.claims.get(claim_id)


@pytest.fixture
def mock_llm_provider() -> AsyncMock:
    """Fixture providing a mock LLM provider for agent execution."""
    provider = AsyncMock(spec=LLMProvider)
    provider.complete = AsyncMock(return_value="Recommend approval of claim based on Coverage Section I.")
    return provider


@pytest.mark.asyncio
async def test_adjudication_drafter_preserves_payout_and_gated_write(
    mock_llm_provider: AsyncMock,
) -> None:
    """Verify AdjudicationDrafter preserves exact calculated_payout and updates claim status to pending_approval."""
    drafter = AdjudicationDrafter(llm_provider=mock_llm_provider)
    claim_repo = InMemoryClaimRepository()

    claim_id = uuid.uuid4()
    claim = Claim(
        id=claim_id,
        policy_number="ISO-CP-00-10",
        date_of_loss=date(2026, 1, 1),
        incident_description="Building fire loss",
        claim_amount_requested=Decimal("5000.00"),
        status="submitted",
    )
    await claim_repo.save(claim)

    chunk = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Building property loss coverage section.",
        source_document="cp0010.pdf",
        section="COVERAGE FORM",
        page=1,
        policy_id="ISO-CP-00-10",
        version="2012-10",
        effective_date=date(2012, 10, 1),
        chunk_type="narrative",
        policy_type="commercial_property",
    )

    coverage_match = CoverageMatchResult(
        policy_id="ISO-CP-00-10",
        version_effective_date=date(2012, 10, 1),
        applicable_coverage_sections=[chunk],
        confidence="matched",
    )

    exclusion_result = ExclusionAnalysisResult(
        exclusions_found=[],
        deductible_applied=Decimal("500.00"),
        policy_limit=Decimal("10000.00"),
        calculated_payout=Decimal("4500.00"),
        anomaly_flags=[],
    )

    draft = await drafter.run(
        claim=claim,
        coverage_match=coverage_match,
        exclusion_result=exclusion_result,
        claim_repo=claim_repo,
    )

    # 1. Assert calculated_payout equals exclusion_result.calculated_payout (exact math preservation)
    assert draft.calculated_payout == Decimal("4500.00")
    assert draft.recommendation == "partial"
    assert "Recommend approval" in draft.reasoning_text

    # 2. Assert claim status transitioned to "pending_approval" ONLY, NEVER "approved"
    saved_claim = await claim_repo.get_by_id(claim_id)
    assert saved_claim is not None
    assert saved_claim.status == "pending_approval"
    assert saved_claim.status != "approved"
