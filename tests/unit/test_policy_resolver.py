"""Unit tests for resolving a customer policy number to a corpus policy id.

The live failure this guards against: a customer holding ``HO3-2024-884512`` was
auto-denied because coverage retrieval filtered on that exact number while the
corpus stores the form as ``SHELTER-HO3``, yielding zero candidates and the
refusal "No matching policy coverage sections found".
"""

from src.application.retrieval.policy_resolver import resolve_policy_id

CORPUS = [
    "SHELTER-HO3",
    "MAINE-HO-JACKET",
    "ISO-CP-00-10",
    "ISO-CP-10-30",
    "NAIC-MDL-280",
    "NAIC-MDL-632",
    "POL-5009",
    "POL-5010",
]


def test_customer_form_number_resolves_to_corpus_id():
    """The exact number that auto-denied the live claim must now resolve."""
    result = resolve_policy_id("HO3-2024-884512", CORPUS)
    assert result.policy_id == "SHELTER-HO3"
    assert result.method == "segment"
    assert result.is_exact is False


def test_exact_corpus_id_resolves_exactly():
    result = resolve_policy_id("SHELTER-HO3", CORPUS)
    assert result.policy_id == "SHELTER-HO3"
    assert result.method == "exact"
    assert result.is_exact is True


def test_prefixed_number_resolves_to_segment_owner():
    result = resolve_policy_id("POL-5009-99812", CORPUS)
    assert result.policy_id == "POL-5009"
    assert result.method == "segment"


def test_longest_segment_match_wins():
    """A longer distinctive segment beats a shorter one shared by another policy."""
    result = resolve_policy_id("NAIC-MDL-280-2024", ["NAIC-MDL-280", "MDL"])
    assert result.policy_id == "NAIC-MDL-280"
    assert result.matched_segment == "naic"


def test_two_iso_policies_stay_unresolved_rather_than_guessing():
    """``cp`` and ``00`` are below the distinctive-segment floor, so both ISO
    policies match only on ``iso``; refusing is the safe outcome."""
    result = resolve_policy_id("CP0010", ["ISO-CP-00-10", "ISO-CP-10-30"])
    assert result.policy_id is None
    assert result.method == "unresolved"


def test_hyphen_jacket_number_resolves():
    result = resolve_policy_id("HO-JACKET-2021-77", CORPUS)
    assert result.policy_id == "MAINE-HO-JACKET"


def test_number_matching_two_policies_equally_stays_unresolved():
    """A number containing both distinctive segments must not be guessed."""
    result = resolve_policy_id("5009-5010", ["POL-5009", "POL-5010"])
    assert result.policy_id is None
    assert result.method == "unresolved"


def test_single_distinctive_segment_still_resolves():
    """``5010-X`` is ambiguous only in name; one corpus policy owns the segment."""
    result = resolve_policy_id("5010-X", ["POL-5009", "POL-5010"])
    assert result.policy_id == "POL-5010"


def test_unknown_number_stays_unresolved():
    result = resolve_policy_id("ZZ-999-000", CORPUS)
    assert result.policy_id is None
    assert result.method == "unresolved"


def test_empty_and_blank_numbers_stay_unresolved():
    for value in ("", "   ", "---"):
        result = resolve_policy_id(value, CORPUS)
        assert result.policy_id is None
        assert result.method == "unresolved"


def test_empty_corpus_stays_unresolved():
    result = resolve_policy_id("HO3-2024-884512", [])
    assert result.policy_id is None
    assert result.method == "unresolved"
