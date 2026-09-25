from datetime import date

import time

from src.application.retrieval.context_expander import expand_to_parent_sections
from src.application.retrieval.hybrid_search import hybrid_search_with_scores
from src.application.retrieval.prompt_loader import load_prompt
from src.domain.interfaces.llm_provider import LLMProvider
from src.domain.interfaces.vector_store import VectorStore
from src.infrastructure.observability.retrieval_logger import (
    build_context_expansion_step,
    build_llm_forward_step,
    update_last_entry,
)
from src.infrastructure.observability.system_logger import emit_system_log


class AskQuestionUseCase:
    """Use case for answering domain policy questions with RAG retrieval and pre-LLM refusal logic."""

    MAX_CONTEXT_CHARS = 6000

    def __init__(
        self,
        llm_provider: LLMProvider,
        vector_store: VectorStore,
        min_confidence_score: float = 0.01,
    ) -> None:
        """Initialize AskQuestionUseCase with LLM provider, vector store, and confidence threshold."""
        self._llm_provider = llm_provider
        self._vector_store = vector_store
        self._min_confidence_score = min_confidence_score

    async def execute(
        self,
        query: str,
        filters: dict | None = None,
        policy_id: str | None = None,
        policy_type: str | None = None,
        effective_date_before: date | None = None,
    ) -> dict:
        """Execute hybrid search, check confidence score, expand context, and generate an answer or refuse."""
        emit_system_log(
            "retrieval",
            "query_received",
            {
                "query": query,
                "policy_id": policy_id,
                "policy_type": policy_type,
                "filters": filters,
            },
        )
        results_with_scores = await hybrid_search_with_scores(
            vector_store=self._vector_store,
            embedder=self._llm_provider,
            query=query,
            filters=filters,
            policy_id=policy_id,
            policy_type=policy_type,
            effective_date_before=effective_date_before,
            top_k=5,
        )

        if not results_with_scores or results_with_scores[0][1] < self._min_confidence_score:
            emit_system_log(
                "generation",
                "refused",
                {
                    "query": query,
                    "reason": "below_min_confidence_or_empty_retrieval",
                    "top_score": results_with_scores[0][1] if results_with_scores else None,
                },
            )
            self._log_generation_steps(
                expanded_items=None,
                chunks_before_expansion=len(results_with_scores),
                forward={
                    "refused": True,
                    "skip_reason": "refused_before_generation: top RRF score below min_confidence_threshold",
                    "response_length_chars": 0,
                    "response": "Not enough information in the corpus to answer this question.",
                },
                note="refused_before_expansion: retrieval confidence below threshold",
            )
            return {
                "answer": "Not enough information in the corpus to answer this question.",
                "citations": [],
                "refused": True,
            }

        candidate_chunks = [chunk for chunk, _ in results_with_scores]
        expanded_context_items = await expand_to_parent_sections(
            candidate_chunks, self._vector_store
        )

        context_blocks = []
        for idx, item in enumerate(expanded_context_items, start=1):
            chunk = item["cited_chunk"]
            text_content = item["context_for_llm"]
            block = (
                f"[Document: {chunk.source_document} | Policy: {chunk.policy_id} "
                f"| Section: {chunk.section} | Page: {chunk.page}]\n{text_content}"
            )
            context_blocks.append(block)

        context_str = "\n\n---\n\n".join(context_blocks)
        context_str = self._bounded_context(context_str)
        prompt_template = load_prompt("ask_qa", "v1")
        prompt_text = prompt_template.format(context=context_str, query=query)
        emit_system_log(
            "generation",
            "prompt_assembled",
            {
                "query": query,
                "context_block_count": len(context_blocks),
                "context_char_count": len(context_str),
                "prompt_char_count": len(prompt_text),
                "min_confidence_threshold": self._min_confidence_score,
                "parent_expansion": True,
            },
        )

        gen_start = time.monotonic()
        answer = await self._llm_provider.complete(prompt_text)
        self._log_generation_steps(
            expanded_items=expanded_context_items,
            chunks_before_expansion=len(candidate_chunks),
            forward={
                "model": self._model_name(),
                "streaming": False,
                "prompt_length_chars": len(prompt_text),
                "prompt": prompt_text,
                "context_char_count": len(context_str),
                "response_length_chars": len(answer),
                "response": answer,
                "elapsed_s": round(time.monotonic() - gen_start, 3),
            },
        )

        citations = [
            {
                "chunk_id": str(chunk.chunk_id),
                "text_snippet": chunk.text,
                "source": chunk.source_document,
                "section": chunk.section,
                "page": chunk.page,
                "policy_id": chunk.policy_id,
                "version": chunk.version,
            }
            for chunk in candidate_chunks
        ]
        emit_system_log(
            "generation",
            "completed",
            {
                "query": query,
                "answer_char_count": len(answer),
                "citation_count": len(citations),
                "citation_chunk_ids": [c["chunk_id"] for c in citations],
                "refused": False,
            },
        )

        return {
            "answer": answer,
            "citations": citations,
            "refused": False,
        }

    async def execute_stream(
        self,
        query: str,
        filters: dict | None = None,
        policy_id: str | None = None,
        policy_type: str | None = None,
        effective_date_before: date | None = None,
    ):
        """Execute RAG retrieval and stream response tokens as SSE event payloads."""
        emit_system_log(
            "retrieval",
            "query_received",
            {
                "query": query,
                "policy_id": policy_id,
                "policy_type": policy_type,
                "filters": filters,
                "stream": True,
            },
        )
        results_with_scores = await hybrid_search_with_scores(
            vector_store=self._vector_store,
            embedder=self._llm_provider,
            query=query,
            filters=filters,
            policy_id=policy_id,
            policy_type=policy_type,
            effective_date_before=effective_date_before,
            top_k=5,
        )

        if not results_with_scores or results_with_scores[0][1] < self._min_confidence_score:
            refused_msg = "Not enough information in the corpus to answer this question."
            emit_system_log(
                "generation",
                "refused",
                {
                    "query": query,
                    "reason": "below_min_confidence_or_empty_retrieval",
                    "top_score": results_with_scores[0][1] if results_with_scores else None,
                    "stream": True,
                },
            )
            self._log_generation_steps(
                expanded_items=None,
                chunks_before_expansion=len(results_with_scores),
                forward={
                    "refused": True,
                    "skip_reason": "refused_before_generation: top RRF score below min_confidence_threshold",
                    "response_length_chars": 0,
                    "response": refused_msg,
                },
                note="refused_before_expansion: retrieval confidence below threshold",
            )
            yield {"type": "token", "content": refused_msg}
            yield {"type": "done", "citations": [], "refused": True}
            return

        candidate_chunks = [chunk for chunk, _ in results_with_scores]
        expanded_context_items = await expand_to_parent_sections(
            candidate_chunks, self._vector_store
        )

        context_blocks = []
        for idx, item in enumerate(expanded_context_items, start=1):
            chunk = item["cited_chunk"]
            text_content = item["context_for_llm"]
            block = (
                f"[Document: {chunk.source_document} | Policy: {chunk.policy_id} "
                f"| Section: {chunk.section} | Page: {chunk.page}]\n{text_content}"
            )
            context_blocks.append(block)

        context_str = "\n\n---\n\n".join(context_blocks)
        context_str = self._bounded_context(context_str)
        prompt_template = load_prompt("ask_qa", "v1")
        prompt_text = prompt_template.format(context=context_str, query=query)
        emit_system_log(
            "generation",
            "prompt_assembled",
            {
                "query": query,
                "context_block_count": len(context_blocks),
                "context_char_count": len(context_str),
                "prompt_char_count": len(prompt_text),
                "stream": True,
            },
        )
        emit_system_log(
            "generation",
            "started",
            {"query": query, "provider_stream": True},
        )

        response_text = ""
        gen_start = time.monotonic()
        async for token in self._llm_provider.stream(prompt_text):
            response_text += token
            yield {"type": "token", "content": token}
        self._log_generation_steps(
            expanded_items=expanded_context_items,
            chunks_before_expansion=len(candidate_chunks),
            forward={
                "model": self._model_name(),
                "streaming": True,
                "prompt_length_chars": len(prompt_text),
                "prompt": prompt_text,
                "context_char_count": len(context_str),
                "response_length_chars": len(response_text),
                "response": response_text,
                "elapsed_s": round(time.monotonic() - gen_start, 3),
            },
        )

        citations = [
            {
                "chunk_id": str(chunk.chunk_id),
                "text_snippet": chunk.text,
                "source": chunk.source_document,
                "section": chunk.section,
                "page": chunk.page,
                "policy_id": chunk.policy_id,
                "version": chunk.version,
            }
            for chunk in candidate_chunks
        ]
        emit_system_log(
            "generation",
            "completed",
            {
                "query": query,
                "token_count_estimate": len(response_text),
                "citation_count": len(citations),
                "citation_chunk_ids": [c["chunk_id"] for c in citations],
                "refused": False,
            },
        )
        yield {"type": "done", "citations": citations, "refused": False}

    @staticmethod
    def _log_generation_steps(
        expanded_items: list[dict] | None,
        chunks_before_expansion: int,
        forward: dict,
        note: str | None = None,
    ) -> None:
        """Patch the retrieval log entry with the expansion and forward-pass steps."""
        update_last_entry(
            {
                "step_4_context_expansion": build_context_expansion_step(
                    expanded_items,
                    chunks_before_expansion=chunks_before_expansion,
                    note=note,
                ),
                "step_5_llm_forward": build_llm_forward_step(forward),
            }
        )

    def _model_name(self) -> str:
        """Best-effort model identifier for logging."""
        return str(
            getattr(self._llm_provider, "model", None)
            or getattr(self._llm_provider, "model_name", None)
            or type(self._llm_provider).__name__
        )

    @staticmethod
    def _bounded_context(context: str) -> str:
        """Trim the assembled context so the prompt always fits a small context window.

        Keeps the leading (most relevant) blocks whole and truncates only the tail
        context if the total still exceeds ``MAX_CONTEXT_CHARS``.
        """
        if len(context) <= AskQuestionUseCase.MAX_CONTEXT_CHARS:
            return context
        return context[: AskQuestionUseCase.MAX_CONTEXT_CHARS].rstrip() + "\n…(additional context omitted)"

