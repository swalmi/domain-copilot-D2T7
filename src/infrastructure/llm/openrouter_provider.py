from collections.abc import AsyncIterator

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.observability.token_usage import record_token_usage


class OpenRouterProvider(LLMProvider):
    """OpenRouter LLM provider implementing the LLMProvider interface via ChatOpenAI."""

    OPENROUTER_MODELS: dict[str, str] = {
        "nvidia": "nvidia/nemotron-3-30b-a3b:free",
        "openai": "openai/gpt-4o-mini:free",
        "liquid": "liquid/lfm-2.5-2.6b:free",
    }

    def __init__(
        self,
        api_key: str,
        model_name: str = "nvidia",
        base_url: str = "https://openrouter.ai/api/v1",
        max_tokens: int = 2048,
    ) -> None:
        """Initialize OpenRouterProvider with API key, model selection, base URL, and max_tokens limit."""
        self.api_key = api_key
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.model_id = self.OPENROUTER_MODELS.get(model_name.lower(), model_name)
        self._llm = ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=self.model_id,
            max_tokens=max_tokens,
        )

    def _build_messages(
        self, prompt: str, system: str | None = None
    ) -> list[BaseMessage]:
        """Construct input messages for the language model, including optional system instructions."""
        messages: list[BaseMessage] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        return messages

    @staticmethod
    def _usage_from_message(response) -> tuple[int | None, int | None]:
        """Extract provider-reported token counts from an AIMessage when present."""
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return None, None
        return usage.get("input_tokens"), usage.get("output_tokens")

    def _account(
        self, operation: str, prompt: str, completion: str, response=None
    ) -> None:
        """Record token/cost usage for one LLM call (never raises into the hot path)."""
        try:
            p_tok, c_tok = (
                self._usage_from_message(response) if response is not None else (None, None)
            )
            record_token_usage(
                provider="openrouter",
                model=self.model_id,
                operation=operation,
                prompt=prompt,
                completion=completion,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
            )
        except Exception:
            pass

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Generate a complete text response from OpenRouter."""
        messages = self._build_messages(prompt=prompt, system=system)
        response = await self._llm.ainvoke(messages)
        text = str(response.content)
        self._account("complete", prompt, text, response)
        return text

    async def stream(
        self, prompt: str, system: str | None = None
    ) -> AsyncIterator[str]:
        """Stream chunks of text response from OpenRouter asynchronously."""
        messages = self._build_messages(prompt=prompt, system=system)
        parts: list[str] = []
        last = None
        async for chunk in self._llm.astream(messages):
            last = chunk
            if chunk.content:
                text = str(chunk.content)
                parts.append(text)
                yield text
        self._account("stream", prompt, "".join(parts), last)

    async def call_tool(
        self, prompt: str, tools: list[dict], system: str | None = None
    ) -> dict:
        """Execute a tool call using the bound tools and return tool call details."""
        messages = self._build_messages(prompt=prompt, system=system)
        bound_llm = self._llm.bind_tools(tools)
        response = await bound_llm.ainvoke(messages)
        tool_calls = getattr(response, "tool_calls", [])
        content = getattr(response, "content", "") or ""
        result: dict
        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
            first_call = tool_calls[0]
            result = {
                "name": first_call.get("name", ""),
                "args": first_call.get("args", {}),
            }
        else:
            result = {}
        self._account("call_tool", prompt, str(content), response)
        return result

    async def embed(self, text: str) -> list[float]:
        """Raise NotImplementedError as OpenRouterProvider does not support embeddings."""
        raise NotImplementedError(
            "OpenRouterProvider does not support embeddings. Use OllamaProvider for embeddings."
        )
