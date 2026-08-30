from src.infrastructure.ingestion.table_title_linker import link_tables_to_titles


def test_link_tables_to_titles_prepends_parent_text() -> None:
    """Verify that parent title text is prepended to matching table chunks."""
    chunks = [
        {
            "category": "Title",
            "element_id": "parent-101",
            "parent_id": None,
            "text": "SECTION VII — LIMITS OF LIABILITY",
        },
        {
            "category": "Table",
            "element_id": "table-202",
            "parent_id": "parent-101",
            "text": "| Item | Cover |\n| --- | --- |\n| Loss | €500 |",
        },
        {
            "category": "NarrativeText",
            "element_id": "text-303",
            "parent_id": None,
            "text": "Some general policy terms.",
        },
    ]

    result = link_tables_to_titles(chunks)

    assert len(result) == 3
    assert result[0]["text"] == "SECTION VII — LIMITS OF LIABILITY"
    assert (
        result[1]["text"]
        == "SECTION VII — LIMITS OF LIABILITY\n\n| Item | Cover |\n| --- | --- |\n| Loss | €500 |"
    )
    assert result[2]["text"] == "Some general policy terms."


def test_link_tables_to_titles_handles_unmatched_parent_id() -> None:
    """Verify that table chunks remain unchanged when parent_id is missing or unmatched."""
    chunks = [
        {
            "category": "Table",
            "element_id": "table-202",
            "parent_id": "non-existent-id",
            "text": "| Header | Value |",
        },
        {
            "category": "Table",
            "element_id": "table-203",
            "parent_id": None,
            "text": "| Standalone | Table |",
        },
    ]

    result = link_tables_to_titles(chunks)

    assert result[0]["text"] == "| Header | Value |"
    assert result[1]["text"] == "| Standalone | Table |"
