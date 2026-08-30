import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.embeddings.cached_embedder import CachedEmbedder


@pytest.fixture
def mock_provider() -> MagicMock:
    """Fixture providing a mock LLMProvider instance."""
    provider = MagicMock(spec=LLMProvider)
    provider.embed = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_cached_embedder_cache_miss(mock_provider) -> None:
    """Verify that CachedEmbedder invokes the provider's embed method on cache miss."""
    expected_embedding = [0.1, 0.2, 0.3]
    mock_provider.embed.return_value = expected_embedding

    embedder = CachedEmbedder(provider=mock_provider)
    text = "Hello, world!"
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    result = await embedder.embed_with_cache(text)

    assert result == expected_embedding
    assert text_hash in embedder.cache
    assert embedder.cache[text_hash] == expected_embedding
    mock_provider.embed.assert_called_once_with(text)


@pytest.mark.asyncio
async def test_cached_embedder_cache_hit(mock_provider) -> None:
    """Verify that CachedEmbedder uses cached embeddings without calling provider's embed method."""
    cached_embedding = [0.5, 0.6, 0.7]
    text = "Hello, world!"
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    initial_cache = {text_hash: cached_embedding}

    embedder = CachedEmbedder(provider=mock_provider, cache=initial_cache)

    result = await embedder.embed_with_cache(text)

    assert result == cached_embedding
    mock_provider.embed.assert_not_called()
