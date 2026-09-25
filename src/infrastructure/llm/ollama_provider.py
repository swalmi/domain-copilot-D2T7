from collections.abc import AsyncIterator

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings

from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.observability.token_usage import record_token_usage


class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementing the domain LLMProvider interface via LangChain."""

    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        chat_model: str = "llama3.2:3b",
        embedding_model: str = "nomic-embed-text",
        max_tokens: int = 512,
        num_ctx: int = 1024,
    ) -> None:
        """Initialize Ollama chat and embedding models with memory-bounded generation caps.

        ``num_ctx`` and ``num_predict`` are kept conservative so generation never
        spikes host memory (this box has ~3.7GB and the LLM is served in-process
        by ollama) and answers stream quickly.
        """
        self.base_url = base_url
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.max_tokens = max_tokens
        self.num_ctx = num_ctx
        self._llm = ChatOllama(
            base_url=base_url,
            model=chat_model,
            num_predict=max_tokens,
            num_ctx=num_ctx,
        )
        self._embeddings = OllamaEmbeddings(base_url=base_url, model=embedding_model)

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
        self,
        operation: str,
        prompt: str,
        completion: str,
        response=None,
    ) -> None:
        """Record token/cost usage for one LLM call (never raises into the hot path)."""
        try:
            p_tok, c_tok = self._usage_from_message(response) if response is not None else (None, None)
            record_token_usage(
                provider="ollama",
                model=self.chat_model if operation != "embed" else self.embedding_model,
                operation=operation,
                prompt=prompt,
                completion=completion,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
            )
        except Exception:
            pass

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Generate a complete text response from the Ollama model."""
        messages = self._build_messages(prompt=prompt, system=system)
        response = await self._llm.ainvoke(messages)
        text = str(response.content)
        self._account("complete", prompt, text, response)
        return text

    async def stream(
        self, prompt: str, system: str | None = None
    ) -> AsyncIterator[str]:
        """Stream chunks of text response from the Ollama model asynchronously."""
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
                "raw_content": content,
            }
        else:
            result = {"raw_content": content}
        self._account("call_tool", prompt, str(content), response)
        return result

    async def embed(self, text: str) -> list[float]:
        """Generate vector embedding representation for text using OllamaEmbeddings."""
        vector = await self._embeddings.aembed_query(text)
        try:
            record_token_usage(
                provider="ollama",
                model=self.embedding_model,
                operation="embed",
                prompt=text,
                completion="",
                prompt_tokens=None,
                completion_tokens=0,
                metadata={"embedding_dimension": len(vector)},
            )
        except Exception:
            pass
        return vector

