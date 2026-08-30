import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.agents.coverage_matcher import CoverageMatcher
from src.application.use_cases.run_adjudication import (
    RunAdjudicationWorkflowUseCase,
)
from src.domain.entities.claim import Claim
from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.claim_repository import ClaimRepository
from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.vectorstore.pgvector_store import PgVectorStore


class InMemoryClaimRepository(ClaimRepository):
    """In-memory test implementation of ClaimRepository."""

    def __init__(self) -> None:
        self.claims: dict[uuid.UUID, Claim] = {}

    async def save(self, claim: Claim) -> None:
        self.claims[claim.id] = claim

    async def get_by_id(self, claim_id: uuid.UUID) -> Claim | None:
        return self.claims.get(claim_id)


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
    """Fixture providing a mock LLM provider for workflow orchestrator."""
    provider = AsyncMock(spec=LLMProvider)
    provider.embed = AsyncMock(return_value=[0.1] * 768)
    provider.embed_with_cache = AsyncMock(return_value=[0.1] * 768)
    provider.complete = AsyncMock(
        return_value="Adjudication recommendation draft text for fire damage loss."
    )
    provider.call_tool = AsyncMock(
        side_effect=lambda prompt, tools: {
            "name": tools[0]["function"]["name"],
            "args": {
                "confidence": "matched",
                "deductible": 500.0,
                "policy_limit": 10000.0,
                "has_exclusion": False,
            },
        }
    )
    return provider


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_happy_path(
    db_session: AsyncSession, mock_llm_provider: AsyncMock
) -> None:
    """Verify happy-path workflow execution generates AdjudicationDraft and updates claim status to pending_approval."""
    store = PgVectorStore(db_session)
    claim_repo = InMemoryClaimRepository()

    policy_id = "ISO-CP-00-10"
    chunk = CitedChunk(
        chunk_id=uuid.uuid4(),
        text="Building property loss coverage section.",
        source_document="cp0010.pdf",
        section="COVERAGE FORM",
        page=1,
        policy_id=policy_id,
        version="2012-10",
        effective_date=date(2012, 10, 1),
        chunk_type="narrative",
        policy_type="commercial_property",
    )
    await store.upsert(chunk, [0.1] * 768)

    claim_id = uuid.uuid4()
    claim = Claim(
        id=claim_id,
        policy_number=policy_id,
        date_of_loss=date(2015, 1, 1),
        incident_description="Building personal property loss due to fire",
        claim_amount_requested=Decimal("5000.00"),
        status="submitted",
    )
    await claim_repo.save(claim)

    use_case = RunAdjudicationWorkflowUseCase(
        llm_provider=mock_llm_provider,
        vector_store=store,
        claim_repo=claim_repo,
    )

    draft = await use_case.execute(claim=claim, correlation_id=uuid.uuid4())

    assert draft.calculated_payout == Decimal("4500.00")
    assert draft.recommendation in ["approve", "partial"]

    saved_claim = await claim_repo.get_by_id(claim_id)
    assert saved_claim is not None
    assert saved_claim.status == "pending_approval"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_graceful_degradation_on_error(
    db_session: AsyncSession, mock_llm_provider: AsyncMock, monkeypatch
) -> None:
    """Verify orchestrator gracefully degrades to AskQuestionUseCase fallback when an agent raises an exception."""
    store = PgVectorStore(db_session)
    claim_repo = InMemoryClaimRepository()

    claim_id = uuid.uuid4()
    claim = Claim(
        id=claim_id,
        policy_number="ISO-CP-00-10",
        date_of_loss=date(2015, 1, 1),
        incident_description="Building fire loss",
        claim_amount_requested=Decimal("3000.00"),
        status="submitted",
    )
    await claim_repo.save(claim)

    # Monkeypatch CoverageMatcher.run to force failure
    async def failing_run(*args, **kwargs):
        raise RuntimeError("Simulated agent failure")

    monkeypatch.setattr(CoverageMatcher, "run", failing_run)

    use_case = RunAdjudicationWorkflowUseCase(
        llm_provider=mock_llm_provider,
        vector_store=store,
        claim_repo=claim_repo,
    )

    draft = await use_case.execute(claim=claim, correlation_id=uuid.uuid4())

    assert draft.confidence == "low"
    assert "DEGRADED FALLBACK" in draft.reasoning_text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_no_match_short_circuit(
    db_session: AsyncSession, mock_llm_provider: AsyncMock
) -> None:
    """Verify orchestrator short-circuits workflow and marks claim refused when policy coverage is no_match."""
    store = PgVectorStore(db_session)
    claim_repo = InMemoryClaimRepository()

    claim_id = uuid.uuid4()
    claim = Claim(
        id=claim_id,
        policy_number="NON-EXISTENT-POLICY",
        date_of_loss=date(2026, 1, 1),
        incident_description="Unknown incident",
        claim_amount_requested=Decimal("1000.00"),
        status="submitted",
    )
    await claim_repo.save(claim)

    use_case = RunAdjudicationWorkflowUseCase(
        llm_provider=mock_llm_provider,
        vector_store=store,
        claim_repo=claim_repo,
    )

    draft = await use_case.execute(claim=claim, correlation_id=uuid.uuid4())

    assert draft.recommendation == "deny"
    assert draft.calculated_payout == Decimal("0.00")

    saved_claim = await claim_repo.get_by_id(claim_id)
    assert saved_claim is not None
    assert saved_claim.status == "refused"
