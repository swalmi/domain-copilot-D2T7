"""Keep the committed diagram source and the rendered copy in ARCHITECTURE.md in sync.

`docs/ARCHITECTURE.md` embeds each diagram so GitHub renders it, and
`docs/diagrams/*.mmd` holds the same Mermaid as standalone source for export and
linting. Two copies drift silently unless a test compares them, which is exactly
the failure this file prevents.
"""

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[2] / "docs"
ARCHITECTURE = DOCS / "ARCHITECTURE.md"
DIAGRAMS = sorted((DOCS / "diagrams").glob("*.mmd"))

FENCE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def test_diagram_source_files_exist() -> None:
    assert len(DIAGRAMS) >= 7, (
        "expected the C4 L1-L3, sequence, data-flow, ER and layer-dependency "
        f"sources, found {len(DIAGRAMS)}"
    )


def test_architecture_md_embeds_every_diagram() -> None:
    """Each .mmd file must appear, byte for byte, in a mermaid block."""
    body = ARCHITECTURE.read_text(encoding="utf-8")
    blocks = [block.strip() for block in FENCE.findall(body)]

    for source in DIAGRAMS:
        assert source.read_text(encoding="utf-8").strip() in blocks, (
            f"{source.name} is not embedded verbatim in {ARCHITECTURE.name}. "
            "Copy the .mmd contents into a ```mermaid fence, or delete the "
            ".mmd if the diagram only lives inline."
        )


def test_every_mermaid_block_has_a_source_file() -> None:
    """The reverse direction: no orphan diagrams in the prose document."""
    body = ARCHITECTURE.read_text(encoding="utf-8")
    blocks = {block.strip() for block in FENCE.findall(body)}
    sources = {source.read_text(encoding="utf-8").strip() for source in DIAGRAMS}

    orphans = blocks - sources
    assert not orphans, (
        f"{len(orphans)} mermaid block(s) in {ARCHITECTURE.name} have no "
        f"{DOCS.name}/diagrams/*.mmd source. Commit the source too."
    )


@pytest.mark.parametrize("source", DIAGRAMS, ids=lambda p: p.name)
def test_diagram_is_well_formed(source: Path) -> None:
    """Cheap sanity checks so a typo cannot ship a silently broken diagram.

    Deliberately does not try to parse Mermaid — bracket counting is not a valid
    check here, because ``||--o{`` in an ER diagram is cardinality notation rather
    than an unbalanced brace.
    """
    text = source.read_text(encoding="utf-8")
    assert text.strip(), f"{source.name} is empty"

    first = next(
        (line for line in text.splitlines() if line.strip() and not line.startswith("%%")),
        "",
    )
    assert first.split()[0] in {
        "graph",
        "flowchart",
        "sequenceDiagram",
        "erDiagram",
        "classDiagram",
        "stateDiagram",
    }, f"{source.name} does not begin with a Mermaid diagram declaration, got {first!r}"

    assert "External service" not in text, (
        f"{source.name} still contains the placeholder 'External service' "
        "instead of the real LLM provider"
    )


def test_mermaid_fences_are_balanced() -> None:
    body = ARCHITECTURE.read_text(encoding="utf-8")
    assert body.count("```mermaid") == len(FENCE.findall(body)), (
        "an unterminated ```mermaid fence in ARCHITECTURE.md would break rendering"
    )
