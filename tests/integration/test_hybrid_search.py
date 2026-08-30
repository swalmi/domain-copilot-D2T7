from datetime import date
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.retrieval.hybrid_search import hybrid_search
from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.vectorstore.pgvector_store import PgVectorStore


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Fixture providing an active AsyncSession connected to the local database."""
    engine = create_async_engine(
        "postgresql+psycopg://postgres:postgres@localhost:5432/domain_copilot"
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """Fixture providing a mock embedder supporting embed and embed_with_cache."""
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[0.1] * 768)
    embedder.embed_with_cache = AsyncMock(return_value=[0.1] * 768)
    return embedder


@pytest.mark.asyncio
async def test_hybrid_search_semantic_and_keyword(
    db_session: AsyncSession, mock_embedder: AsyncMock
) -> None:
    """Verify hybrid search executes dense vector search and keyword search with RRF fusion."""
    store = PgVectorStore(db_session)

    # 1. Test semantic query: "deer collision" or animal collision terms
    results_semantic = await hybrid_search(
        vector_store=store,
        embedder=mock_embedder,
        query="deer collision animal impact",
        filters={},
        top_k=5,
    )
    assert isinstance(results_semantic, list)

    # 2. Test exact keyword policy phrase search: "Building and Personal Property"
    results_keyword = await hybrid_search(
        vector_store=store,
        embedder=mock_embedder,
        query="Building and Personal Property",
        filters={},
        top_k=5,
    )
    assert isinstance(results_keyword, list)
    assert len(results_keyword) > 0
    assert any("Building" in c.text or "Property" in c.text for c in results_keyword)
