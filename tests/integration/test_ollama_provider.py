import os

import pytest

from src.infrastructure.llm.ollama_provider import OllamaProvider

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


@pytest.fixture
def ollama_provider() -> OllamaProvider:
    """Fixture initializing OllamaProvider targeting the active Ollama instance."""
    return OllamaProvider(
        base_url=OLLAMA_BASE_URL,
        chat_model="llama3.2:3b",
        embedding_model="nomic-embed-text",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_returns_non_empty_string(
    ollama_provider: OllamaProvider,
) -> None:
    """Verify complete() returns a non-empty string for a simple prompt."""
    prompt = "Respond with a single word: hello."
    response = await ollama_provider.complete(prompt)
    assert isinstance(response, str)
    assert len(response.strip()) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_embed_returns_correct_dimension(
    ollama_provider: OllamaProvider,
) -> None:
    """Verify embed() returns a float list matching nomic-embed-text 768 dimensions."""
    text = "Insurance policy document chunk for embedding test."
    embedding = await ollama_provider.embed(text)
    assert isinstance(embedding, list)
    assert len(embedding) == 768
    assert all(isinstance(val, float) for val in embedding)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_call_tool_extracts_tool_call(ollama_provider: OllamaProvider) -> None:
    """Verify call_tool() extracts a tool call dictionary when prompt requires tool execution."""
    weather_tool = {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a specified city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The name of the city, e.g. Tokyo, London",
                    }
                },
                "required": ["city"],
            },
        },
    }

    prompt = "What is the weather in Tokyo right now? Call the get_weather tool."
    result = await ollama_provider.call_tool(prompt=prompt, tools=[weather_tool])

    assert isinstance(result, dict)
    assert result.get("name") == "get_weather"
    assert "args" in result
    assert isinstance(result["args"], dict)
