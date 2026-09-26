"""Unit tests for retrieval-log pipeline steps (expansion and LLM forward pass)."""

import json
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from src.infrastructure.observability import retrieval_logger
from src.infrastructure.observability.retrieval_logger import (
    build_agent_steps,
    build_context_expansion_step,
    build_llm_forward_step,
    create_retrieval_log,
    update_entry_for_query,
    update_last_entry,
)


def _chunk():
    from src.domain.entities.policy import CitedChunk

    return CitedChunk(
        chunk_id=uuid4(),
        text="The named peril is windstorm damage to the dwelling.",
        policy_id="SHELTER-HO3",
        source_document="ho3.txt",
        section="Section I",
        page=17,
        chunk_type="narrative",
        version="2007-01",
        effective_date=date(2007, 1, 1),
    )


def _expanded_item():
    chunk = _chunk()
    return {
        "cited_chunk": chunk,
        "context_for_llm": "SECTION I - PERILS INSURED. " + chunk.text,
    }


@pytest.fixture
def log_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "retrieval_log.json"
    monkeypatch.setattr(retrieval_logger, "_default_path", lambda: path)
    return path


def test_context_expansion_step_lists_expanded_items():
    step = build_context_expansion_step([_expanded_item()], chunks_before_expansion=5)

    assert step["expansion_applied"] is True
    assert step["total_expanded_items"] == 1
    assert step["items_expanded"][0]["cited_chunk"]["policy_id"] == "SHELTER-HO3"
    assert step["items_expanded"][0]["expanded_from_single_chunk"] is True
    assert "skip_reason" not in step


def test_context_expansion_step_explains_empty_result():
    step = build_context_expansion_step(None, chunks_before_expansion=3)

    assert step["items_expanded"] == []
    assert step["expansion_applied"] is False
    assert step["total_expanded_items"] == 0
    assert "skip_reason" in step


def test_context_expansion_step_keeps_caller_note():
    step = build_context_expansion_step([], note="not_applicable: agent retrieval")

    assert step["skip_reason"] == "not_applicable: agent retrieval"


def test_llm_forward_step_records_prompt_and_response():
    step = build_llm_forward_step(
        {
            "model": "llama3.2:3b",
            "prompt": "Context: windstorm\nQuestion: what is covered?",
            "prompt_length_chars": 45,
            "context_char_count": 20,
            "response": "Windstorm damage to the dwelling is covered.",
            "response_length_chars": 45,
            "elapsed_s": 1.5,
        }
    )

    assert step["executed"] is True
    assert step["model"] == "llama3.2:3b"
    assert step["prompt_chars"] == 45
    assert step["response_preview"].startswith("Windstorm damage")
    assert step["elapsed_s"] == 1.5


def test_llm_forward_step_marked_skipped_when_prompt_absent():
    step = build_llm_forward_step({"skip_reason": "refused_before_generation"})

    assert step["executed"] is False
    assert step["skip_reason"] == "refused_before_generation"


def test_llm_forward_step_explains_missing_generation():
    step = build_llm_forward_step(None)

    assert step["executed"] is False
    assert step["prompt_chars"] == 0
    assert step["response_chars"] == 0
    assert "generation_not_recorded" in step["skip_reason"]


def test_create_retrieval_log_numbers_all_steps_and_patches_forward(log_file: Path):
    chunk = _chunk()
    create_retrieval_log(
        query="is windstorm damage covered?",
        dense_results=[chunk],
        keyword_results=[chunk],
        fused_results=[(chunk, 0.03)],
        top_k=5,
    )

    logged = json.loads(log_file.read_text(encoding="utf-8"))["entries"][-1]
    assert "step_4_context_expansion" in logged
    assert "step_5_llm_forward" in logged
    assert "step_6_agent_coverage_matcher" in logged
    assert "step_7_agent_exclusion_analyst" in logged
    assert "step_8_agent_adjudication_drafter" in logged
    assert logged["step_5_llm_forward"]["executed"] is False

    assert update_last_entry({"step_5_llm_forward": build_llm_forward_step({"response": "Yes", "response_length_chars": 3})}) is True

    patched = json.loads(log_file.read_text(encoding="utf-8"))["entries"][-1]
    assert patched["step_5_llm_forward"]["executed"] is True
    assert patched["step_5_llm_forward"]["response_preview"] == "Yes"
    assert len(json.loads(log_file.read_text(encoding="utf-8"))["entries"]) == 1


