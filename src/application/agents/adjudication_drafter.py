import asyncio
import threading
import time
from collections.abc import Callable
from typing import ClassVar

from src.application.agents.base_agent import BaseAgent
from src.application.agents.decision_text import (
    ensure_decision_text,
    looks_like_model_refusal,
)
from src.application.contracts.adjudication_draft import AdjudicationDraft
from src.application.contracts.coverage_match_result import CoverageMatchResult
from src.application.contracts.exclusion_analysis_result import (
    ExclusionAnalysisResult,
)
from src.application.retrieval.prompt_loader import load_prompt
from src.application.tools.submit_for_approval import submit_for_approval
from src.domain.entities.claim import Claim
from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.claim_repository import ClaimRepository
from src.domain.interfaces.llm_provider import LLMProvider


def _structured_reasoning(
    claim: Claim,
    coverage_match: CoverageMatchResult,
    exclusion_result: ExclusionAnalysisResult,
    recommendation: str,
) -> str:
    """Deterministic justification built from structured facts.

    Used when the language model does not produce usable text, so the corp UI
    never shows a refusal string as the AI decision.
    """
    return (
        "Automated decision summary (the language model did not return a usable "
        f"justification): coverage match '{coverage_match.confidence}' for policy "
        f"{claim.policy_number}; requested {claim.claim_amount_requested}; calculated "
        f"payout {exclusion_result.calculated_payout} after deductible "
        f"{exclusion_result.deductible_applied}; policy limit "
        f"{exclusion_result.policy_limit}; recommendation {recommendation}."
    )


class AdjudicationDrafter(BaseAgent):
    """Agent responsible for composing adjudication recommendation drafts and invoking gated submit_for_approval."""

    ALLOWED_TOOLS: ClassVar[list[str]] = ["submit_for_approval"]

    def __init__(
        self, llm_provider: LLMProvider, name: str = "AdjudicationDrafter", on_progress: Callable[[dict], None] | None = None
    ) -> None:
        """Initialize AdjudicationDrafter with LLM provider and agent name."""
        super().__init__(llm_provider=llm_provider, name=name, on_progress=on_progress)
        self.generation_record: dict = {}

    async def run(
        self,
        claim: Claim,
        coverage_match: CoverageMatchResult,
        exclusion_result: ExclusionAnalysisResult,
        claim_repo: ClaimRepository | None = None,
    ) -> AdjudicationDraft:
        """Compose adjudication recommendation draft and submit for approval."""
        prompt_template = load_prompt("adjudication_drafter", "v1")
        prompt = prompt_template.format(
            policy_number=claim.policy_number,
            incident_description=claim.incident_description,
            claim_amount_requested=str(claim.claim_amount_requested),
            calculated_payout=str(exclusion_result.calculated_payout),
            deductible_applied=str(exclusion_result.deductible_applied),
            policy_limit=str(exclusion_result.policy_limit),
            coverage_confidence=coverage_match.confidence,
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
                                "stage": "llm_complete",
                                "elapsed_s": round(time.monotonic() - start, 1),
                                "detail": "LLM generation in flight…",
                            }
                        )

            beat_task = asyncio.create_task(_beat())
        try:
            reasoning = await self.llm_provider.complete(prompt)
            retry_count = 0
            if looks_like_model_refusal(reasoning):
                # Small models sometimes answer with a refusal/apology. Ask once
                # more with an explicit instruction, then fall back to a
                # deterministic summary of the structured facts below.
                retry_prompt = (
                    prompt
                    + "\n\nREMINDER: reply with ONLY the reasoning paragraph in the "
                    "example's style. Do not apologise, refuse, or comment on what "
                    "you can or cannot do."
                )
                reasoning = await self.llm_provider.complete(retry_prompt)
                retry_count = 1
        finally:
            done.set()
            if beat_task is not None:
                beat_task.cancel()
                try:
                    await beat_task
                except asyncio.CancelledError:
                    pass

        raw_reasoning = reasoning
        elapsed_s = round(time.monotonic() - start, 3)

        if coverage_match.confidence == "no_match" or exclusion_result.calculated_payout == 0:
            recommendation = "deny"
        elif exclusion_result.calculated_payout < claim.claim_amount_requested:
            recommendation = "partial"
        else:
            recommendation = "approve"

        reasoning_text = ensure_decision_text(
            reasoning,
            fallback=_structured_reasoning(
                claim=claim,
                coverage_match=coverage_match,
                exclusion_result=exclusion_result,
                recommendation=recommendation,
            ),
        )

        model_name = str(
            getattr(self.llm_provider, "model", None)
            or getattr(self.llm_provider, "model_name", None)
            or type(self.llm_provider).__name__
        )
        self.generation_record = {
            "model": model_name,
            "streaming": False,
            "prompt": prompt,
            "prompt_length_chars": len(prompt),
            "response": raw_reasoning,
            "response_length_chars": len(raw_reasoning),
            "elapsed_s": elapsed_s,
            "retry_count": retry_count,
            "fallback_text_used": reasoning_text != raw_reasoning,
        }
        self.tool_responses.append(
            {
                "tool_name": "llm_complete",
                "prompt_length_chars": len(prompt),
                "prompt": prompt,
                "elapsed_s": elapsed_s,
                "retry_count": retry_count,
                "response": {
                    "raw_reasoning": raw_reasoning,
                    "final_reasoning_text": reasoning_text,
                    "fallback_text_used": reasoning_text != raw_reasoning,
                },
            }
        )

        citations: list[CitedChunk] = (
            coverage_match.applicable_coverage_sections
            + exclusion_result.exclusions_found
        )

        confidence_rating = "high" if coverage_match.confidence == "matched" else "medium"

        draft = AdjudicationDraft(
            recommendation=recommendation,  # type: ignore[arg-type]
            calculated_payout=exclusion_result.calculated_payout,
            reasoning_text=reasoning_text,
            citations=citations,
            confidence=confidence_rating,  # type: ignore[arg-type]
            deductible_applied=exclusion_result.deductible_applied,
            policy_limit=exclusion_result.policy_limit,
        )

        if claim_repo is not None:
            await submit_for_approval(draft, claim.id, claim_repo)

        return draft
