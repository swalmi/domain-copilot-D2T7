from typing import ClassVar

from src.application.agents.base_agent import BaseAgent
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


class AdjudicationDrafter(BaseAgent):
    """Agent responsible for composing adjudication recommendation drafts and invoking gated submit_for_approval."""

    ALLOWED_TOOLS: ClassVar[list[str]] = ["submit_for_approval"]

    def __init__(
        self, llm_provider: LLMProvider, name: str = "AdjudicationDrafter"
    ) -> None:
        """Initialize AdjudicationDrafter with LLM provider and agent name."""
        super().__init__(llm_provider=llm_provider, name=name)

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

        reasoning = await self.llm_provider.complete(prompt)

        if coverage_match.confidence == "no_match" or exclusion_result.calculated_payout == 0:
            recommendation = "deny"
        elif exclusion_result.calculated_payout < claim.claim_amount_requested:
            recommendation = "partial"
        else:
            recommendation = "approve"

        citations: list[CitedChunk] = (
            coverage_match.applicable_coverage_sections
            + exclusion_result.exclusions_found
        )

        confidence_rating = "high" if coverage_match.confidence == "matched" else "medium"

        draft = AdjudicationDraft(
            recommendation=recommendation,  # type: ignore[arg-type]
            calculated_payout=exclusion_result.calculated_payout,
            reasoning_text=reasoning,
            citations=citations,
            confidence=confidence_rating,  # type: ignore[arg-type]
        )

        if claim_repo is not None:
            await submit_for_approval(draft, claim.id, claim_repo)

        return draft
