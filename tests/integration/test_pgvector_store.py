from datetime import date
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.entities.policy import CitedChunk
from src.infrastructure.db.models import ChunkModel, DocumentModel
from src.infrastructure.vectorstore.pgvector_store import PgVectorStore


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Fixture providing an active AsyncSession connected to the local test database."""
    engine = create_async_engine(
        "postgresql+psycopg://postgres:postgres@localhost:5432/domain_copilot"
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        await session.execute(text("TRUNCATE TABLE chunks, documents CASCADE;"))
        await session.commit()
        yield session
        await session.execute(text("TRUNCATE TABLE chunks, documents CASCADE;"))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_and_filtered_search(db_session: AsyncSession) -> None:
    """Verify that PgVectorStore correctly filters dense and keyword search results."""
    store = PgVectorStore(db_session)

    chunk_home_1 = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Home policy coverage for fire and theft property loss.",
        source_document="home_policy_v1.pdf",
        section="SECTION I — PROPERTY",
        page=1,
        policy_id="POL-HOME-1",
        version="1.0",
        effective_date=date(2026, 1, 1),
        chunk_type="narrative",
        policy_type="home",
    )
    chunk_auto = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Auto policy coverage for vehicle collision and road damage.",
        source_document="auto_policy_v1.pdf",
        section="SECTION II — COLLISION",
        page=2,
        policy_id="POL-AUTO-1",
        version="1.0",
        effective_date=date(2026, 2, 1),
        chunk_type="narrative",
        policy_type="auto",
    )
    chunk_home_old = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Older home policy water damage and storm protection terms.",
        source_document="home_policy_v0.pdf",
        section="SECTION I — WATER DAMAGE",
        page=3,
        policy_id="POL-HOME-0",
        version="0.9",
        effective_date=date(2024, 5, 10),
        chunk_type="narrative",
        policy_type="home",
    )

    embed_home_1 = [0.1] * 768
    embed_auto = [0.9] * 768
    embed_home_old = [0.15] * 768

    await store.upsert(chunk_home_1, embed_home_1)
    await store.upsert(chunk_auto, embed_auto)
    await store.upsert(chunk_home_old, embed_home_old)

    # 1. Filter search by policy_type="home"
    results_home = await store.search(
        query_embedding=[0.1] * 768,
        filters={"policy_type": "home"},
        top_k=10,
    )
    assert len(results_home) == 2
    assert all(c.policy_type == "home" for c in results_home)
    assert not any(c.policy_type == "auto" for c in results_home)

    # 2. Filter search by effective_date_before
    results_old = await store.search(
        query_embedding=[0.1] * 768,
        filters={"effective_date_before": date(2025, 1, 1)},
        top_k=10,
    )
    assert len(results_old) == 1
    assert results_old[0].policy_id == "POL-HOME-0"

    # 3. Keyword search for "vehicle"
    results_kw = await store.keyword_search(
        query_text="vehicle",
        filters={"policy_type": "auto"},
        top_k=5,
    )
    assert len(results_kw) == 1
    assert results_kw[0].policy_id == "POL-AUTO-1"


@pytest.mark.asyncio
async def test_upsert_idempotency(db_session: AsyncSession) -> None:
    """Verify that upserting the exact same chunk twice inserts only one record."""
    store = PgVectorStore(db_session)

    chunk = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Unique idempotency test chunk content for policy policy-999.",
        source_document="idempotency_doc.pdf",
        section="SECTION A",
        page=1,
        policy_id="POL-IDEM-1",
        version="1.0",
        effective_date=date(2026, 1, 1),
        chunk_type="narrative",
        policy_type="home",
    )
    embedding = [0.2] * 768

    await store.upsert(chunk, embedding)
    await store.upsert(chunk, embedding)

    stmt = select(ChunkModel).where(ChunkModel.policy_id == "POL-IDEM-1")
    res = await db_session.execute(stmt)
    rows = res.scalars().all()
    assert len(rows) == 1
