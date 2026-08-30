from datetime import date
from uuid import UUID

from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.vector_store import VectorStore


def reciprocal_rank_fusion_with_scores(
    result_lists: list[list[CitedChunk]], k: int = 60
) -> list[tuple[CitedChunk, float]]:
    """Fuse multiple ranked lists of CitedChunk entities using RRF, returning (CitedChunk, score) tuples."""
    scores: dict[UUID, float] = {}
    chunk_map: dict[UUID, CitedChunk] = {}

    for result_list in result_lists:
        for rank, chunk in enumerate(result_list, start=1):
            chunk_id = chunk.chunk_id
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk
            scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (rank + k))

    sorted_chunk_ids = sorted(
        scores.keys(), key=lambda cid: scores[cid], reverse=True
    )
    return [(chunk_map[cid], scores[cid]) for cid in sorted_chunk_ids]


def reciprocal_rank_fusion(
    result_lists: list[list[CitedChunk]], k: int = 60
) -> list[CitedChunk]:
    """Fuse multiple ranked lists of CitedChunk entities using Reciprocal Rank Fusion."""
    fused_scores = reciprocal_rank_fusion_with_scores(result_lists, k=k)
    return [chunk for chunk, _ in fused_scores]


async def hybrid_search_with_scores(
    vector_store: VectorStore,
    embedder,
    query: str,
    filters: dict | None = None,
    policy_id: str | None = None,
    policy_type: str | None = None,
    effective_date_before: date | None = None,
    top_k: int = 5,
) -> list[tuple[CitedChunk, float]]:
    """Execute hybrid dense vector and keyword search returning (CitedChunk, RRF_score) tuples."""
    filters_dict = dict(filters) if filters else {}
    if policy_id is not None:
        filters_dict["policy_id"] = policy_id
    if policy_type is not None:
        filters_dict["policy_type"] = policy_type
    if effective_date_before is not None:
        filters_dict["effective_date_before"] = effective_date_before

    if hasattr(embedder, "embed_with_cache"):
        query_embedding = await embedder.embed_with_cache(query)
    elif hasattr(embedder, "embed"):
        query_embedding = await embedder.embed(query)
    else:
        query_embedding = await embedder(query)

    dense_results = await vector_store.search(
        query_embedding=query_embedding, filters=filters_dict, top_k=20
    )
    keyword_results = await vector_store.keyword_search(
        query_text=query, filters=filters_dict, top_k=20
    )

    fused_results = reciprocal_rank_fusion_with_scores(
        [dense_results, keyword_results], k=60
    )
    return fused_results[:top_k]


async def hybrid_search(
    vector_store: VectorStore,
    embedder,
    query: str,
    filters: dict | None = None,
    policy_id: str | None = None,
    policy_type: str | None = None,
    effective_date_before: date | None = None,
    top_k: int = 5,
) -> list[CitedChunk]:
    """Execute hybrid dense vector and keyword search fused with Reciprocal Rank Fusion."""
    fused_with_scores = await hybrid_search_with_scores(
        vector_store=vector_store,
        embedder=embedder,
        query=query,
        filters=filters,
        policy_id=policy_id,
        policy_type=policy_type,
        effective_date_before=effective_date_before,
        top_k=top_k,
    )
    return [chunk for chunk, _ in fused_with_scores]
