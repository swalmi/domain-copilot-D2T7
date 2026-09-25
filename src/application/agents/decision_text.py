"""Guards that keep model refusals and meta chatter out of decision justifications.

A small local model occasionally answers an adjudication prompt with a refusal
("I can't fulfill this request.") or an apology instead of a justification. That
text ends up in the corp approvals UI as the AI decision, which is not an
acceptable artefact of an adjudication pipeline — so such outputs are detected
and replaced with a deterministic summary built from structured facts.
"""

#: Phrases that mark a language-model refusal/apology rather than a justification.
#: Matching is case-insensitive and substring based (curly apostrophes normalised).
REFUSAL_MARKERS: tuple[str, ...] = (
    "i can't fulfill",
    "i cannot fulfill",
    "unable to fulfill",
    "cannot fulfill this request",
    "i can't help",
    "i cannot help",
    "i can't assist",
    "i cannot assist",
    "i'm sorry",
    "i am sorry",
    "i apologize",
    "i apologise",
    "as an ai",
    "as a language model",
    "i'm unable",
    "i am unable",
    "i must decline",
    "i cannot comply",
    "i can't comply",
    "i cannot provide",
    "i can't provide",
    "i cannot generate",
    "i can't generate",
    "i cannot write",
    "i can't write",
    "i won't be able",
    "i am not able",
    "i'm not able",
)

#: Shorter than any usable adjudication justification.
_MIN_LENGTH = 40


def _normalise(text: str) -> str:
    return (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("\u201f", '"')
        .strip()
        .lower()
    )


def looks_like_model_refusal(text: str | None) -> bool:
    """True when ``text`` is empty, too short to be a justification, or a refusal."""
    if not text:
        return True
    normalised = _normalise(text)
    if not normalised or not any(ch.isalpha() for ch in normalised):
        return True
    if len(normalised) < _MIN_LENGTH:
        return True
    return any(marker in normalised for marker in REFUSAL_MARKERS)


def ensure_decision_text(text: str | None, fallback: str) -> str:
    """Return ``text`` unless it is unusable as a decision justification.

    ``fallback`` must be deterministic and built from structured facts (payout,
    deductible, limit, recommendation) so a weak model can never surface a
    refusal string as the AI decision.
    """
    if looks_like_model_refusal(text):
        return fallback
    return text  # type: ignore[return-value]
