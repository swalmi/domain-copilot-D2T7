def link_tables_to_titles(chunks: list[dict]) -> list[dict]:
    """Prepend parent title text to table chunks that reference a parent element ID."""
    id_to_text = {
        chunk["element_id"]: chunk["text"]
        for chunk in chunks
        if chunk.get("element_id") and chunk.get("text")
    }

    result = []
    for chunk in chunks:
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
