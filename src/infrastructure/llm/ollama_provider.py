from collections.abc import AsyncIterator

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings

from src.domain.interfaces.llm_provider import LLMProvider


class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementing the domain LLMProvider interface via LangChain."""

    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        chat_model: str = "llama3.2:3b",
        embedding_model: str = "nomic-embed-text",
        max_tokens: int = 2048,
    ) -> None:
        """Initialize Ollama chat and embedding models with max token consumption caps."""
        self.base_url = base_url
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.max_tokens = max_tokens
        self._llm = ChatOllama(base_url=base_url, model=chat_model, num_predict=max_tokens)
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

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Generate a complete text response from the Ollama model."""
        messages = self._build_messages(prompt=prompt, system=system)
        response = await self._llm.ainvoke(messages)
        return str(response.content)

    async def stream(
        self, prompt: str, system: str | None = None
    ) -> AsyncIterator[str]:
        """Stream chunks of text response from the Ollama model asynchronously."""
        messages = self._build_messages(prompt=prompt, system=system)
        async for chunk in self._llm.astream(messages):
            if chunk.content:
                yield str(chunk.content)

    async def call_tool(
        self, prompt: str, tools: list[dict], system: str | None = None
    ) -> dict:
        """Execute a tool call using the bound tools and return tool call details."""
        messages = self._build_messages(prompt=prompt, system=system)
        bound_llm = self._llm.bind_tools(tools)
        response = await bound_llm.ainvoke(messages)
        tool_calls = getattr(response, "tool_calls", [])
        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
            first_call = tool_calls[0]
            return {
                "name": first_call.get("name", ""),
                "args": first_call.get("args", {}),
            }
        return {}

    async def embed(self, text: str) -> list[float]:
        """Generate vector embedding representation for text using OllamaEmbeddings."""
        return await self._embeddings.aembed_query(text)
