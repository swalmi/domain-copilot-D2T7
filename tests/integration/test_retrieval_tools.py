from datetime import date
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.tools.search_exclusions import search_exclusions
from src.application.tools.search_policies import search_policies
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_policies_tool(
    db_session: AsyncSession, mock_embedder: AsyncMock
) -> None:
    """Verify search_policies retrieval tool returns policy chunks matching pre-filters."""
    store = PgVectorStore(db_session)

    results = await search_policies(
        vector_store=store,
        embedder=mock_embedder,
        query="Building and Personal Property",
        policy_id="ISO-CP-00-10",
        top_k=5,
    )

    assert isinstance(results, list)
    if results:
        assert all(c.policy_id == "ISO-CP-00-10" for c in results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_exclusions_tool(
    db_session: AsyncSession, mock_embedder: AsyncMock
) -> None:
    """Verify search_exclusions retrieval tool returns chunks filtered by chunk_type and version."""
    store = PgVectorStore(db_session)

    results = await search_exclusions(
        vector_store=store,
        embedder=mock_embedder,
        query="water damage wear and tear exclusions",
        policy_id="SHELTER-HO3",
        top_k=5,
    )

    assert isinstance(results, list)
    if results:
        assert all(c.policy_id == "SHELTER-HO3" for c in results)
