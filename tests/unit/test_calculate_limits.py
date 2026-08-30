from decimal import Decimal

from src.application.tools.calculate_limits import calculate_limits_and_deductibles


def test_claim_below_deductible() -> None:
    """Verify claim below deductible yields 0 payout."""
    res = calculate_limits_and_deductibles(
        claim_amount=Decimal("300.00"),
        deductible=Decimal("500.00"),
        policy_limit=Decimal("10000.00"),
    )
    assert res["payout"] == Decimal("0.00")
    assert res["deductible_applied"] == Decimal("500.00")
    assert res["limit_applied"] == Decimal("10000.00")
    assert res["capped_by_limit"] is False


def test_claim_exactly_at_deductible() -> None:
    """Verify claim exactly equal to deductible yields 0 payout."""
    res = calculate_limits_and_deductibles(
        claim_amount=Decimal("500.00"),
        deductible=Decimal("500.00"),
        policy_limit=Decimal("10000.00"),
    )
    assert res["payout"] == Decimal("0.00")
    assert res["capped_by_limit"] is False


def test_claim_between_deductible_and_limit() -> None:
    """Verify normal claim between deductible and limit calculates exact net payout."""
    res = calculate_limits_and_deductibles(
        claim_amount=Decimal("2500.00"),
        deductible=Decimal("500.00"),
        policy_limit=Decimal("10000.00"),
    )
    assert res["payout"] == Decimal("2000.00")
    assert res["capped_by_limit"] is False


def test_claim_above_policy_limit() -> None:
    """Verify claim resulting in payout exceeding policy limit is capped to policy limit."""
    res = calculate_limits_and_deductibles(
        claim_amount=Decimal("15000.00"),
        deductible=Decimal("500.00"),
        policy_limit=Decimal("10000.00"),
    )
    assert res["payout"] == Decimal("10000.00")
    assert res["capped_by_limit"] is True


def test_claim_exactly_at_limit_boundary() -> None:
    """Verify claim where net amount equals policy limit exactly triggers capped_by_limit flag."""
    res = calculate_limits_and_deductibles(
        claim_amount=Decimal("10500.00"),
        deductible=Decimal("500.00"),
        policy_limit=Decimal("10000.00"),
    )
    assert res["payout"] == Decimal("10000.00")
    assert res["capped_by_limit"] is True
