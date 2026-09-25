"""Persisting an adjudication draft must keep the machine decision and the prose apart."""

from datetime import date
from decimal import Decimal

from src.application.contracts.adjudication_draft import AdjudicationDraft
from src.domain.entities.claim import Claim
from src.infrastructure.tasks.claim_tasks import apply_draft_to_claim


def _claim() -> Claim:
    return Claim(
        id=__import__("uuid").uuid4(),
        policy_number="ISO-CP-00-10",
        date_of_loss=date(2026, 1, 1),
        incident_description="Building fire loss",
        claim_amount_requested=Decimal("5000.00"),
        status="processing",
    )


def test_draft_persists_recommendation_and_justification_separately() -> None:
    claim = _claim()
    draft = AdjudicationDraft(
        recommendation="partial",
        calculated_payout=Decimal("4500.00"),
        reasoning_text=(
            "The claim for building fire damage is covered under Section I and "
            "a deductible of $500.00 was applied to the calculated payout."
        ),
        citations=[],
        confidence="high",
        deductible_applied=Decimal("500.00"),
        policy_limit=Decimal("10000.00"),
    )

    apply_draft_to_claim(claim, draft)

    assert claim.recommendation == "partial"
    assert claim.reasoning_text == draft.reasoning_text
    assert claim.status == "report_ready"
    assert claim.pipeline_stage == "done"
    assert claim.calculated_payout == Decimal("4500.00")


def test_justification_never_lands_in_the_recommendation_column() -> None:
    """Regression: the reasoning text used to overwrite `recommendation`, so the
    corp queue showed the justification (or a model refusal) as the AI decision."""
    claim = _claim()
    draft = AdjudicationDraft(
        recommendation="deny",
        calculated_payout=Decimal("0.00"),
        reasoning_text="I can't fulfill this request.",
        citations=[],
        confidence="low",
    )

    apply_draft_to_claim(claim, draft)

    assert claim.recommendation == "deny"
    assert claim.recommendation != claim.reasoning_text
