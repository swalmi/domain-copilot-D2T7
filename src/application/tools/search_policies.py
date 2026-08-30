from datetime import date

from src.application.retrieval.hybrid_search import hybrid_search
from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.vector_store import VectorStore


async def search_policies(
    vector_store: VectorStore,
    embedder,
    query: str,
    policy_id: str | None = None,
    effective_date_before: date | None = None,
    top_k: int = 5,
) -> list[CitedChunk]:
    """Retrieve policy coverage chunks using hybrid search pre-filtered by policy_id and effective date."""
    return await hybrid_search(
        vector_store=vector_store,
        embedder=embedder,
        query=query,
        policy_id=policy_id,
        effective_date_before=effective_date_before,
        top_k=top_k,
    )
