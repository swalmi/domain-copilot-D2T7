from datetime import date
from unittest.mock import AsyncMock
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.retrieval.hybrid_search import hybrid_search
from src.domain.entities.policy import CitedChunk
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
async def test_version_matching_risk_guard_hard_filter(
    db_session: AsyncSession, mock_embedder: AsyncMock
) -> None:
    """Verify hard metadata pre-filtering prevents newer policy version chunks from leaking into results."""
    store = PgVectorStore(db_session)

    policy_id = "POL-RISK-GUARD"

    # Older version 2005 (effective 2005-01-01)
    chunk_old = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Building debris removal coverage limit is $10,000 under the 2005 policy version.",
        source_document="policy_v2005.pdf",
        section="COVERAGE A - DEBRIS REMOVAL",
        page=1,
        policy_id=policy_id,
        version="2005",
        effective_date=date(2005, 1, 1),
        chunk_type="narrative",
        policy_type="commercial_property",
    )

    # Newer version 2024 (effective 2024-01-01) - semantically identical/closer text
    chunk_new = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Building debris removal coverage limit is $25,000 under the 2024 updated policy version.",
        source_document="policy_v2024.pdf",
        section="COVERAGE A - DEBRIS REMOVAL",
        page=1,
        policy_id=policy_id,
        version="2024",
        effective_date=date(2024, 1, 1),
        chunk_type="narrative",
        policy_type="commercial_property",
    )

    embedding = [0.1] * 768
    await store.upsert(chunk_old, embedding)
    await store.upsert(chunk_new, embedding)

    # Execute hybrid search with effective_date_before=2010-01-01
    results = await hybrid_search(
        vector_store=store,
        embedder=mock_embedder,
        query="Building debris removal coverage limit",
        policy_id=policy_id,
        effective_date_before=date(2010, 1, 1),
        top_k=10,
    )

    # Risk Guard Verification: Only old version (2005) must be returned; newer (2024) must never leak into candidates
    assert len(results) > 0
    assert all(c.effective_date <= date(2010, 1, 1) for c in results)
    assert not any(c.version == "2024" for c in results)
    assert any(c.version == "2005" for c in results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_version_matching_risk_guard_on_seeded_corpus(
    db_session: AsyncSession, mock_embedder: AsyncMock
) -> None:
    """Verify version matching risk guard against seeded ISO-CP-00-10 versions (2000 vs 2012)."""
    store = PgVectorStore(db_session)

    # Query for ISO-CP-00-10 policy effective before 2005-01-01
    results = await hybrid_search(
        vector_store=store,
        embedder=mock_embedder,
        query="Building and Personal Property Coverage Form",
        policy_id="ISO-CP-00-10",
        effective_date_before=date(2005, 1, 1),
        top_k=10,
    )

    if results:
        assert all(c.effective_date <= date(2005, 1, 1) for c in results)
        assert not any(c.version == "2012-10" for c in results)
