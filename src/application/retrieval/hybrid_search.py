from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.vector_store import VectorStore
from src.infrastructure.observability.retrieval_logger import create_retrieval_log
from src.infrastructure.observability.system_logger import emit_system_log


@dataclass
class RetrievalConfidence:
    """Why a retrieval did or did not clear the answer/refuse threshold."""

    top_rrf_score: float
    max_rrf_score: float
    rrf_ratio: float
    top_cosine_distance: float | None
    is_confident: bool
    reason: str

#: Candidates fetched per leg before RRF fusion. A wider pool lets a chunk that
#: one leg ranks poorly (e.g. keyword rank 22 of a dense-favoured query) still
#: contribute its second leg's score and reach the final top-k.
CANDIDATE_POOL = 40

#: RRF's ``k``. Kept as a module constant so the confidence maths below and the
#: fusion itself cannot drift apart.
RRF_K = 60

#: RRF scores are bounded: with ``n`` legs the best possible score is
#: ``n / (1 + RRF_K)``. Thresholds must therefore be expressed relative to this
#: ceiling, never as a bare number.
MAX_RRF_SCORE = 2 / (1 + RRF_K)

# NOTE: there is deliberately no floor on the RRF ratio.
#:
#: RRF consumes ranked lists, so the top hit is always rank 1 in *some* leg and
#: always scores at least ``1/61`` against the ``2/61`` ceiling -- a ratio of
#: exactly 0.5 for ANY non-empty retrieval. A floor below 0.5 (such as the old
#: literal 0.01) is therefore unreachable, which is why the safety net never
#: fired. A floor above 0.5 is equally wrong in the other direction: requiring
#: cross-leg agreement refuses correct answers, because the dense and lexical
#: legs legitimately disagree even when the query vector is an exact corpus
#: match (measured ratio 0.5 at cosine distance 0.0). ``rrf_ratio`` is kept as a
#: logged diagnostic only; ``MAX_COSINE_DISTANCE`` does the actual gating.

#: Absolute ceiling on the best dense cosine distance (0 = identical, 1 =
#: opposite).
#:
#: RRF is rank-based, so it cannot tell a relevant hit from an arbitrary nearest
#: neighbour: an out-of-corpus question still ranks *some* chunk first and
#: scores a perfect 0.0328. Cosine distance is the only absolute relevance
#: signal available before generation, so it gates as well.
#:
#: Measured on the 25-case golden set: in-corpus questions top out at 0.30 and
#: out-of-corpus questions start at 0.30, so this boundary is deliberately set
#: on the weak side — it is a floor, not a classifier, and exists to stop the
#: model answering from a corpus that has nothing relevant to say.
MAX_COSINE_DISTANCE = 0.35

#: Fused candidates handed to generation.
#:
#: The fused list interleaves dual-leg hits (both dense and lexical rank them
#: highly, score ~0.027) with single-leg hits (~0.016). Cutting at 5 discarded
#: the strongest lexical evidence outright, which defeated the point of fixing
#: the keyword leg: the chunk holding the answer for "property excluded from
#: Coverage A" ranks 7th. Six keeps the extra candidate without materially
#: enlarging the prompt. Eight scored 100% on the 20-item retrieval proxy, but
#: that is too small a sample to justify a wider context.
RETRIEVAL_TOP_K = 6


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
    """Execute hybrid search returning (CitedChunk, RRF_score) tuples."""
    results, _ = await hybrid_search_with_confidence(
        vector_store=vector_store,
        embedder=embedder,
        query=query,
        filters=filters,
        policy_id=policy_id,
        policy_type=policy_type,
        effective_date_before=effective_date_before,
        top_k=top_k,
    )
    return results


async def hybrid_search_with_confidence(
    vector_store: VectorStore,
    embedder,
    query: str,
    filters: dict | None = None,
    policy_id: str | None = None,
    policy_type: str | None = None,
    effective_date_before: date | None = None,
    top_k: int = 5,
    max_cosine_distance: float | None = None,
) -> tuple[list[tuple[CitedChunk, float]], RetrievalConfidence]:
    """Execute hybrid search, also returning whether retrieval is confident enough to answer."""
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
        query_embedding=query_embedding, filters=filters_dict, top_k=CANDIDATE_POOL
    )
    keyword_results = await vector_store.keyword_search(
        query_text=query, filters=filters_dict, top_k=CANDIDATE_POOL
    )

    fused_results = reciprocal_rank_fusion_with_scores(
        [dense_results, keyword_results], k=RRF_K
    )
    distance_ceiling = (
        MAX_COSINE_DISTANCE if max_cosine_distance is None else max_cosine_distance
    )
    top_score = fused_results[0][1] if fused_results else 0.0
    rrf_ratio = top_score / MAX_RRF_SCORE if MAX_RRF_SCORE else 0.0
    top_distance = await vector_store.top_cosine_distance(
        query_embedding=query_embedding, filters=filters_dict
    )
    if not fused_results:
        is_confident, reason = False, "no_results"
    elif top_distance is not None and top_distance > distance_ceiling:
        is_confident, reason = False, "max_cosine_distance_exceeded"
    else:
        is_confident, reason = True, "retrieval_confident"
    confidence = RetrievalConfidence(
        top_rrf_score=top_score,
        max_rrf_score=MAX_RRF_SCORE,
        rrf_ratio=round(rrf_ratio, 4),
        top_cosine_distance=top_distance,
        is_confident=is_confident,
        reason=reason,
    )
    embedder_name = str(getattr(embedder, "model_name", getattr(embedder, "__class__.__name__", "unknown")))
    has_cache = hasattr(embedder, "embed_with_cache")
    create_retrieval_log(
        query=query,
        query_embedding=list(query_embedding),
        dense_results=dense_results,
        keyword_results=keyword_results,
        fused_results=fused_results,
        top_k=top_k,
        filters=filters_dict,
        embedder_name=str(embedder_name),
        cache_hit=has_cache,
    )
    emit_system_log(
        "retrieval",
        "query_embedded",
        {"query_length": len(query), "embed_cache": hasattr(embedder, "embed_with_cache")},
    )
    emit_system_log(
        "retrieval",
        "fusion_complete",
        {
            "dense_candidates": len(dense_results),
            "keyword_candidates": len(keyword_results),
            "fused_returned": min(len(fused_results), top_k),
            "top_chunk_id": str(fused_results[0][0].chunk_id) if fused_results else None,
            "top_rrf_score": round(confidence.top_rrf_score, 5),
            "max_rrf_score": round(confidence.max_rrf_score, 5),
            "rrf_ratio": confidence.rrf_ratio,
            "top_cosine_distance": confidence.top_cosine_distance,
            "is_confident": confidence.is_confident,
            "confidence_reason": confidence.reason,
        },
    )
    return fused_results[:top_k], confidence


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
