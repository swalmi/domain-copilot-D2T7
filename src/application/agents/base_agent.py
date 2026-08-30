from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from src.domain.interfaces.llm_provider import LLMProvider


class BaseAgent(ABC):
    """Abstract base class for domain co-pilot workflow agents enforcing tool allow-lists."""

    ALLOWED_TOOLS: ClassVar[list[str]] = []

    def __init__(self, llm_provider: LLMProvider, name: str) -> None:
        """Initialize BaseAgent with LLM provider and agent name."""
        self.llm_provider = llm_provider
        self.name = name

    @abstractmethod
    async def run(self, **kwargs) -> BaseModel:
        """Execute agent workflow logic and return a structured Pydantic model contract."""

    async def _call_tool(self, tool_schema: dict, prompt: str) -> dict:
        """Call LLM provider tool execution while enforcing restricted ALLOWED_TOOLS allow-list."""
        tool_name = tool_schema.get("function", {}).get("name") or tool_schema.get("name")
        if self.ALLOWED_TOOLS and tool_name not in self.ALLOWED_TOOLS:
            raise PermissionError(
                f"Agent '{self.name}' is not authorized to execute tool '{tool_name}'. "
                f"Allowed tools: {self.ALLOWED_TOOLS}"
            )
        return await self.llm_provider.call_tool(prompt=prompt, tools=[tool_schema])
