"""Tests that the RAG answer path records expansion and forward-pass steps."""

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from src.application.use_cases import ask_question as ask_module
from src.application.retrieval.hybrid_search import RetrievalConfidence
from src.application.use_cases.ask_question import AskQuestionUseCase
from src.domain.entities.policy import CitedChunk
from src.infrastructure.observability import retrieval_logger


class _FakeLLM:
    model = "fake-llm"

    async def complete(self, prompt: str) -> str:
        return "Windstorm damage to the dwelling is covered under Section I."

    async def stream(self, prompt: str):
        for token in ["Windstorm damage ", "is covered."]:
            yield token

    async def embed(self, text: str) -> list[float]:
        return [0.1] * 8

    def __call__(self, prompt: str) -> str:  # pragma: no cover - not used
        return prompt


def _chunk() -> CitedChunk:
    return CitedChunk(
        chunk_id=uuid4(),
        text="Windstorm damage to the dwelling is a named peril.",
        policy_id="SHELTER-HO3",
        source_document="ho3.txt",
        section="Section I",
        page=17,
        chunk_type="narrative",
        version="2007-01",
        effective_date=date(2007, 1, 1),
    )


@pytest.fixture
def logged_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "retrieval_log.json"
    monkeypatch.setattr(retrieval_logger, "_default_path", lambda: path)
    import json

    def read_entry():
        return json.loads(path.read_text(encoding="utf-8"))["entries"][-1]

    return read_entry


@pytest.mark.asyncio
async def test_execute_records_expansion_and_forward_steps(monkeypatch, logged_entry):
    chunk = _chunk()

    async def fake_hybrid(**kwargs):
        retrieval_logger.create_retrieval_log(
            query=kwargs["query"],
            dense_results=[chunk],
            keyword_results=[chunk],
            fused_results=[(chunk, 0.03)],
        )
        return [(chunk, 0.03)], RetrievalConfidence(
            top_rrf_score=0.03,
            max_rrf_score=0.0328,
            rrf_ratio=0.92,
            top_cosine_distance=0.2,
            is_confident=True,
            reason="retrieval_confident",
        )

    async def fake_expand(chunks, vector_store):
        return [
            {
                "cited_chunk": chunk,
                "context_for_llm": "SECTION I - PERILS INSURED. Windstorm damage is covered.",
            }
        ]

    monkeypatch.setattr(ask_module, "hybrid_search_with_confidence", fake_hybrid)
    monkeypatch.setattr(ask_module, "expand_to_parent_sections", fake_expand)

    result = await AskQuestionUseCase(llm_provider=_FakeLLM(), vector_store=object()).execute(
        "is windstorm damage covered?"
    )

    assert result["refused"] is False
    entry = logged_entry()
    assert entry["step_4_context_expansion"]["expansion_applied"] is True
    assert entry["step_4_context_expansion"]["items_expanded"][0]["cited_chunk"]["policy_id"] == "SHELTER-HO3"
    forward = entry["step_5_llm_forward"]
    assert forward["executed"] is True
    assert forward["model"] == "fake-llm"
    assert forward["prompt_chars"] > 0
    assert "Windstorm damage" in forward["response_preview"]


@pytest.mark.asyncio
async def test_execute_stream_records_forward_step(monkeypatch, logged_entry):
    chunk = _chunk()

    async def fake_hybrid(**kwargs):
        retrieval_logger.create_retrieval_log(
            query=kwargs["query"],
            dense_results=[chunk],
            keyword_results=[chunk],
            fused_results=[(chunk, 0.03)],
        )
        return [(chunk, 0.03)], RetrievalConfidence(
            top_rrf_score=0.03,
            max_rrf_score=0.0328,
            rrf_ratio=0.92,
            top_cosine_distance=0.2,
            is_confident=True,
            reason="retrieval_confident",
        )

    async def fake_expand(chunks, vector_store):
        return [{"cited_chunk": chunk, "context_for_llm": chunk.text}]

    monkeypatch.setattr(ask_module, "hybrid_search_with_confidence", fake_hybrid)
    monkeypatch.setattr(ask_module, "expand_to_parent_sections", fake_expand)

    events = [
        event
        async for event in AskQuestionUseCase(
            llm_provider=_FakeLLM(), vector_store=object()
        ).execute_stream("is windstorm damage covered?")
    ]

    assert events[-1]["type"] == "done"
    forward = logged_entry()["step_5_llm_forward"]
    assert forward["executed"] is True
    assert forward["streaming"] is True
    assert forward["response_preview"] == "Windstorm damage is covered."


@pytest.mark.asyncio
async def test_refusal_records_skip_reasons(monkeypatch, logged_entry):
    async def fake_hybrid(**kwargs):
        retrieval_logger.create_retrieval_log(query=kwargs["query"], fused_results=[])
        return [], RetrievalConfidence(
            top_rrf_score=0.0,
            max_rrf_score=0.0328,
            rrf_ratio=0.0,
            top_cosine_distance=None,
            is_confident=False,
            reason="no_results",
        )

    monkeypatch.setattr(ask_module, "hybrid_search_with_confidence", fake_hybrid)

    result = await AskQuestionUseCase(llm_provider=_FakeLLM(), vector_store=object()).execute(
        "what is covered?"
    )

    assert result["refused"] is True
    entry = logged_entry()
    assert entry["step_4_context_expansion"]["expansion_applied"] is False
    assert "refused_before_expansion" in entry["step_4_context_expansion"]["skip_reason"]
    assert entry["step_5_llm_forward"]["executed"] is False
    assert "refused_before_generation" in entry["step_5_llm_forward"]["skip_reason"]
