from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.llm.openrouter_provider import OpenRouterProvider


@pytest.fixture
def mock_chat_openai():
    """Fixture providing a mocked ChatOpenAI instance."""
    with patch(
        "src.infrastructure.llm.openrouter_provider.ChatOpenAI"
    ) as mock_chat_cls:
        mock_llm_instance = MagicMock()
        mock_llm_instance.ainvoke = AsyncMock()
        mock_llm_instance.astream = MagicMock()
        mock_llm_instance.bind_tools = MagicMock()
        mock_chat_cls.return_value = mock_llm_instance
        yield mock_chat_cls, mock_llm_instance


def test_openrouter_provider_model_selection(mock_chat_openai) -> None:
    """Verify that OpenRouterProvider resolves model selection keys correctly."""
    mock_chat_cls, _ = mock_chat_openai

    provider_nvidia = OpenRouterProvider(api_key="fake-key", model_name="nvidia")
    assert provider_nvidia.model_id == "nvidia/nemotron-3-30b-a3b:free"
    assert isinstance(provider_nvidia, LLMProvider)

    provider_openai = OpenRouterProvider(api_key="fake-key", model_name="openai")
    assert provider_openai.model_id == "openai/gpt-4o-mini:free"

    provider_liquid = OpenRouterProvider(api_key="fake-key", model_name="liquid")
    assert provider_liquid.model_id == "liquid/lfm-2.5-2.6b:free"


@pytest.mark.asyncio
async def test_openrouter_complete(mock_chat_openai) -> None:
    """Verify that complete() returns a plain string from ChatOpenAI."""
    _, mock_llm = mock_chat_openai
    mock_llm.ainvoke.return_value = AIMessage(content="OpenRouter response")

    provider = OpenRouterProvider(api_key="fake-key", model_name="nvidia")
    result = await provider.complete("Test prompt")

    assert isinstance(result, str)
    assert result == "OpenRouter response"


@pytest.mark.asyncio
async def test_openrouter_stream(mock_chat_openai) -> None:
    """Verify that stream() yields string chunks from ChatOpenAI."""
    _, mock_llm = mock_chat_openai

    async def async_generator(*args, **kwargs):
        yield AIMessage(content="Chunk 1 ")
        yield AIMessage(content="Chunk 2")

    mock_llm.astream.side_effect = async_generator

    provider = OpenRouterProvider(api_key="fake-key")
    chunks = [chunk async for chunk in provider.stream("Prompt")]

    assert chunks == ["Chunk 1 ", "Chunk 2"]


@pytest.mark.asyncio
async def test_openrouter_call_tool(mock_chat_openai) -> None:
    """Verify that call_tool() parses tool calls into a plain dictionary."""
    _, mock_llm = mock_chat_openai
    bound_llm_mock = MagicMock()
    bound_llm_mock.ainvoke = AsyncMock(
        return_value=AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "calc_payout",
                    "args": {"amount": 500},
                    "id": "call_456",
                }
            ],
        )
    )
    mock_llm.bind_tools.return_value = bound_llm_mock

    provider = OpenRouterProvider(api_key="fake-key")
    tools = [{"name": "calc_payout"}]
    result = await provider.call_tool("Calculate", tools=tools)

    assert result == {"name": "calc_payout", "args": {"amount": 500}}


@pytest.mark.asyncio
async def test_openrouter_embed_raises_not_implemented(mock_chat_openai) -> None:
    """Verify that embed() raises NotImplementedError directing callers to OllamaProvider."""
    provider = OpenRouterProvider(api_key="fake-key")
    with pytest.raises(NotImplementedError) as exc_info:
        await provider.embed("sample text")

    assert "OllamaProvider" in str(exc_info.value)
