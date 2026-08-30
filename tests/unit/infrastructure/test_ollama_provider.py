from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.llm.ollama_provider import OllamaProvider


@pytest.fixture
def mock_ollama_components():
    """Fixture providing mocked ChatOllama and OllamaEmbeddings instances."""
    with (
        patch("src.infrastructure.llm.ollama_provider.ChatOllama") as mock_chat_cls,
        patch(
            "src.infrastructure.llm.ollama_provider.OllamaEmbeddings"
        ) as mock_embed_cls,
    ):
        mock_llm_instance = MagicMock()
        mock_llm_instance.ainvoke = AsyncMock()
        mock_llm_instance.astream = MagicMock()
        mock_llm_instance.bind_tools = MagicMock()
        mock_chat_cls.return_value = mock_llm_instance

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.aembed_query = AsyncMock()
        mock_embed_cls.return_value = mock_embeddings_instance

        yield mock_llm_instance, mock_embeddings_instance


def test_ollama_provider_implements_interface(mock_ollama_components) -> None:
    """Verify that OllamaProvider inherits from LLMProvider and sets defaults."""
    provider = OllamaProvider()
    assert isinstance(provider, LLMProvider)
    assert provider.base_url == "http://ollama:11434"
    assert provider.chat_model == "llama3.2:3b"
    assert provider.embedding_model == "nomic-embed-text"


@pytest.mark.asyncio
async def test_complete_returns_plain_str(mock_ollama_components) -> None:
    """Verify that complete() invokes ChatOllama and returns a plain string."""
    mock_llm, _ = mock_ollama_components
    mock_llm.ainvoke.return_value = AIMessage(content="Generated response text")

    provider = OllamaProvider()
    result = await provider.complete("Hello", system="Be concise")

    assert isinstance(result, str)
    assert result == "Generated response text"
    mock_llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_stream_yields_str_chunks(mock_ollama_components) -> None:
    """Verify that stream() yields plain string chunks asynchronously."""
    mock_llm, _ = mock_ollama_components

    async def async_generator(*args, **kwargs):
        yield AIMessage(content="Hello ")
        yield AIMessage(content="world!")

    mock_llm.astream.side_effect = async_generator

    provider = OllamaProvider()
    chunks = [chunk async for chunk in provider.stream("Hello")]

    assert chunks == ["Hello ", "world!"]
    assert all(isinstance(c, str) for c in chunks)


@pytest.mark.asyncio
async def test_call_tool_returns_dict(mock_ollama_components) -> None:
    """Verify that call_tool() parses tool calls into a plain dictionary."""
    mock_llm, _ = mock_ollama_components
    bound_llm_mock = MagicMock()
    bound_llm_mock.ainvoke = AsyncMock(
        return_value=AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_policy",
                    "args": {"query": "deductible"},
                    "id": "call_123",
                }
            ],
        )
    )
    mock_llm.bind_tools.return_value = bound_llm_mock

    provider = OllamaProvider()
    tools = [{"name": "search_policy", "description": "Search"}]
    result = await provider.call_tool("Find deductible", tools=tools)

    assert isinstance(result, dict)
    assert result == {"name": "search_policy", "args": {"query": "deductible"}}


@pytest.mark.asyncio
async def test_embed_returns_float_list(mock_ollama_components) -> None:
    """Verify that embed() returns a list of float vector embeddings."""
    _, mock_embeddings = mock_ollama_components
    mock_embeddings.aembed_query.return_value = [0.1, 0.2, 0.3]

    provider = OllamaProvider()
    embedding = await provider.embed("sample text")

    assert isinstance(embedding, list)
    assert embedding == [0.1, 0.2, 0.3]
