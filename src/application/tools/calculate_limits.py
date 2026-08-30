from decimal import Decimal


def calculate_limits_and_deductibles(
    claim_amount: Decimal, deductible: Decimal, policy_limit: Decimal
) -> dict:
    """Calculate claim payout deterministically applying deductibles and policy limits."""
    payout = min(max(claim_amount - deductible, Decimal(0)), policy_limit)
    return {
        "payout": payout,
        "deductible_applied": deductible,
        "limit_applied": policy_limit,
        "capped_by_limit": payout == policy_limit,
    }
