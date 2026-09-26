"""Unit tests for deriving a section key so parent expansion can join siblings.

Live regression: 1956 of 1958 chunks had an empty ``section`` because the loader
required a ``Title`` ancestor via ``parent_id``, which langchain_unstructured
never emits. ``expand_to_parent_sections`` then fell through and returned the
same single fragment, so the LLM never saw a parent section.
"""

import pytest

from src.infrastructure.ingestion.section_titles import (
    detect_section_heading,
    section_key_for,
)


@pytest.mark.parametrize(
    "text",
    [
        "HOMEOWNERS' INSURANCE POLICY",
        "DEFINITIONS USED THROUGHOUT THIS POLICY",
        "SHELTER INSURANCE COMPANIES",
        "Section 2.\n\nDefinitions\n\nThe following terms as used in this section",
        "COVERAGE C-PERSONAL PROPERTY\n\nINSURING AGREEMENT\n\nWe cover accidental",
        "HO-3 (01-07)",
    ],
)
def test_recognises_real_headings(text: str):
    assert detect_section_heading(text)


@pytest.mark.parametrize(
    "text",
    [
        # Table-of-contents leaders, not headings.
        "Coverage D - Additional Living Expense and Loss of Rents ......... 20",
        "Rents .........ccccscsscsecessseeseeseeseeseeseeses 20 Addenda",
        # Prose and extraction debris.
        "damage.",
        "(a) consequential economic damage resulting from such physical damage",
        "4. Bodily injury means:",
        "1-800-927-4357",
        "NAIC Model Laws, Regulations, Guidelines",
        "2007",
        "",
        None,
    ],
)
def test_rejects_non_headings(text: str | None):
    assert detect_section_heading(text) is None


def test_section_key_falls_back_to_page_when_no_heading():
    assert section_key_for("Some body text with no heading at all.", 29) == "page 29"


def test_section_key_prefers_heading_over_page():
    assert section_key_for("HOMEOWNERS' INSURANCE POLICY", 1) == "HOMEOWNERS' INSURANCE POLICY"


def test_section_key_without_page_still_groups():
    assert section_key_for("plain text", None) == "page unknown"


def test_heading_detection_is_deterministic():
    """Backfill must be idempotent, so the same text always yields the same key."""
    text = "COVERAGE A - DWELLING PROPERTY"
    assert section_key_for(text, 15) == section_key_for(text, 15)
