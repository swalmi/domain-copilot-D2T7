from datetime import date
from decimal import Decimal
import uuid

import pytest
from pydantic import ValidationError

from src.application.contracts import (
    AdjudicationDraft,
    CoverageMatchResult,
    ExclusionAnalysisResult,
)
from src.domain.entities.policy import CitedChunk


def make_chunk() -> CitedChunk:
    """Helper fixture to create a valid CitedChunk instance for contract testing."""
    return CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Coverage section text for dwelling property loss.",
        source_document="ho3_policy.pdf",
        section="SECTION I - COVERAGES",
        page=1,
        policy_id="POL-HO3",
        version="1.0",
        effective_date=date(2026, 1, 1),
        chunk_type="narrative",
        policy_type="home",
    )


def test_coverage_match_result_valid_and_invalid() -> None:
    """Verify CoverageMatchResult instantiates with valid data and raises ValidationError on invalid Literals."""
    chunk = make_chunk()
    valid_res = CoverageMatchResult(
        policy_id="POL-HO3",
        version_effective_date=date(2026, 1, 1),
        applicable_coverage_sections=[chunk],
        confidence="matched",
    )
    assert valid_res.policy_id == "POL-HO3"
    assert valid_res.confidence == "matched"

    with pytest.raises(ValidationError):
        CoverageMatchResult(
            policy_id="POL-HO3",
            version_effective_date=date(2026, 1, 1),
            applicable_coverage_sections=[chunk],
            confidence="invalid_confidence_string",  # type: ignore[arg-type]
        )


def test_exclusion_analysis_result_valid_and_invalid() -> None:
    """Verify ExclusionAnalysisResult handles Decimal types and validates structure."""
    chunk = make_chunk()
    valid_res = ExclusionAnalysisResult(
        exclusions_found=[chunk],
        deductible_applied=Decimal("500.00"),
        policy_limit=Decimal("50000.00"),
        calculated_payout=Decimal("4500.00"),
        anomaly_flags=["high_claim_amount"],
    )
    assert valid_res.deductible_applied == Decimal("500.00")
    assert valid_res.anomaly_flags == ["high_claim_amount"]

    with pytest.raises(ValidationError):
        ExclusionAnalysisResult(
            exclusions_found="not_a_list",  # type: ignore[arg-type]
            deductible_applied=Decimal("500.00"),
            policy_limit=Decimal("50000.00"),
            calculated_payout=Decimal("4500.00"),
            anomaly_flags=[],
        )


def test_adjudication_draft_valid_and_invalid() -> None:
    """Verify AdjudicationDraft instantiates properly and enforces valid Literals."""
    chunk = make_chunk()
    valid_draft = AdjudicationDraft(
        recommendation="approve",
        calculated_payout=Decimal("1200.50"),
        reasoning_text="Property loss covered under Section I.",
        citations=[chunk],
        confidence="high",
    )
    assert valid_draft.recommendation == "approve"
    assert valid_draft.confidence == "high"

    with pytest.raises(ValidationError):
        AdjudicationDraft(
            recommendation="maybe_approve",  # type: ignore[arg-type]
            calculated_payout=Decimal("1200.50"),
            reasoning_text="Reasoning",
            citations=[chunk],
            confidence="high",
        )

    with pytest.raises(ValidationError):
        AdjudicationDraft(
            recommendation="approve",
            calculated_payout=Decimal("1200.50"),
            reasoning_text="Reasoning",
            citations=[chunk],
            confidence="ultra_high",  # type: ignore[arg-type]
        )
