from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from src.domain.entities.adjudication import Adjudication
from src.domain.entities.claim import Claim
from src.domain.entities.policy import CitedChunk, PolicyVersion
from src.domain.errors.domain_errors import (
    DomainError,
    InsufficientEvidenceError,
    InvalidClaimStateError,
    PolicyNotFoundError,
    PolicyVersionMismatchError,
)


def test_claim_entity_instantiation() -> None:
    """Verify that Claim entity attributes are correctly initialized."""
    claim_id = uuid4()
    claim = Claim(
        id=claim_id,
        policy_number="POL-98765",
        date_of_loss=date(2026, 2, 14),
        incident_description="Water leak in kitchen",
        claim_amount_requested=Decimal("1250.50"),
        status="submitted",
    )
    assert claim.id == claim_id
    assert claim.policy_number == "POL-98765"
    assert claim.date_of_loss == date(2026, 2, 14)
    assert claim.incident_description == "Water leak in kitchen"
    assert claim.claim_amount_requested == Decimal("1250.50")
    assert claim.status == "submitted"


def test_policy_version_entity_instantiation() -> None:
    """Verify that PolicyVersion entity attributes are correctly initialized."""
    policy_version = PolicyVersion(
        policy_id="POL-98765",
        version="v2.0",
        effective_date=date(2026, 1, 1),
        policy_type="home",
    )
    assert policy_version.policy_id == "POL-98765"
    assert policy_version.version == "v2.0"
    assert policy_version.effective_date == date(2026, 1, 1)
    assert policy_version.policy_type == "home"


def test_cited_chunk_entity_instantiation() -> None:
    """Verify that CitedChunk entity attributes are correctly initialized."""
    chunk_id = uuid4()
    cited_chunk = CitedChunk(
        chunk_id=chunk_id,
        text="Coverage includes water damage from plumbing discharge.",
        source_document="home_policy_v2.pdf",
        section="Section 4.1 - Water Damage",
        page=12,
        policy_id="POL-98765",
        version="v2.0",
        effective_date=date(2026, 1, 1),
        chunk_type="narrative",
    )
    assert cited_chunk.chunk_id == chunk_id
    assert cited_chunk.text == "Coverage includes water damage from plumbing discharge."
    assert cited_chunk.source_document == "home_policy_v2.pdf"
    assert cited_chunk.section == "Section 4.1 - Water Damage"
    assert cited_chunk.page == 12
    assert cited_chunk.policy_id == "POL-98765"
    assert cited_chunk.version == "v2.0"
    assert cited_chunk.effective_date == date(2026, 1, 1)
    assert cited_chunk.chunk_type == "narrative"


def test_adjudication_entity_instantiation() -> None:
    """Verify that Adjudication entity attributes and nested citations are correctly initialized."""
    adjudication_id = uuid4()
    claim_id = uuid4()
    chunk_id = uuid4()

    citation = CitedChunk(
        chunk_id=chunk_id,
        text="Excludes damage due to neglect.",
        source_document="home_policy_v2.pdf",
        section="Section 5.2 - Exclusions",
        page=15,
        policy_id="POL-98765",
        version="v2.0",
        effective_date=date(2026, 1, 1),
        chunk_type="table",
    )

    adjudication = Adjudication(
        id=adjudication_id,
        claim_id=claim_id,
        recommendation="approve",
        calculated_payout=Decimal("1250.50"),
        citations=[citation],
        confidence="high",
        status="pending_approval",
    )
    assert adjudication.id == adjudication_id
    assert adjudication.claim_id == claim_id
    assert adjudication.recommendation == "approve"
    assert adjudication.calculated_payout == Decimal("1250.50")
    assert len(adjudication.citations) == 1
    assert adjudication.citations[0].chunk_id == chunk_id
    assert adjudication.confidence == "high"
    assert adjudication.status == "pending_approval"


def test_domain_errors_raisable_and_catchable() -> None:
    """Verify that custom domain exceptions inherit from DomainError and retain error messages."""
    errors = [
        PolicyVersionMismatchError("Version mismatch detected"),
        InsufficientEvidenceError("Not enough document citations"),
        PolicyNotFoundError("Policy POL-98765 not found"),
        InvalidClaimStateError("Claim state cannot transition to approved"),
    ]

    for err in errors:
        with pytest.raises(DomainError) as exc_info:
            raise err
        assert str(exc_info.value) == err.message
