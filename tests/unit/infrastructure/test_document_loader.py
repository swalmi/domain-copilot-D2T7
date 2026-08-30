from datetime import date
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from src.infrastructure.ingestion.document_loader import load_and_chunk


def test_load_and_chunk_parameters_and_metadata_mapping() -> None:
    """Verify that UnstructuredLoader is instantiated with exact parameters and metadata is correctly enriched."""
    mock_title_doc = Document(
        page_content="SECTION I — COVERAGE",
        metadata={
            "category": "Title",
            "element_id": "parent-456",
            "parent_id": None,
            "page_number": 1,
        },
    )
    mock_narrative_doc = Document(
        page_content="Sample document narrative section.",
        metadata={
            "category": "NarrativeText",
            "element_id": "elem-123",
            "parent_id": "parent-456",
            "page_number": 1,
        },
    )
    mock_table_doc = Document(
        page_content="| Limit | €1000 |",
        metadata={
            "category": "Table",
            "element_id": "table-789",
            "parent_id": "parent-456",
            "page_number": 1,
        },
    )

    sample_date = date(2026, 1, 1)

    with patch(
        "langchain_unstructured.UnstructuredLoader"
    ) as mock_loader_cls:
        mock_instance = MagicMock()
        mock_instance.load.return_value = [
            mock_title_doc,
            mock_narrative_doc,
            mock_table_doc,
        ]
        mock_loader_cls.return_value = mock_instance

        chunks = load_and_chunk(
            file_path="sample_file.pdf",
            policy_id="POL-12345",
            policy_type="home",
            version="1.0",
            effective_date=sample_date,
        )

        mock_loader_cls.assert_called_once_with(
            file_path="sample_file.pdf",
            chunking_strategy="by_title",
            strategy="hi_res",
            max_characters=1200,
            new_after_n_chars=1000,
            combine_text_under_n_chars=200,
            multipage_sections=True,
            overlap=100,
            overlap_all=False,
        )

        assert len(chunks) == 3

        expected_fields = {
            "policy_id",
            "policy_type",
            "version",
            "effective_date",
            "chunk_type",
            "section",
            "page_number",
            "element_id",
        }

        for chunk in chunks:
            assert expected_fields.issubset(chunk.keys())
            assert chunk["policy_id"] == "POL-12345"
            assert chunk["policy_type"] == "home"
            assert chunk["version"] == "1.0"
            assert chunk["effective_date"] == sample_date
            assert chunk["page_number"] == 1
            assert chunk["element_id"] is not None

        title_chunk = chunks[0]
        assert title_chunk["element_id"] == "parent-456"
        assert title_chunk["category"] == "Title"
        assert title_chunk["chunk_type"] == "narrative"
        assert title_chunk["section"] is None

        narrative_chunk = chunks[1]
        assert narrative_chunk["element_id"] == "elem-123"
        assert narrative_chunk["text"] == "Sample document narrative section."
        assert narrative_chunk["category"] == "NarrativeText"
        assert narrative_chunk["chunk_type"] == "narrative"
        assert narrative_chunk["section"] == "SECTION I — COVERAGE"

        table_chunk = chunks[2]
        assert table_chunk["element_id"] == "table-789"
        assert table_chunk["category"] == "Table"
        assert table_chunk["chunk_type"] == "table"
        assert table_chunk["section"] == "SECTION I — COVERAGE"


def test_load_and_chunk_docx_file() -> None:
    """Verify that DOCX files receive policy metadata and defaults."""
    mock_doc = Document(
        page_content="Docx section content",
        metadata={
            "category": "Title",
            "element_id": "elem-789",
        },
    )

    sample_date = date(2025, 6, 15)

    with patch(
        "langchain_unstructured.UnstructuredLoader"
    ) as mock_loader_cls:
        mock_instance = MagicMock()
        mock_instance.load.return_value = [mock_doc]
        mock_loader_cls.return_value = mock_instance

        chunks = load_and_chunk(
            file_path="sample_policy.docx",
            policy_id="POL-999",
            policy_type="auto",
            version="2.1",
            effective_date=sample_date,
        )

        assert len(chunks) == 1
        chunk = chunks[0]

        expected_fields = {
            "policy_id",
            "policy_type",
            "version",
            "effective_date",
            "chunk_type",
            "section",
            "page_number",
            "element_id",
        }
        assert expected_fields.issubset(chunk.keys())

        assert chunk["text"] == "Docx section content"
        assert chunk["category"] == "Title"
        assert chunk["chunk_type"] == "narrative"
        assert chunk["policy_id"] == "POL-999"
        assert chunk["policy_type"] == "auto"
        assert chunk["version"] == "2.1"
        assert chunk["effective_date"] == sample_date
        assert chunk["section"] is None
