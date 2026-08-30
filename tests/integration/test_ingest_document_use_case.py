from datetime import date
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.use_cases.ingest_document import IngestDocumentUseCase
from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.db.models import ChunkModel
from src.infrastructure.db.repositories.document_repository import (
    SqlalchemyDocumentRepository,
)
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


@pytest.fixture
def mock_llm_provider() -> LLMProvider:
    """Fixture providing a mock LLMProvider for fast embedding generation."""
    provider = AsyncMock(spec=LLMProvider)
    provider.embed.return_value = [0.1] * 768
    return provider


@pytest.mark.asyncio
async def test_ingest_document_use_case_success_and_idempotency(
    db_session: AsyncSession, mock_llm_provider: LLMProvider
) -> None:
    """Verify end-to-end ingestion success, Postgres persistence, and already_ingested idempotency."""
    vector_store = PgVectorStore(db_session)
    document_repo = SqlalchemyDocumentRepository(db_session)

    use_case = IngestDocumentUseCase(
        llm_provider=mock_llm_provider,
        vector_store=vector_store,
        document_repo=document_repo,
    )

    pdf_path = "data/auto/pp-00-01-09-18.pdf"

    result1 = await use_case.execute(
        file_path=pdf_path,
        policy_id="ISO-PP-00-01",
        policy_type="auto",
        version="2018-09",
        effective_date=date(2018, 9, 1),
    )

    assert result1["status"] == "success"
    assert result1["chunks_count"] > 0

    stmt = select(ChunkModel).where(ChunkModel.policy_id == "ISO-PP-00-01")
    res = await db_session.execute(stmt)
    chunks = res.scalars().all()
    assert len(chunks) == result1["chunks_count"]
    for c in chunks:
        assert c.policy_id == "ISO-PP-00-01"
        assert c.policy_type == "auto"
        assert c.version == "2018-09"
        assert c.effective_date == date(2018, 9, 1)

    initial_chunk_count = len(chunks)

    result2 = await use_case.execute(
        file_path=pdf_path,
        policy_id="ISO-PP-00-01",
        policy_type="auto",
        version="2018-09",
        effective_date=date(2018, 9, 1),
    )

    assert result2["status"] == "already_ingested"

    res_after = await db_session.execute(stmt)
    chunks_after = res_after.scalars().all()
    assert len(chunks_after) == initial_chunk_count


@pytest.mark.asyncio
async def test_ingest_document_use_case_docx(
    db_session: AsyncSession, mock_llm_provider: LLMProvider
) -> None:
    """Verify ingestion of a DOCX policy document."""
    vector_store = PgVectorStore(db_session)
    document_repo = SqlalchemyDocumentRepository(db_session)

    use_case = IngestDocumentUseCase(
        llm_provider=mock_llm_provider,
        vector_store=vector_store,
        document_repo=document_repo,
    )

    docx_path = "data/regulatory/coverage-policies-template-doc.docx"

    result = await use_case.execute(
        file_path=docx_path,
        policy_id="ILDOI-COV-TEMPLATE",
        policy_type="home",
        version="current",
        effective_date=date(2024, 1, 1),
    )

    assert result["status"] == "success"
    assert result["chunks_count"] > 0


@pytest.mark.asyncio
async def test_ingest_document_use_case_handles_corrupt_file(
    db_session: AsyncSession, mock_llm_provider: LLMProvider
) -> None:
    """Verify that pointing to a non-existent or invalid file returns status='failed' without raising."""
    vector_store = PgVectorStore(db_session)
    document_repo = SqlalchemyDocumentRepository(db_session)

    use_case = IngestDocumentUseCase(
        llm_provider=mock_llm_provider,
        vector_store=vector_store,
        document_repo=document_repo,
    )

    invalid_path = "non_existent_file.pdf"

    result = await use_case.execute(
        file_path=invalid_path,
        policy_id="POL-BAD",
        policy_type="home",
        version="1.0",
        effective_date=date(2026, 1, 1),
    )

    assert result["status"] == "failed"
    assert "error" in result
