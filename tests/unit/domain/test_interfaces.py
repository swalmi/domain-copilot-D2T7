import uuid
from collections.abc import AsyncIterator
from uuid import UUID

import pytest

from src.domain.entities.claim import Claim
from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.claim_repository import ClaimRepository
from src.domain.interfaces.document_repository import DocumentRepository
from src.domain.interfaces.llm_provider import LLMProvider
from src.domain.interfaces.vector_store import VectorStore


def test_cannot_instantiate_abstract_interfaces() -> None:
    """Verify that domain interface ABCs cannot be directly instantiated."""
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]

    with pytest.raises(TypeError):
        VectorStore()  # type: ignore[abstract]

    with pytest.raises(TypeError):
        ClaimRepository()  # type: ignore[abstract]

    with pytest.raises(TypeError):
        DocumentRepository()  # type: ignore[abstract]


def test_concrete_implementations_satisfy_interfaces() -> None:
    """Verify that concrete dummy implementations can be instantiated when abstract methods are implemented."""

    class DummyLLMProvider(LLMProvider):
        """Concrete test implementation of LLMProvider."""

        async def complete(self, prompt: str, system: str | None = None) -> str:
            return "response"

        async def stream(
            self, prompt: str, system: str | None = None
        ) -> AsyncIterator[str]:
            yield "chunk"

        async def call_tool(
            self, prompt: str, tools: list[dict], system: str | None = None
        ) -> dict:
            return {}

        async def embed(self, text: str) -> list[float]:
            return [0.1, 0.2]

    class DummyVectorStore(VectorStore):
        """Concrete test implementation of VectorStore."""

        async def search(
            self, query_embedding: list[float], filters: dict, top_k: int
        ) -> list[CitedChunk]:
            return []

        async def keyword_search(
            self, query_text: str, filters: dict, top_k: int
        ) -> list[CitedChunk]:
            return []

        async def upsert(self, chunk: CitedChunk, embedding: list[float]) -> None:
            pass

        async def chunk_exists(self, content_hash: str) -> bool:
            return False

        async def get_chunks_by_section(
            self, policy_id: str, version: str, section: str
        ) -> list[CitedChunk]:
            return []

    class DummyClaimRepository(ClaimRepository):
        """Concrete test implementation of ClaimRepository."""

        async def save(self, claim: Claim) -> None:
            pass

        async def get_by_id(self, claim_id: UUID) -> Claim | None:
            return None

    class DummyDocumentRepository(DocumentRepository):
        """Concrete test implementation of DocumentRepository."""

        async def create_document(
            self, filename: str, content_hash: str, status: str
        ) -> UUID:
            return uuid.uuid4()

        async def save_document_status(self, document_id: UUID, status: str) -> None:
            pass

        async def get_document_by_hash(self, content_hash: str) -> UUID | None:
            return None

    assert isinstance(DummyLLMProvider(), LLMProvider)
    assert isinstance(DummyVectorStore(), VectorStore)
    assert isinstance(DummyClaimRepository(), ClaimRepository)
    assert isinstance(DummyDocumentRepository(), DocumentRepository)
