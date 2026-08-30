import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.retrieval.context_expander import expand_to_parent_sections
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expand_to_parent_sections(db_session: AsyncSession) -> None:
    """Verify small-to-big context expansion concatenates all parent section chunks into context_for_llm."""
    store = PgVectorStore(db_session)

    policy_id = "POL-EXPAND-TEST"
    version = "1.0"
    section = "SECTION I - PROPERTY COVERAGES"

    chunk_part1 = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Part 1: We cover dwelling structure on the residence premises.",
        source_document="ho3_policy.pdf",
        section=section,
        page=1,
        policy_id=policy_id,
        version=version,
        effective_date=date(2026, 1, 1),
        chunk_type="narrative",
        policy_type="home",
    )

    chunk_part2 = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Part 2: Other structures on the residence premises set apart from dwelling.",
        source_document="ho3_policy.pdf",
        section=section,
        page=2,
        policy_id=policy_id,
        version=version,
        effective_date=date(2026, 1, 1),
        chunk_type="narrative",
        policy_type="home",
    )

    embedding = [0.1] * 768
    await store.upsert(chunk_part1, embedding)
    await store.upsert(chunk_part2, embedding)

    # Expand chunk_part1
    expanded = await expand_to_parent_sections([chunk_part1], store)

    assert len(expanded) == 1
    result_item = expanded[0]

    # Citation must remain original small chunk
    assert result_item["cited_chunk"] == chunk_part1
    assert result_item["cited_chunk"].text == chunk_part1.text

    # LLM-facing context must be expanded, contain chunk_part1.text, and be longer
    context_text = result_item["context_for_llm"]
    assert chunk_part1.text in context_text
    assert chunk_part2.text in context_text
    assert len(context_text) > len(chunk_part1.text)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expand_to_parent_sections_on_seeded_corpus(
    db_session: AsyncSession,
) -> None:
    """Verify context expansion against seeded corpus chunks."""
    store = PgVectorStore(db_session)

    # Perform dense search to get a real chunk from seeded database
    search_results = await store.search(
        query_embedding=[0.1] * 768, filters={}, top_k=1
    )
    if not search_results:
        pytest.skip("Database has no seeded chunks.")

    target_chunk = search_results[0]
    expanded = await expand_to_parent_sections([target_chunk], store)

    assert len(expanded) == 1
    assert expanded[0]["cited_chunk"] == target_chunk
    assert target_chunk.text in expanded[0]["context_for_llm"]
