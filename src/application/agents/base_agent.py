import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import BaseModel

from src.domain.interfaces.llm_provider import LLMProvider


class BaseAgent(ABC):
    """Abstract base class for domain co-pilot workflow agents enforcing tool allow-lists and schema validation."""

    ALLOWED_TOOLS: ClassVar[list[str]] = []

    def __init__(self, llm_provider: LLMProvider, name: str, on_progress: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Initialize BaseAgent with LLM provider and agent name."""
        self.llm_provider = llm_provider
        self.name = name
        self._on_progress = on_progress
        self.tool_responses: list[dict[str, Any]] = []

    @abstractmethod
    async def run(self, **kwargs) -> BaseModel:
        """Execute agent workflow logic and return a structured Pydantic model contract."""

    async def _call_tool(self, tool_schema: dict, prompt: str) -> dict:
        """Call LLM provider tool execution enforcing ALLOWED_TOOLS security control and result schema validation."""
        tool_name = tool_schema.get("function", {}).get("name") or tool_schema.get("name")
        if self.ALLOWED_TOOLS and tool_name not in self.ALLOWED_TOOLS:
            raise PermissionError(
                f"Agent '{self.name}' is not authorized to execute tool '{tool_name}'. "
                f"Allowed tools: {self.ALLOWED_TOOLS}"
            )

        start = time.monotonic()
        done = threading.Event()
        beat_task: asyncio.Task | None = None
        if self._on_progress is not None:

            async def _beat() -> None:
                while not done.is_set():
                    await asyncio.sleep(1.0)
                    if not done.is_set():
                        self._on_progress(
                            {
                                "agent": self.name,
                                "stage": "llm_call",
                                "elapsed_s": round(time.monotonic() - start, 1),
                                "detail": "LLM tool call in flight…",
                            }
                        )

            beat_task = asyncio.create_task(_beat())
        try:
            result = await self.llm_provider.call_tool(prompt=prompt, tools=[tool_schema])
        finally:
            done.set()
            if beat_task is not None:
                beat_task.cancel()
                try:
                    await beat_task
                except asyncio.CancelledError:
                    pass
        if not isinstance(result, dict):
            raise TypeError(
                f"Tool call output from '{tool_name}' must be a dict structure, got {type(result)}"
            )
        self.tool_responses.append(
            {
                "tool_name": tool_name,
                "prompt_length_chars": len(prompt),
                "prompt": prompt,
                "elapsed_s": round(time.monotonic() - start, 3),
                "response": result,
            }
        )
        return result
