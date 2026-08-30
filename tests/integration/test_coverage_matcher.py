from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.agents.coverage_matcher import CoverageMatcher
from src.domain.entities.claim import Claim
from src.domain.entities.policy import CitedChunk
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
def mock_llm_provider() -> AsyncMock:
    """Fixture providing a mock LLM provider for agent execution."""
    provider = AsyncMock(spec=LLMProvider)
    provider.embed = AsyncMock(return_value=[0.1] * 768)
    provider.embed_with_cache = AsyncMock(return_value=[0.1] * 768)
    provider.call_tool = AsyncMock(
        return_value={"name": "search_policies", "args": {"confidence": "matched"}}
    )
    return provider


@pytest.mark.integration
@pytest.mark.asyncio
async def test_coverage_matcher_version_matching_risk_guard(
    db_session: AsyncSession, mock_llm_provider: AsyncMock
) -> None:
    """Verify CoverageMatcher matches older policy version when claim date of loss precedes newer version."""
    store = PgVectorStore(db_session)
    matcher = CoverageMatcher(llm_provider=mock_llm_provider)

    policy_id = "ISO-CP-00-10"

    chunk_old = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Building personal property loss coverage form details under 2000 version.",
        source_document="CP0010_2000.pdf",
        section="BUILDING AND PERSONAL PROPERTY COVERAGE FORM",
        page=1,
        policy_id=policy_id,
        version="2000-10",
        effective_date=date(2000, 10, 1),
        chunk_type="narrative",
        policy_type="commercial_property",
    )

    chunk_new = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Building personal property loss coverage form details under 2012 updated version.",
        source_document="CP0010_2012.pdf",
        section="BUILDING AND PERSONAL PROPERTY COVERAGE FORM",
        page=1,
        policy_id=policy_id,
        version="2012-10",
        effective_date=date(2012, 10, 1),
        chunk_type="narrative",
        policy_type="commercial_property",
    )

    embedding = [0.1] * 768
    await store.upsert(chunk_old, embedding)
    await store.upsert(chunk_new, embedding)

    claim_old = Claim(
        id=uuid.uuid4(),
        policy_number=policy_id,
        date_of_loss=date(2005, 1, 1),
        incident_description="Building personal property loss due to fire",
        claim_amount_requested=Decimal("5000.00"),
        status="submitted",
    )

    result = await matcher.run(claim=claim_old, vector_store=store)

    assert result.confidence == "matched"
    assert result.version_effective_date <= date(2005, 1, 1)
    assert len(result.applicable_coverage_sections) > 0
    assert all(c.effective_date <= date(2005, 1, 1) for c in result.applicable_coverage_sections)
    assert not any(c.version == "2012-10" for c in result.applicable_coverage_sections)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_coverage_matcher_no_match_for_nonexistent_policy(
    db_session: AsyncSession, mock_llm_provider: AsyncMock
) -> None:
    """Verify CoverageMatcher returns no_match when policy number does not exist in corpus."""
    store = PgVectorStore(db_session)
    matcher = CoverageMatcher(llm_provider=mock_llm_provider)

    claim_nonexistent = Claim(
        id=uuid.uuid4(),
        policy_number="NON-EXISTENT-POLICY-99999",
        date_of_loss=date(2026, 1, 1),
        incident_description="Unknown incident description",
        claim_amount_requested=Decimal("1000.00"),
        status="submitted",
    )

    result = await matcher.run(claim=claim_nonexistent, vector_store=store)

    assert result.confidence == "no_match"
    assert result.applicable_coverage_sections == []
