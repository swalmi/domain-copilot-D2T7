from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.llm.provider_router import ProviderRouter


@pytest.fixture
def mock_providers():
    """Fixture providing primary and fallback mock LLMProvider instances."""
    primary = MagicMock(spec=LLMProvider)
    primary.complete = AsyncMock()
    primary.stream = MagicMock()
    primary.call_tool = AsyncMock()
    primary.embed = AsyncMock()

    fallback = MagicMock(spec=LLMProvider)
    fallback.complete = AsyncMock()
    fallback.stream = MagicMock()
    fallback.call_tool = AsyncMock()
    fallback.embed = AsyncMock()

    return primary, fallback


@pytest.mark.asyncio
async def test_complete_primary_success(mock_providers) -> None:
    """Verify that complete() returns primary provider result when primary succeeds."""
    primary, fallback = mock_providers
    primary.complete.return_value = "Primary success"

    router = ProviderRouter(primary=primary, fallback=fallback)
    result = await router.complete("Hello")

    assert result == "Primary success"
    primary.complete.assert_called_once_with(prompt="Hello", system=None)
    fallback.complete.assert_not_called()


@pytest.mark.asyncio
async def test_complete_primary_failure_fallback_success(mock_providers) -> None:
    """Verify that complete() triggers fallback when primary provider raises an exception."""
    primary, fallback = mock_providers
    primary.complete.side_effect = RuntimeError("Primary connection error")
    fallback.complete.return_value = "Fallback success"

    router = ProviderRouter(primary=primary, fallback=fallback)
    with patch("src.infrastructure.llm.provider_router.logger.warning") as mock_log:
        result = await router.complete("Hello", system="Sys prompt")

    assert result == "Fallback success"
    fallback.complete.assert_called_once_with(prompt="Hello", system="Sys prompt")
    mock_log.assert_called_once()
    _, kwargs = mock_log.call_args
    assert kwargs.get("extra", {}).get("step_type") == "fallback_triggered"


@pytest.mark.asyncio
async def test_stream_fallback(mock_providers) -> None:
    """Verify that stream() falls back to secondary provider if primary fails during stream."""
    primary, fallback = mock_providers

    async def primary_failing_stream(*args, **kwargs):
        raise RuntimeError("Primary stream error")
        yield "Never reached"  # pragma: no cover

    async def fallback_stream(*args, **kwargs):
        yield "Fallback "
        yield "chunk"

    primary.stream.side_effect = primary_failing_stream
    fallback.stream.side_effect = fallback_stream

    router = ProviderRouter(primary=primary, fallback=fallback)
    chunks = [chunk async for chunk in router.stream("Hello")]

    assert chunks == ["Fallback ", "chunk"]


@pytest.mark.asyncio
async def test_call_tool_fallback(mock_providers) -> None:
    """Verify that call_tool() falls back to secondary provider if primary fails."""
    primary, fallback = mock_providers
    primary.call_tool.side_effect = RuntimeError("Tool call error")
    fallback.call_tool.return_value = {
        "name": "get_weather",
        "args": {"city": "Paris"},
    }

    router = ProviderRouter(primary=primary, fallback=fallback)
    tools = [{"name": "get_weather"}]
    result = await router.call_tool("Weather in Paris", tools=tools)

    assert result == {"name": "get_weather", "args": {"city": "Paris"}}
    fallback.call_tool.assert_called_once_with(
        prompt="Weather in Paris", tools=tools, system=None
    )


@pytest.mark.asyncio
async def test_embed_never_uses_fallback(mock_providers) -> None:
    """Verify that embed() calls primary provider only and never falls back to secondary provider."""
    primary, fallback = mock_providers
    primary.embed.side_effect = RuntimeError("Embedding service unavailable")

    router = ProviderRouter(primary=primary, fallback=fallback)
    with pytest.raises(RuntimeError):
        await router.embed("Text to embed")

    primary.embed.assert_called_once_with("Text to embed")
    fallback.embed.assert_not_called()