def test_update_last_entry_without_entries_is_noop(log_file: Path):
    assert update_last_entry({"step_5_llm_forward": {}}) is False
    assert log_file.exists() is False


def test_update_last_entry_with_no_updates_is_noop(log_file: Path):
    create_retrieval_log(query="hello", fused_results=[])

    assert update_last_entry({}) is False


def test_update_entry_for_query_patches_own_entry_instead_of_appending(log_file: Path):
    """A claim must never add a second, blank retrieval record.

    The live bug: ``run_adjudication`` appended a fresh entry for the agent
    results, producing a record with ``filters_applied={}`` and
    ``embedding_dimension=0`` that read like a failed search, while the entry
    holding the real cause sat next to it.
    """
    chunk = _chunk()
    create_retrieval_log(
        query="a kitchen fire damaged the cabinets",
        query_embedding=[0.1, 0.2, 0.3],
        dense_results=[chunk],
        keyword_results=[chunk],
        fused_results=[(chunk, 0.03)],
        top_k=5,
    )
    before = len(json.loads(log_file.read_text(encoding="utf-8"))["entries"])

    patched = update_entry_for_query(
        "a kitchen fire damaged the cabinets",
        {"final_decision": {"refused": False, "recommendation": "partial"}},
    )

    entries = json.loads(log_file.read_text(encoding="utf-8"))["entries"]
    assert patched is True
    assert len(entries) == before, "agent steps must patch, not append"
    assert entries[-1]["final_decision"]["recommendation"] == "partial"
    # The retrieval evidence must survive the patch.
    assert entries[-1]["query_embedding"]["dimension"] > 0
    assert entries[-1]["step_1_dense_search"]["results"]


def test_update_entry_for_query_targets_most_recent_matching_entry(log_file: Path):
    create_retrieval_log(query="first question", fused_results=[])
    create_retrieval_log(query="unrelated question", fused_results=[])
    create_retrieval_log(query="first question", fused_results=[])

    assert update_entry_for_query("first question", {"marker": "hit"}) is True

    entries = json.loads(log_file.read_text(encoding="utf-8"))["entries"]
    assert len(entries) == 3
    assert entries[2]["marker"] == "hit"
    assert "marker" not in entries[0]
    assert "marker" not in entries[1]


def test_update_entry_for_query_reports_no_match_so_caller_can_fall_back(log_file: Path):
    create_retrieval_log(query="logged question", fused_results=[])

    assert update_entry_for_query("a query that was never logged", {"marker": "x"}) is False

    entries = json.loads(log_file.read_text(encoding="utf-8"))["entries"]
    assert len(entries) == 1
    assert "marker" not in entries[0]


def test_update_entry_for_query_with_no_updates_is_noop(log_file: Path):
    create_retrieval_log(query="hello", fused_results=[])

    assert update_entry_for_query("hello", {}) is False


def test_build_agent_steps_matches_create_retrieval_log_schema(log_file: Path):
    """The patch path and the create path must emit identical step keys."""
    create_retrieval_log(
        query="schema check",
        fused_results=[],
        refusal_reason="No matching policy coverage sections found",
    )
    created = json.loads(retrieval_logger._default_path().read_text(encoding="utf-8"))["entries"][-1]

    built = build_agent_steps(refusal_reason="No matching policy coverage sections found")

    assert "refusal" in built
    assert built["refusal"] == created["refusal"]
    for key in (
        "step_6_agent_coverage_matcher",
        "step_7_agent_exclusion_analyst",
        "step_8_agent_adjudication_drafter",
    ):
        assert key in built
        assert key in created

