import sys
import types
from unittest.mock import MagicMock

from langchain_core.documents import Document

from src.infrastructure.ingestion.document_loader import load_and_chunk


def _with_mock_unstructured_loader(mock_loader_cls):
    """Inject a fake langchain_unstructured module into sys.modules so the lazy import resolves to our mock."""
    fake_module = types.ModuleType("langchain_unstructured")
    fake_module.UnstructuredLoader = mock_loader_cls
    token = sys.modules.get("langchain_unstructured")
    sys.modules["langchain_unstructured"] = fake_module
    return token


def _restore_unstructured_module(token):
    """Restore sys.modules to its previous state."""
    if token is None:
        sys.modules.pop("langchain_unstructured", None)
    else:
        sys.modules["langchain_unstructured"] = token


def test_load_and_chunk_parameters_and_metadata_mapping() -> None:
    """Verify that UnstructuredLoader is instantiated with exact parameters and metadata is correctly extracted."""
    mock_doc = Document(
        page_content="Sample document narrative section.",
        metadata={
            "category": "NarrativeText",
            "element_id": "elem-123",
            "parent_id": "parent-456",
            "page_number": 1,
        },
    )

    mock_loader_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.load.return_value = [mock_doc]
    mock_loader_cls.return_value = mock_instance

    token = _with_mock_unstructured_loader(mock_loader_cls)
    try:
        chunks = load_and_chunk("sample_file.pdf")
    finally:
        _restore_unstructured_module(token)

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

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["text"] == "Sample document narrative section."
    assert chunk["category"] == "NarrativeText"
    assert chunk["element_id"] == "elem-123"
    assert chunk["parent_id"] == "parent-456"
    assert chunk["page_number"] == 1


def test_load_and_chunk_docx_file() -> None:
    """Verify that DOCX files rely on auto-detection without format-specific branching."""
    mock_doc = Document(
        page_content="Docx section content",
        metadata={
            "category": "Title",
            "element_id": "elem-789",
        },
    )

    mock_loader_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.load.return_value = [mock_doc]
    mock_loader_cls.return_value = mock_instance

    token = _with_mock_unstructured_loader(mock_loader_cls)
    try:
        chunks = load_and_chunk("sample_policy.docx")
    finally:
        _restore_unstructured_module(token)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["text"] == "Docx section content"
    assert chunk["category"] == "Title"
    assert chunk["element_id"] == "elem-789"
    assert chunk["parent_id"] is None
    assert chunk["page_number"] is None
