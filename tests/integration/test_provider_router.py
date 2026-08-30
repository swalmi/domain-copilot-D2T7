import os
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.infrastructure.llm.ollama_provider import OllamaProvider
from src.infrastructure.llm.openrouter_provider import OpenRouterProvider
from src.infrastructure.llm.provider_router import ProviderRouter


@pytest.mark.integration
@pytest.mark.asyncio
async def test_primary_provider_used_when_working() -> None:
    """Verify that a working primary provider is used directly and fallback is never called."""
    primary = AsyncMock()
    fallback = AsyncMock()
    primary.complete.return_value = "Primary response"

    router = ProviderRouter(primary=primary, fallback=fallback)
    result = await router.complete("Hello")

    assert result == "Primary response"
    primary.complete.assert_called_once_with(prompt="Hello", system=None)
    fallback.complete.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fallback_called_when_primary_fails() -> None:
    """Verify that fallback provider is called and its result returned when primary fails."""
    primary = AsyncMock()
    fallback = AsyncMock()
    primary.complete.side_effect = RuntimeError("Primary error")
    fallback.complete.return_value = "Fallback response"

    router = ProviderRouter(primary=primary, fallback=fallback)
    result = await router.complete("Hello")

    assert result == "Fallback response"
    primary.complete.assert_called_once_with(prompt="Hello", system=None)
    fallback.complete.assert_called_once_with(prompt="Hello", system=None)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simulated_real_fallback_from_broken_ollama_to_openrouter() -> None:
    """Simulate real fallback from an unreachable Ollama provider to OpenRouterProvider."""
    broken_ollama = OllamaProvider(base_url="http://localhost:59999")
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    openrouter = OpenRouterProvider(api_key=api_key or "fake-key", model_name="nvidia")

    router = ProviderRouter(primary=broken_ollama, fallback=openrouter)

    if not api_key or api_key == "your-openrouter-api-key-here":
        with patch(
            "src.infrastructure.llm.openrouter_provider.ChatOpenAI.ainvoke",
            new_callable=AsyncMock,
            return_value=AIMessage(content="Fallback response from OpenRouter"),
        ):
            response = await router.complete("Hello")
    else:
        response = await router.complete("Hello")

    assert isinstance(response, str)
    assert len(response.strip()) > 0
