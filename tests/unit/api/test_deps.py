import pytest
from src.api.deps import (
    get_ask_question_use_case,
    get_claim_repository,
    get_ollama_provider,
    get_openrouter_provider,
    get_provider_router,
    get_run_adjudication_use_case,
)
from src.application.use_cases.ask_question import AskQuestionUseCase
from src.application.use_cases.run_adjudication import RunAdjudicationWorkflowUseCase
from src.domain.interfaces.claim_repository import ClaimRepository
from src.infrastructure.config import Settings, get_settings
from src.infrastructure.llm.ollama_provider import OllamaProvider
from src.infrastructure.llm.openrouter_provider import OpenRouterProvider
from src.infrastructure.llm.provider_router import ProviderRouter


def test_settings_wildcard_cors_rejected() -> None:
    """Ensure that configuring wildcard CORS origins raises a validation error."""
    with pytest.raises(ValueError, match="strictly prohibited"):
        Settings(allow_origins=["*"])


def test_settings_string_cors_origins() -> None:
    """Ensure comma-separated CORS origin strings are parsed into a list."""
    settings = Settings(allow_origins="http://example.com, http://test.com")
    assert settings.allow_origins == ["http://example.com", "http://test.com"]


def test_db_url_async_fix() -> None:
    """Ensure postgresql:// database URLs are updated to use postgresql+asyncpg://."""
    settings = Settings(database_url="postgresql://user:pass@localhost:5432/db")
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_deps_llm_providers_wiring() -> None:
    """Verify dependency injection functions instantiate expected provider objects."""
    ollama = get_ollama_provider()
    assert isinstance(ollama, OllamaProvider)

    openrouter = get_openrouter_provider()
    assert isinstance(openrouter, OpenRouterProvider)

    router = get_provider_router(ollama=ollama, openrouter=openrouter)
    assert isinstance(router, ProviderRouter)
    assert router.primary == ollama
    assert router.fallback == openrouter


def test_deps_claim_repo_wiring() -> None:
    """Verify claim repository dependency returns a ClaimRepository instance."""
    repo = get_claim_repository()
    assert isinstance(repo, ClaimRepository)


def test_deps_use_cases_wiring() -> None:
    """Verify use case dependency functions build valid use case instances."""
    ollama = get_ollama_provider()
    openrouter = get_openrouter_provider()
    router = get_provider_router(ollama=ollama, openrouter=openrouter)
    claim_repo = get_claim_repository()

    mock_vector_store = object()

    ask_case = get_ask_question_use_case(
        llm_provider=router, vector_store=mock_vector_store
    )
    assert isinstance(ask_case, AskQuestionUseCase)

    adjudication_case = get_run_adjudication_use_case(
        llm_provider=router, vector_store=mock_vector_store, claim_repo=claim_repo
    )
    assert isinstance(adjudication_case, RunAdjudicationWorkflowUseCase)
