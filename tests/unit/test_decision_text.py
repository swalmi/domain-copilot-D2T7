"""Unit tests for the decision-text guard that keeps model refusals out of claims."""

from src.application.agents.decision_text import (
    ensure_decision_text,
    looks_like_model_refusal,
)

FALLBACK = (
    "Automated decision summary (the language model did not return a usable "
    "justification): coverage match 'matched' for policy ISO-CP-00-10; "
    "recommendation partial."
)

GOOD_JUSTIFICATION = (
    "The claim for building fire damage is covered under Section I. "
    "A deductible of $500.00 was applied and no applicable exclusions were found."
)


def test_detects_reported_refusal_string() -> None:
    assert looks_like_model_refusal("I can't fulfill this request.")


def test_detects_other_refusal_shapes() -> None:
    for text in (
        "I cannot fulfill this request.",
        "I’m sorry, but I am unable to assist with that.",
        "As an AI language model, I must decline.",
        "I cannot comply with that instruction.",
    ):
        assert looks_like_model_refusal(text), text


def test_detects_empty_or_too_short_output() -> None:
    assert looks_like_model_refusal(None)
    assert looks_like_model_refusal("")
    assert looks_like_model_refusal("Denied.")
    assert looks_like_model_refusal(".... ...")


def test_accepts_substantive_justification() -> None:
    assert not looks_like_model_refusal(GOOD_JUSTIFICATION)
    assert not looks_like_model_refusal(
        "Coverage matched. Calculated payout 4500.00 after a 500.00 deductible "
        "against a policy limit of 10000.00; recommendation partial."
    )


def test_ensure_returns_usable_text_unchanged() -> None:
    assert ensure_decision_text(GOOD_JUSTIFICATION, FALLBACK) == GOOD_JUSTIFICATION


def test_ensure_replaces_refusal_with_fallback() -> None:
    assert (
        ensure_decision_text("I can't fulfill this request.", FALLBACK) == FALLBACK
    )


def test_ensure_replaces_empty_with_fallback() -> None:
    assert ensure_decision_text(None, FALLBACK) == FALLBACK
