"""Map a customer policy number onto a corpus policy id.

Customers type their own policy number (``HO3-2024-884512``); the corpus is keyed
by internal ids (``SHELTER-HO3``). Filtering retrieval by the raw policy number
therefore matches nothing, which made every claim look uncovered and auto-deny.

Resolution is intentionally conservative: it either produces one unambiguous
corpus id or nothing at all, so a genuinely foreign policy number falls through
to unfiltered retrieval rather than being forced onto the wrong policy.
"""

from dataclasses import dataclass
from typing import Literal

#: A hyphen-separated segment must be at least this long to identify a policy.
#: This keeps short or ambiguous segments ("cp", "00", "10") from matching
#: unrelated numbers that merely contain the same digits.
MIN_SEGMENT_LENGTH = 3

ResolutionMethod = Literal["exact", "segment", "unresolved"]


@dataclass(frozen=True)
class PolicyResolution:
    """Outcome of resolving a customer policy number to a corpus policy id."""

    policy_id: str | None
    method: ResolutionMethod
    matched_segment: str | None = None

    @property
    def is_exact(self) -> bool:
        """True when the policy number was already a corpus id."""
        return self.method == "exact"


def _canonical(value: str) -> str:
    """Lowercase and drop every separator so spellings can be compared."""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _segments(policy_id: str) -> list[str]:
    """Split a corpus policy id into its meaningful hyphen-separated segments."""
    return [seg for seg in policy_id.lower().split("-") if seg]


def resolve_policy_id(
    policy_number: str, available_policy_ids: list[str]
) -> PolicyResolution:
    """Resolve ``policy_number`` to a single corpus ``policy_id`` if unambiguous.

    Resolution order:

    1. ``exact`` — the policy number already equals a corpus id.
    2. ``segment`` — a distinctive segment of a corpus id (e.g. ``ho3``) appears
       in the policy number once separators are ignored. The longest match wins,
       so ``SHELTER-HO3`` beats a policy that merely shares a short segment.
    3. ``unresolved`` — nothing matched, or several policies matched equally
       well. The caller should retrieve unfiltered rather than guess.
    """
    number = _canonical(policy_number)
    if not number:
        return PolicyResolution(None, "unresolved")

    for policy_id in available_policy_ids:
        if _canonical(policy_id) == number:
            return PolicyResolution(policy_id, "exact")

    best: tuple[int, str, str] | None = None
    ambiguous = False
    for policy_id in available_policy_ids:
        for segment in _segments(policy_id):
            if len(segment) < MIN_SEGMENT_LENGTH:
                continue
            if segment not in number:
                continue
            if best is None or len(segment) > best[0]:
                best = (len(segment), policy_id, segment)
                ambiguous = False
            elif len(segment) == best[0] and policy_id != best[1]:
                ambiguous = True

    if best is None or ambiguous:
        return PolicyResolution(None, "unresolved")
    return PolicyResolution(best[1], "segment", best[2])
