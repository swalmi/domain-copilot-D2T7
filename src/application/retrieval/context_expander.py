from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.vector_store import VectorStore


async def expand_to_parent_sections(
    chunks: list[CitedChunk], vector_store: VectorStore
) -> list[dict]:
    """Expand retrieved small CitedChunk entities into full parent-section context for LLM processing."""
    expanded_results: list[dict] = []

    for chunk in chunks:
        full_section_text = chunk.text

        if chunk.section:
            section_chunks = await vector_store.get_chunks_by_section(
                policy_id=chunk.policy_id,
                version=chunk.version,
                section=chunk.section,
            )
            if section_chunks:
                full_section_text = "\n\n".join(c.text for c in section_chunks)

        expanded_results.append({
            "cited_chunk": chunk,
            "context_for_llm": full_section_text,
        })

    return expanded_results
