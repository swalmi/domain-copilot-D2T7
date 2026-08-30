

def load_and_chunk(file_path: str) -> list[dict]:
    """Load a PDF or DOCX file using UnstructuredLoader and return chunked elements with extracted metadata."""
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
