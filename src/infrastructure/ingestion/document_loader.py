from pathlib import Path


def load_and_chunk(file_path: str) -> list[dict]:
    """Load a PDF using Unstructured's partition API (hi_res) and return chunk dicts.

    This avoids relying on the LangChain `UnstructuredLoader` wrapper which
    can fail when package versions for `unstructured` / `unstructured-inference`
    diverge. We call `partition_pdf(..., chunking_strategy=...)` directly and
    map Element objects to simple dicts for downstream use.
    """
    from unstructured.partition.pdf import partition_pdf

    # Call partition_pdf with chunking parameters similar to previous loader usage.
    elements = partition_pdf(
        filename=file_path,
        strategy="hi_res",
        chunking_strategy="by_title",
        max_characters=1200,
        new_after_n_chars=1000,
        combine_text_under_n_chars=200,
        multipage_sections=True,
    )

    chunks: list[dict] = []
    for el in elements:
        # element.text is the primary textual content for most Element types
        text = getattr(el, "text", None)

        # element metadata may be an ElementMetadata dataclass; safely extract common fields
        meta = getattr(el, "metadata", None)
        def _meta_get(key):
            if meta is None:
                return None
            # try dict-like access
            try:
                return meta.get(key)
            except Exception:
                pass
            # try attribute access
            return getattr(meta, key, None)

        chunks.append(
            {
                "text": text,
                "type": type(el).__name__,
                "element_id": _meta_get("element_id"),
                "parent_id": _meta_get("parent_id"),
                "page_number": _meta_get("page_number") or _meta_get("page") or _meta_get("page_number_display"),
                "raw_metadata": meta,
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
    # Prefer direct partition call for raw elements to avoid wrapper mismatches.
    try:
        from unstructured.partition.pdf import partition_pdf

        elements = partition_pdf(filename=file_path, strategy="fast")
        if elements:
            return elements
    except Exception:
        # fall back to hi_res if fast fails
        pass

    try:
        from unstructured.partition.pdf import partition_pdf

        return partition_pdf(filename=file_path, strategy="hi_res")
    except Exception:
        # Last resort: fall back to pypdf text extraction
        try:
            from pypdf import PdfReader

            reader = PdfReader(file_path)
            pages = []
            for p in reader.pages:
                text = p.extract_text() or ""
                pages.append(text)
            return pages
        except Exception:
            return []
