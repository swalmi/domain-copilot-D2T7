from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    """Abstract interface defining contracts for LLM and embedding operations."""

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Generate a complete text response from the language model."""

    @abstractmethod
    async def stream(
        self, prompt: str, system: str | None = None
    ) -> AsyncIterator[str]:
        """Stream chunks of text responses from the language model."""

    @abstractmethod
    async def call_tool(
        self, prompt: str, tools: list[dict], system: str | None = None
    ) -> dict:
        """Execute a tool call using the language model."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate vector embeddings for a given text input."""
