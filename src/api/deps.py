from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.application.use_cases.ask_question import AskQuestionUseCase
from src.application.use_cases.run_adjudication import RunAdjudicationWorkflowUseCase
from src.domain.interfaces.claim_repository import ClaimRepository
from src.domain.interfaces.vector_store import VectorStore
from src.infrastructure.config import get_settings
from src.infrastructure.db.repositories.claim_repository import InMemoryClaimRepository
from src.infrastructure.llm.ollama_provider import OllamaProvider
from src.infrastructure.llm.openrouter_provider import OpenRouterProvider
from src.infrastructure.llm.provider_router import ProviderRouter
from src.infrastructure.vectorstore.pgvector_store import PgVectorStore

_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_claim_repository: ClaimRepository = InMemoryClaimRepository()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retrieve or initialize the async SQLAlchemy session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        _async_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an active asynchronous database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


def get_ollama_provider() -> OllamaProvider:
    """Instantiate the primary Ollama LLM provider using configuration settings."""
    settings = get_settings()
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        chat_model=settings.ollama_chat_model,
        embedding_model=settings.ollama_embedding_model,
    )


def get_openrouter_provider() -> OpenRouterProvider:
    """Instantiate the fallback OpenRouter LLM provider using configuration settings."""
    settings = get_settings()
    return OpenRouterProvider(
        api_key=settings.openrouter_api_key,
        model_name=settings.openrouter_model_name,
        base_url=settings.openrouter_base_url,
    )


def get_provider_router(
    ollama: OllamaProvider = Depends(get_ollama_provider),
    openrouter: OpenRouterProvider = Depends(get_openrouter_provider),
) -> ProviderRouter:
    """Wire Ollama as primary provider and OpenRouter as fallback in a ProviderRouter instance."""
    return ProviderRouter(primary=ollama, fallback=openrouter)


def get_vector_store(
    session: AsyncSession = Depends(get_db_session),
) -> VectorStore:
    """Instantiate PostgreSQL pgvector vector store bound to active database session."""
    return PgVectorStore(session=session)


def get_claim_repository() -> ClaimRepository:
    """Provide single-instance claim repository for claim entity persistence."""
    return _claim_repository


def get_ask_question_use_case(
    llm_provider: ProviderRouter = Depends(get_provider_router),
    vector_store: VectorStore = Depends(get_vector_store),
) -> AskQuestionUseCase:
    """Construct AskQuestionUseCase instance wired with ProviderRouter and VectorStore."""
    settings = get_settings()
    return AskQuestionUseCase(
        llm_provider=llm_provider,
        vector_store=vector_store,
        min_confidence_score=settings.min_confidence_score,
    )


def get_run_adjudication_use_case(
    llm_provider: ProviderRouter = Depends(get_provider_router),
    vector_store: VectorStore = Depends(get_vector_store),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> RunAdjudicationWorkflowUseCase:
    """Construct RunAdjudicationWorkflowUseCase instance with ProviderRouter, VectorStore, and ClaimRepository."""
    return RunAdjudicationWorkflowUseCase(
        llm_provider=llm_provider,
        vector_store=vector_store,
        claim_repo=claim_repo,
    )
