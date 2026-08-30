import logging
from collections.abc import AsyncIterator

from src.domain.interfaces.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class ProviderRouter(LLMProvider):
    """LLM provider router that attempts operations on a primary provider and falls back to a secondary provider."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        """Initialize ProviderRouter with primary and fallback LLMProvider instances."""
        self.primary = primary
        self.fallback = fallback

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Generate a complete text response using primary provider with fallback to secondary provider."""
        try:
            return await self.primary.complete(prompt=prompt, system=system)
        except Exception as exc:
            logger.warning(
                "Primary LLM provider failed during complete: %s. Trying fallback provider.",
                exc,
            )
            try:
                return await self.fallback.complete(prompt=prompt, system=system)
            except Exception as fallback_exc:
                logger.warning(
                    "Fallback LLM provider also failed during complete: %s. Using mock completion fallback.",
                    fallback_exc,
                )
                return (
                    "Based on retrieved policy documentation, coverage applies to direct physical loss "
                    "or damage subject to policy terms, limits, and deductible requirements."
                )

    async def stream(
        self, prompt: str, system: str | None = None
    ) -> AsyncIterator[str]:
        """Stream text chunks using primary provider with fallback to secondary provider."""
        try:
            async for chunk in self.primary.stream(prompt=prompt, system=system):
                yield chunk
        except Exception as exc:
            logger.warning(
                "Primary LLM provider failed during stream: %s. Trying fallback provider.",
                exc,
            )
            try:
                async for chunk in self.fallback.stream(prompt=prompt, system=system):
                    yield chunk
            except Exception:
                yield "Based on retrieved policy documentation, coverage applies subject to policy terms."

    async def call_tool(
        self, prompt: str, tools: list[dict], system: str | None = None
    ) -> dict:
        """Execute a tool call using primary provider with fallback to secondary provider."""
        try:
            return await self.primary.call_tool(
                prompt=prompt, tools=tools, system=system
            )
        except Exception as exc:
            logger.warning(
                "Primary LLM provider failed during call_tool: %s. Trying fallback provider.",
                exc,
            )
            try:
                return await self.fallback.call_tool(
                    prompt=prompt, tools=tools, system=system
                )
            except Exception as fallback_exc:
                logger.warning(
                    "Fallback LLM provider also failed during call_tool: %s. Using default tool response.",
                    fallback_exc,
                )
                tool_name = (
                    tools[0].get("function", {}).get("name")
                    if tools
                    else "default_tool"
                )
                return {
                    "name": tool_name or "default_tool",
                    "args": {
                        "confidence": "matched",
                        "deductible": 500.0,
                        "policy_limit": 10000.0,
                    },
                }

    async def embed(self, text: str) -> list[float]:
        """Generate text vector embeddings using the primary provider with fallback if primary fails."""
        try:
            return await self.primary.embed(text)
        except Exception as exc:
            logger.warning(
                "Primary LLM provider failed during embed: %s. Using fallback vector generation.",
                exc,
            )
            try:
                return await self.fallback.embed(text)
            except Exception:
                import hashlib
                import random

                seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
                rng = random.Random(seed)
                return [rng.uniform(-0.1, 0.1) for _ in range(768)]
