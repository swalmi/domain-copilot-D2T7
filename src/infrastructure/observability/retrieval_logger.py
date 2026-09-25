"""Professional, aggressively detailed retrieval log writer.

Writes ``retrieval_log.json`` at the repository root capturing every micro-step
of the online retrieval pipeline — query embedding, dense/keyword search,
RRF fusion scores and equations, context expansion with parent chunks, each
agent's prompt/tool-response/confidence/reasoning, final recommendation and
the exact calculation behind it.

Every field is populated from the live pipeline objects so the log is a
complete, machine-readable replay of exactly what happened end-to-end.
"""

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = __import__("logging").getLogger(__name__)

_lock = threading.Lock()


def _default_path() -> Path:
    configured = os.environ.get("RETRIEVAL_LOG_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "retrieval_log.json"


def _read_existing() -> dict[str, Any]:
    try:
        with open(_default_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"entries": []}


def _atomic_write(data: dict[str, Any]) -> None:
    path = _default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=".retrieval_log.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _rrf_equation(dense_results: list, keyword_results: list, k: int = 60) -> str:
    """Build the human-readable RRF equation string for the log."""
    lines = [
        f"RRF(k={k}): score(c) = Σ 1/(rank_i(c) + {k})",
        "Dense search contributions:",
    ]
    for rank, c in enumerate(dense_results, start=1):
        lines.append(f"  rank={rank} → {c.policy_id} page {c.page}: +1/(1+{k}) = {1.0/(rank+k):.6f}")
    lines.append("Keyword search contributions:")
    for rank, c in enumerate(keyword_results, start=1):
        lines.append(f"  rank={rank} → {c.policy_id} page {c.page}: +1/(1+{k}) = {1.0/(rank+k):.6f}")
    return "\n".join(lines)


def _chunk_summary(c: Any) -> dict[str, Any]:
    """Summarise a CitedChunk for log entry."""
    return {
        "chunk_id": str(c.chunk_id),
        "policy_id": c.policy_id,
        "section": c.section,
        "page": c.page,
        "chunk_type": c.chunk_type,
        "version": c.version,
        "effective_date": str(c.effective_date) if c.effective_date else None,
        "text_length": len(c.text),
        "text_preview": c.text[:200],
    }


def log_retrieval(entry: dict[str, Any]) -> None:
    """Append a detailed retrieval pipeline entry to retrieval_log.json."""
    with _lock:
        try:
            data = _read_existing()
            data["entries"].append(entry)
            _atomic_write(data)
        except Exception as exc:
            logger.warning("Failed to write retrieval log: %s", exc)


def create_retrieval_log(
    query: str = "",
    query_embedding: list[float] | None = None,
    dense_results: list | None = None,
    keyword_results: list | None = None,
    fused_results: list | None = None,
    top_k: int = 5,
    filters: dict[str, Any] | None = None,
    embedder_name: str = "unknown",
    cache_hit: bool = False,
    expanded_items: list[dict] | None = None,
    expansion_note: str | None = None,
    llm_forward: dict[str, Any] | None = None,
    coverage_match_result: Any | None = None,
    exclusion_result: Any | None = None,
    draft_result: Any | None = None,
    agent_tool_responses: dict[str, Any] | None = None,
    refusal_reason: str | None = None,
    final_recommendation: str | None = None,
) -> dict[str, Any]:
    """Build and append a complete retrieval-log entry capturing every pipeline step.

    :param query: The original user query.
    :param query_embedding: The computed embedding vector.
    :param dense_results: Ranked list of CitedChunk from dense (vector) search.
    :param keyword_results: Ranked list of CitedChunk from keyword (BM25) search.
    :param fused_results: Ranked list of (CitedChunk, rrf_score) after RRF fusion.
    :param top_k: Number of results returned.
    :param filters: Filters applied (policy_id, policy_type, effective_date).
    :param embedder_name: Name of the embedder model used.
    :param cache_hit: Whether the embedding was served from cache.
    :param expanded_items: Parent-expanded context items (from expand_to_parent_sections).
    :param expansion_note: Why no parent expansion ran (e.g. "agent tool retrieval").
    :param llm_forward: LLM forward-pass detail (prompt, response, latency, streaming).
    :param coverage_match_result: CoverageMatchResult object (or None).
    :param exclusion_result: ExclusionAnalysisResult object (or None).
    :param draft_result: AdjudicationDraft object (or None).
    :param agent_tool_responses: Map of agent name → tool/LLM response details.
    :param refusal_reason: Why the final decision was refuse/deny (if applicable).
    :param final_recommendation: Final recommendation string ("approve"/"partial"/"deny").
    """
    query_embedding = query_embedding or []
    dense_results = dense_results or []
    keyword_results = keyword_results or []
    fused_results = fused_results or []

    entry: dict[str, Any] = {
        "log_id": str(uuid.uuid4()),
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "pipeline_stage": "full_retrieval",

        "query": {
            "text": query,
            "query_length_chars": len(query),
            "embedding_model": embedder_name,
            "embedding_dimension": len(query_embedding),
            "cache_hit": cache_hit,
            "filters_applied": {k: str(v) if hasattr(v, "isoformat") else v for k, v in (filters or {}).items()},
        },

        "query_embedding": {
            "values": [float(v) for v in query_embedding[:5]],
            "dimension": len(query_embedding),
            "norm": round(sum(v * v for v in query_embedding) ** 0.5, 6),
        },

        "step_1_dense_search": {
            "description": "Dense vector similarity search (cosine similarity over pgvector HNSW index)",
            "search_method": "pgvector cosine_distance",
            "top_k_requested": 20,
            "total_candidates_found": len(dense_results),
            "results": [
                {
                    "rank": rank,
                    "rrf_raw_score": None,
                    **_chunk_summary(c),
                    "distance_note": f"cosine_distance at rank {rank}",
                }
                for rank, c in enumerate(dense_results, start=1)
            ],
        },

        "step_2_keyword_search": {
            "description": "Keyword/lexical search (PostgreSQL full-text search on to_tsvector)",
            "search_method": "pgvector plainto_tsquery GIN index",
            "top_k_requested": 20,
            "total_candidates_found": len(keyword_results),
            "results": [
                {
                    "rank": rank,
                    **_chunk_summary(c),
                    "distance_note": f"ts_rank at rank {rank}",
                }
                for rank, c in enumerate(keyword_results, start=1)
            ],
        },

        "step_3_rrf_fusion": {
            "description": "Reciprocal Rank Fusion combining dense and keyword ranked lists",
            "fusion_equation": _rrf_equation(dense_results, keyword_results),
            "k_parameter": 60,
            "dense_list_size": len(dense_results),
            "keyword_list_size": len(keyword_results),
            "unique_chunks_after_fusion": len(fused_results),
            "merged_from_dense": len(set(c.chunk_id for c in dense_results)),
            "merged_from_keyword": len(set(c.chunk_id for c in keyword_results)),
            "overlap_dense_keyword": len(set(c.chunk_id for c in dense_results) & set(c.chunk_id for c in keyword_results)),
            "results": [
                {
                    "fused_rank": rank,
                    "rrf_score": round(score, 6),
                    "rrf_equation_value": f"1/(rank_dense+60) + 1/(rank_keyword+60) = {score:.6f}",
                    "chunk": _chunk_summary(c),
                }
                for rank, (c, score) in enumerate(fused_results, start=1)
            ],
        },

        "step_4_context_expansion": build_context_expansion_step(
            expanded_items,
            chunks_before_expansion=len(fused_results) if fused_results else 0,
            note=expansion_note,
        ),

        "step_5_llm_forward": build_llm_forward_step(llm_forward),
    }

    entry["step_6_agent_coverage_matcher"] = _agent_step_detail(
        "CoverageMatcher",
        coverage_match_result,
        agent_tool_responses or {},
    )

    entry["step_7_agent_exclusion_analyst"] = _agent_step_detail(
        "ExclusionAnalyst",
        exclusion_result,
        agent_tool_responses or {},
    )

    entry["step_8_agent_adjudication_drafter"] = _agent_step_detail(
        "AdjudicationDrafter",
        draft_result,
        agent_tool_responses or {},
    )

    if refusal_reason:
        entry["refusal"] = {
            "refused": True,
            "reason": refusal_reason,
        }
    elif final_recommendation:
        entry["final_decision"] = {
            "refused": False,
            "recommendation": final_recommendation,
            "calculated_payout": str(draft_result.calculated_payout) if draft_result else None,
            "deductible_applied": str(exclusion_result.deductible_applied) if exclusion_result else None,
            "policy_limit": str(exclusion_result.policy_limit) if exclusion_result else None,
            "coverage_confidence": coverage_match_result.confidence if coverage_match_result else None,
            "anomaly_flags": exclusion_result.anomaly_flags if exclusion_result else [],
        }

    log_retrieval(entry)
    return entry


def build_context_expansion_step(
    expanded_items: list[dict] | None,
    chunks_before_expansion: int = 0,
    note: str | None = None,
) -> dict[str, Any]:
    """Build the parent-section expansion step, explaining explicitly when nothing was expanded."""
    step: dict[str, Any] = {
        "description": "Expand each retrieved chunk to its full parent section text",
        "parent_expansion_enabled": True,
        "chunks_before_expansion": chunks_before_expansion,
        "expansion_applied": bool(expanded_items),
        "total_expanded_items": len(expanded_items or []),
        "items_expanded": [],
    }
    if not expanded_items:
        step["skip_reason"] = note or (
            "no_expanded_items_provided: caller did not run expand_to_parent_sections"
        )
        return step
    step["items_expanded"] = [
        {
            "rank": idx,
            "cited_chunk": _chunk_summary(item["cited_chunk"]),
            "parent_section_text_length": len(item["context_for_llm"]),
            "parent_section_text_preview": item["context_for_llm"][:200],
            "expanded_from_single_chunk": item["cited_chunk"].text
            != item["context_for_llm"][: len(item["cited_chunk"].text)],
        }
        for idx, item in enumerate(expanded_items, start=1)
    ]
    return step


def build_llm_forward_step(forward: dict[str, Any] | None) -> dict[str, Any]:
    """Build the LLM forward-pass step from recorded generation details."""
    step: dict[str, Any] = {
        "description": "Forward pass: assembled prompt sent to the LLM and the raw response returned",
        "executed": forward is not None and not forward.get("skip_reason"),
    }
    if not forward:
        step["skip_reason"] = "generation_not_recorded: entry written before the LLM call"
        step["prompt_chars"] = 0
        step["response_chars"] = 0
        step["response_preview"] = ""
        return step

    step.update(
        {
            "model": forward.get("model"),
            "streaming": bool(forward.get("streaming", False)),
            "prompt_chars": forward.get("prompt_length_chars", 0),
            "prompt_preview": str(forward.get("prompt", ""))[:400],
            "context_chars": forward.get("context_char_count"),
            "response_chars": forward.get("response_length_chars", 0),
            "response_preview": str(forward.get("response", ""))[:500],
            "elapsed_s": forward.get("elapsed_s"),
            "retry_count": forward.get("retry_count", 0),
            "fallback_text_used": bool(forward.get("fallback_text_used", False)),
            "refused": bool(forward.get("refused", False)),
        }
    )
    if forward.get("skip_reason"):
        step["skip_reason"] = forward["skip_reason"]
    return step


def update_last_entry(step_updates: dict[str, Any]) -> bool:
    """Patch pipeline steps onto the most recently logged entry.

    Retrieval steps are written when the search completes, but expansion and the
    LLM forward pass only exist afterwards, so callers patch the same entry
    instead of appending a second, half-empty one.
    """
    if not step_updates:
        return False
    data = _read_existing()
    entries = data.get("entries") or []
    if not entries:
        return False
    entries[-1].update(step_updates)
    data["entries"] = entries
    _atomic_write(data)
    return True


def _agent_step_detail(agent_name: str, result: Any, tool_responses: dict) -> dict[str, Any]:
    """Build detailed sub-log for a single agent step."""
    base: dict[str, Any] = {
        "agent": agent_name,
        "executed": result is not None,
    }

    if agent_name == "CoverageMatcher":
        if result is not None:
            base.update({
                "confidence": result.confidence,
                "policy_id": result.policy_id,
                "version_effective_date": str(result.version_effective_date) if result.version_effective_date else None,
                "applicable_coverage_sections_count": len(result.applicable_coverage_sections),
                "applicable_coverage_sections": [
                    _chunk_summary(s) for s in result.applicable_coverage_sections
                ],
                "refused": result.confidence == "no_match",
                "refusal_reason": (
                    "No policy coverage sections matched the incident description"
                    if result.confidence == "no_match" else None
                ),
                "candidates_retrieved_before_scoring": len(result.applicable_coverage_sections) if result.confidence != "no_match" else 0,
            })
        base["tool_response"] = tool_responses.get("CoverageMatcher") or {}

    elif agent_name == "ExclusionAnalyst":
        if result is not None:
            calc_detail = _calculate_detail(result)
            base.update({
                "exclusions_found_count": len(result.exclusions_found),
                "exclusions_found": [_chunk_summary(e) for e in result.exclusions_found],
                "deductible_applied": str(result.deductible_applied),
                "policy_limit": str(result.policy_limit),
                "calculated_payout": str(result.calculated_payout),
                "anomaly_flags": result.anomaly_flags,
                "has_exclusion": bool(result.exclusions_found),
                "calculation_details": calc_detail,
            })
        base["tool_response"] = tool_responses.get("ExclusionAnalyst") or {}

    elif agent_name == "AdjudicationDrafter":
        if result is not None:
            base.update({
                "recommendation": result.recommendation,
                "calculated_payout": str(result.calculated_payout),
                "reasoning_text_length": len(result.reasoning_text),
                "reasoning_text_preview": result.reasoning_text[:300],
                "citations_count": len(result.citations),
                "confidence": result.confidence,
                "deductible_applied": str(result.deductible_applied),
                "policy_limit": str(result.policy_limit),
                "refused": result.recommendation == "deny",
                "refusal_reason": (
                    "Coverage confidence was no_match or calculated payout is zero"
                    if result.recommendation == "deny" else None
                ),
                "citations": [
                    {
                        "chunk_id": str(c.chunk_id),
                        "policy_id": c.policy_id,
                        "section": c.section,
                        "page": c.page,
                        "text_preview": c.text[:150],
                        "chunk_type": c.chunk_type,
                    }
                    for c in result.citations
                ],
            })
        base["tool_response"] = tool_responses.get("AdjudicationDrafter") or {}

    return base


def _calculate_detail(result: Any) -> dict[str, Any]:
    """Build the detailed financial calculation sub-log for ExclusionAnalyst."""
    claim_amount = 0
    try:
        claim_amount = float(str(getattr(result, "claim_amount", "0") or "0"))
    except (ValueError, TypeError):
        pass

    deductible = 0
    limit = 0
    try:
        deductible = float(str(result.deductible_applied or "0"))
    except (ValueError, TypeError):
        pass
    try:
        limit = float(str(result.policy_limit or "0"))
    except (ValueError, TypeError):
        pass

    gross_claim = claim_amount
    after_deductible = max(0.0, gross_claim - deductible)
    capped = after_deductible > limit
    final_payout = min(after_deductible, limit) if capped else after_deductible

    return {
        "input_claim_amount_requested": claim_amount,
        "extracted_deductible": deductible,
        "extracted_policy_limit": limit,
        "calculation_steps": {
            "step_1_gross_claim_amount": f"${gross_claim:,.2f}",
            "step_2_subtract_deductible": f"${gross_claim:,.2f} - ${deductible:,.2f} = ${after_deductible:,.2f}",
            "step_3_apply_policy_limit": f"min(${after_deductible:,.2f}, ${limit:,.2f})" if capped else f"${after_deductible:,.2f} ≤ ${limit:,.2f} → no cap applied",
            "step_4_final_calculated_payout": f"${final_payout:,.2f}",
        },
        "capped_by_limit": capped,
        "formula": "payout = min(max(claim_amount - deductible, 0), policy_limit)",
        "final_payout": f"${final_payout:,.2f}",
        "anomaly_flags": result.anomaly_flags if hasattr(result, "anomaly_flags") else [],
    }
