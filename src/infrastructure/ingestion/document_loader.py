from pathlib import Path


def load_and_chunk(file_path: str) -> list[dict]:
    """Load a PDF or DOCX file using UnstructuredLoader with hi_res strategy and return chunked elements."""
    from langchain_unstructured import UnstructuredLoader

    loader = UnstructuredLoader(
        file_path=file_path,
        chunking_strategy="by_title",
        strategy="hi_res",
        max_characters=1200,
        new_after_n_chars=1000,
        combine_text_under_n_chars=200,
        multipage_sections=True,
        overlap=100,
        overlap_all=False,
    )

    documents = loader.load()

    chunks: list[dict] = []
    for doc in documents:
        metadata = doc.metadata or {}
        chunks.append(
            {
                "text": doc.page_content,
                "category": str(metadata.get("category", "")),
                "element_id": str(metadata.get("element_id", "")),
                "parent_id": metadata.get("parent_id"),
                "page_number": metadata.get("page_number"),
            }
        )

    return chunks


def inspect_raw_unstructured_elements(file_path: str) -> list:
    """Temporarily load raw Unstructured elements before chunking for debugging.

    This helper tries to instantiate `UnstructuredLoader` with chunking disabled
    so you can inspect the raw elements returned by the underlying extractor.
    It is intended for temporary local debugging only and should not be used
    in production code.
    """
    from langchain_unstructured import UnstructuredLoader

    # Attempt to disable chunking; different versions of the loader may accept
    # different values (None, "none", or omitting the parameter). Try common
    # options and fall back to a default loader if necessary.
    loader_variants = [
        {"chunking_strategy": None, "strategy": "hi_res"},
        {"chunking_strategy": "none", "strategy": "hi_res"},
        {"strategy": "hi_res"},
    ]

    for params in loader_variants:
        try:
            loader = UnstructuredLoader(file_path=file_path, **params)
            elements = loader.load()
            return elements
        except TypeError:
            # Parameter not accepted by this loader implementation; try next
            continue

    # As a last resort, construct with the same defaults as load_and_chunk
    loader = UnstructuredLoader(
        file_path=file_path,
        chunking_strategy="by_title",
        strategy="hi_res",
        max_characters=1200,
        new_after_n_chars=1000,
        combine_text_under_n_chars=200,
        multipage_sections=True,
        overlap=100,
        overlap_all=False,
    )

    return loader.load()
