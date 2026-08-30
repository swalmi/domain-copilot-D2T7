from abc import ABC, abstractmethod

from src.domain.entities.policy import CitedChunk


class VectorStore(ABC):
    """Abstract interface defining contracts for vector and hybrid search operations."""

    @abstractmethod
    async def search(
        self, query_embedding: list[float], filters: dict, top_k: int
    ) -> list[CitedChunk]:
        """Search for relevant policy chunks using vector similarity embeddings."""

    @abstractmethod
    async def keyword_search(
        self, query_text: str, filters: dict, top_k: int
    ) -> list[CitedChunk]:
        """Search for relevant policy chunks using text keyword matching."""

    @abstractmethod
    async def upsert(self, chunk: CitedChunk, embedding: list[float]) -> None:
        """Insert or update a policy chunk and its associated embedding in the store."""
