from collections.abc import Callable
from typing import Any


def link_tables_to_titles(
    chunks: list[dict],
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict]:
    """Prepend parent title text to table chunks that reference a parent element ID.

    :param on_progress: Optional callback invoked per chunk with
        ``{"index", "total", "element_id", "category"}`` while section linking
        runs, so the live system log shows chunk-level progress.
    """
    id_to_text = {
        chunk["element_id"]: chunk["text"]
        for chunk in chunks
        if chunk.get("element_id") and chunk.get("text")
    }

    result = []
    n = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        if on_progress is not None:
            on_progress(
                {
                    "index": idx,
                    "total": n,
                    "element_id": chunk.get("element_id", ""),
                    "category": chunk.get("category", ""),
                }
            )
        if chunk.get("category") == "Table":
            parent_id = chunk.get("parent_id")
            if parent_id and parent_id in id_to_text:
                parent_text = id_to_text[parent_id]
                table_text = chunk.get("text", "")
                updated_chunk = dict(chunk)
                updated_chunk["text"] = f"{parent_text}\n\n{table_text}"
                result.append(updated_chunk)
                continue
        result.append(chunk)

    return result