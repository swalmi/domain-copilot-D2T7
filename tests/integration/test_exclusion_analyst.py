from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.agents.exclusion_analyst import ExclusionAnalyst
from src.application.contracts.coverage_match_result import CoverageMatchResult
from src.application.tools.calculate_limits import calculate_limits_and_deductibles
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
        return_value={
            "name": "search_exclusions",
            "args": {
                "deductible": 500.0,
                "policy_limit": 10000.0,
                "has_exclusion": True,
            },
        }
    )
    return provider


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exclusion_analyst_deterministic_math(
    db_session: AsyncSession, mock_llm_provider: AsyncMock
) -> None:
    """Verify calculated_payout matches independent calculate_limits_and_deductibles output."""
    store = PgVectorStore(db_session)
    analyst = ExclusionAnalyst(llm_provider=mock_llm_provider)

    policy_id = "POL-EXCL-TEST"
    chunk = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Wear and tear exclusion clause.",
        source_document="policy.pdf",
        section="EXCLUSIONS",
        page=1,
        policy_id=policy_id,
        version="1.0",
        effective_date=date(2026, 1, 1),
        chunk_type="narrative",
        policy_type="home",
    )
    await store.upsert(chunk, [0.1] * 768)

    claim = Claim(
        id=uuid.uuid4(),
        policy_number=policy_id,
        date_of_loss=date(2026, 1, 1),
        incident_description="Water damage wear and tear",
        claim_amount_requested=Decimal("3500.00"),
        status="submitted",
    )

    coverage_match = CoverageMatchResult(
        policy_id=policy_id,
        version_effective_date=date(2026, 1, 1),
        applicable_coverage_sections=[chunk],
        confidence="matched",
    )

    result = await analyst.run(claim=claim, coverage_match=coverage_match, vector_store=store)

    expected_calc = calculate_limits_and_deductibles(
        claim_amount=Decimal("3500.00"),
        deductible=Decimal("500.00"),
        policy_limit=Decimal("10000.00"),
    )

    assert result.calculated_payout == expected_calc["payout"]
    assert result.deductible_applied == Decimal("500.00")
    assert result.policy_limit == Decimal("10000.00")
    assert "applicable_exclusion_found" in result.anomaly_flags
