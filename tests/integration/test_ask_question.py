from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.use_cases.ask_question import AskQuestionUseCase
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
    """Fixture providing a mock LLM provider spying on complete and embed calls."""
    provider = AsyncMock(spec=LLMProvider)
    provider.embed = AsyncMock(return_value=[0.1] * 768)
    provider.embed_with_cache = AsyncMock(return_value=[0.1] * 768)
    provider.complete = AsyncMock(return_value="This is a generated policy answer.")
    return provider


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ask_question_answered_by_corpus(
    db_session: AsyncSession, mock_llm_provider: AsyncMock
) -> None:
    """Verify AskQuestionUseCase answers valid corpus query with citations and refused=False."""
    store = PgVectorStore(db_session)
    use_case = AskQuestionUseCase(
        llm_provider=mock_llm_provider,
        vector_store=store,
        min_confidence_score=0.01,
    )

    result = await use_case.execute(query="Building and Personal Property")

    assert result["refused"] is False
    assert result["answer"] == "This is a generated policy answer."
    assert len(result["citations"]) > 0
    first_citation = result["citations"][0]
    assert "text_snippet" in first_citation
    assert "source" in first_citation
    assert "section" in first_citation
    assert "page" in first_citation
    mock_llm_provider.complete.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ask_question_out_of_corpus_pre_llm_refusal(
    db_session: AsyncSession, mock_llm_provider: AsyncMock
) -> None:
    """Verify AskQuestionUseCase refuses out-of-corpus query pre-LLM without calling complete()."""
    store = PgVectorStore(db_session)

    # Instantiate use case with high confidence threshold or empty filter matching nothing
    use_case = AskQuestionUseCase(
        llm_provider=mock_llm_provider,
        vector_store=store,
        min_confidence_score=0.05,  # Higher than single-list max RRF score 1/61 (~0.01639)
    )

    out_of_corpus_query = "Quantum electrodynamics Feynman diagram loop expansion in 11D space"
    result = await use_case.execute(query=out_of_corpus_query)

    assert result["refused"] is True
    assert result["answer"] == "Not enough information in the corpus to answer this question."
    assert result["citations"] == []
    mock_llm_provider.complete.assert_not_called()
