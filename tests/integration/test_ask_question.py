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


async def _corpus_embedding(db_session: AsyncSession) -> list[float]:
    """Return a real chunk embedding so the refusal gate sees a plausible query.

    A constant vector such as ``[0.1] * 768`` is far from every real embedding,
    so the cosine-distance gate correctly treats it as an out-of-corpus query and
    refuses before the LLM is reached. Tests that want an *answered* response
    must therefore query with a vector that actually resembles the corpus.
    """
    from sqlalchemy import select

    from src.infrastructure.db.models import ChunkModel

    stmt = select(ChunkModel.embedding).limit(1)
    embedding = (await db_session.execute(stmt)).scalar_one()
    assert embedding is not None, "corpus is empty; run the ingestion first"
    return list(embedding)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ask_question_answered_by_corpus(
    db_session: AsyncSession, mock_llm_provider: AsyncMock
) -> None:
    """Verify AskQuestionUseCase answers valid corpus query with citations and refused=False."""
    store = PgVectorStore(db_session)
    # hybrid_search prefers embed_with_cache, so both must carry a real vector.
    corpus_embedding = await _corpus_embedding(db_session)
    mock_llm_provider.embed.return_value = corpus_embedding
    mock_llm_provider.embed_with_cache.return_value = corpus_embedding
    use_case = AskQuestionUseCase(
        llm_provider=mock_llm_provider,
        vector_store=store,
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

    # Point the query directly away from the corpus. RRF cannot catch this: it is
    # rank-based, so a nonsense query still ranks *some* chunk first. Only the
    # absolute cosine distance reveals that nothing relevant was found.
    away = await _corpus_embedding(db_session)
    negated = [-float(v) for v in away]
    mock_llm_provider.embed.return_value = negated
    mock_llm_provider.embed_with_cache.return_value = negated
    use_case = AskQuestionUseCase(
        llm_provider=mock_llm_provider,
        vector_store=store,
    )

    out_of_corpus_query = "Quantum electrodynamics Feynman diagram loop expansion in 11D space"
    result = await use_case.execute(query=out_of_corpus_query)

    assert result["refused"] is True
    assert result["answer"] == "Not enough information in the corpus to answer this question."
    assert result["citations"] == []
    mock_llm_provider.complete.assert_not_called()
