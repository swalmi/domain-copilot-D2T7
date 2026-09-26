"""Derive a section key for a chunk so parent expansion can join siblings.

``context_expander`` expands a retrieved chunk by pulling every chunk sharing its
``(policy_id, version, section)``. That only works if ``section`` is populated,
and it was not: the loader looked for a ``Title`` ancestor via ``parent_id``,
but the installed ``langchain_unstructured`` emits ``category="CompositeElement"``
with ``parent_id=None``, so 1956 of 1958 chunks stored an empty section and
expansion silently degraded to "return the same single fragment".

The heading is instead recovered from the chunk text itself, which survives every
extraction strategy because ``by_title`` chunking keeps the heading at the front
of the merged element.
"""

import re

#: Three or more consecutive dots marks a table-of-contents leader, not a heading.
_DOT_LEADER = re.compile(r"\.{3,}")

#: Numbered or named structural headings, e.g. "Section 2.", "Coverage A - Dwelling".
_STRUCTURAL = re.compile(
    r"^(?:section|coverage|part|article|schedule|endorsement|appendix|chapter)\b",
    re.IGNORECASE,
)

#: A heading line longer than this is body text that merely starts with a capital.
MAX_HEADING_CHARS = 90

#: Real headings are short; a long "sentence" in caps is usually body text.
MAX_HEADING_WORDS = 12

_CAPS = re.compile(r"[A-Z]")


def detect_section_heading(text: str | None) -> str | None:
    """Return the section heading a chunk opens with, or None if it does not.

    Recognises structural headings ("Section 2.", "Coverage A - Dwelling") and
    short all-caps headings ("DEFINITIONS USED THROUGHOUT THIS POLICY"), while
    rejecting table-of-contents lines, prose, and extraction debris.
    """
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    first = lines[0]

    if _DOT_LEADER.search(first):
        return None
    if len(first) > MAX_HEADING_CHARS or len(first.split()) > MAX_HEADING_WORDS:
        return None
    if _STRUCTURAL.match(first):
        return first.rstrip(".").strip() or first
    letters = [c for c in first if c.isalpha()]
    # Require genuine capitals; a numeric-only line such as "2007" is not a heading.
    if letters and sum(1 for c in letters if _CAPS.match(c)) / len(letters) > 0.7:
        return first.rstrip(":.").strip() or first
    return None


def section_key_for(text: str | None, page: int | None) -> str:
    """Return the section key used to group sibling chunks for expansion.

    Falls back to the page number when no heading can be recovered, so fragments
    that share a page still expand into their surrounding page context instead of
    expanding to nothing.
    """
    heading = detect_section_heading(text)
    if heading:
        return heading
    return f"page {page}" if page is not None else "page unknown"
