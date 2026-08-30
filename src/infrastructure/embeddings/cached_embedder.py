import hashlib

from src.domain.interfaces.llm_provider import LLMProvider


class CachedEmbedder:
    """Embedder wrapper that caches vector embeddings by text SHA-256 hash."""

    def __init__(
        self,
        provider: LLMProvider,
        cache: dict[str, list[float]] | None = None,
    ) -> None:
        """Initialize CachedEmbedder with an LLMProvider instance and optional in-memory cache dictionary."""
        self.provider = provider
        self.cache: dict[str, list[float]] = cache if cache is not None else {}

    async def embed_with_cache(self, text: str) -> list[float]:
        """Return cached embedding if available; otherwise compute, cache, and return the vector embedding."""
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if text_hash in self.cache:
            return self.cache[text_hash]

        embedding = await self.provider.embed(text)
        self.cache[text_hash] = embedding
        return embedding
