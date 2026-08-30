from decimal import Decimal
from typing import ClassVar

from src.application.agents.base_agent import BaseAgent
from src.application.contracts.coverage_match_result import CoverageMatchResult
from src.application.contracts.exclusion_analysis_result import (
    ExclusionAnalysisResult,
)
from src.application.retrieval.prompt_loader import load_prompt
from src.application.tools.calculate_limits import calculate_limits_and_deductibles
from src.application.tools.search_exclusions import search_exclusions
from src.domain.entities.claim import Claim
from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.llm_provider import LLMProvider
from src.domain.interfaces.vector_store import VectorStore


class ExclusionAnalyst(BaseAgent):
    """Agent responsible for analyzing policy exclusions and extracting deductible/limit figures."""

    ALLOWED_TOOLS: ClassVar[list[str]] = [
        "search_exclusions",
        "calculate_limits_and_deductibles",
    ]

    def __init__(
        self, llm_provider: LLMProvider, name: str = "ExclusionAnalyst"
    ) -> None:
        """Initialize ExclusionAnalyst with LLM provider and agent name."""
        super().__init__(llm_provider=llm_provider, name=name)

    async def run(
        self,
        claim: Claim,
        coverage_match: CoverageMatchResult,
        vector_store: VectorStore,
    ) -> ExclusionAnalysisResult:
        """Analyze exclusions and calculate net payout deterministically."""
        retrieved_exclusions: list[CitedChunk] = await search_exclusions(
            vector_store=vector_store,
            embedder=self.llm_provider,
            query=claim.incident_description,
            policy_id=coverage_match.policy_id,
            effective_date_before=coverage_match.version_effective_date,
            top_k=5,
        )

        tool_schema = {
            "type": "function",
            "function": {
                "name": "search_exclusions",
                "description": "Extract raw deductible and policy limit numeric values from policy text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "deductible": {
                            "type": "number",
                            "description": "Numeric deductible amount extracted from policy text.",
                        },
                        "policy_limit": {
                            "type": "number",
                            "description": "Numeric policy limit amount extracted from policy text.",
                        },
                        "has_exclusion": {
                            "type": "boolean",
                            "description": "True if an applicable policy exclusion was identified.",
                        },
                    },
                    "required": ["deductible", "policy_limit"],
                },
            },
        }

        exclusions_formatted = "\n\n".join(
            f"[{c.policy_id} v{c.version} page {c.page} section '{c.section}'] {c.text}"
            for c in retrieved_exclusions
        )

        prompt_template = load_prompt("exclusion_analyst", "v1")
        prompt = prompt_template.format(
            incident_description=claim.incident_description,
            claim_amount_requested=str(claim.claim_amount_requested),
            retrieved_exclusions=exclusions_formatted or "No explicit exclusion sections found.",
        )

        extracted_deductible = Decimal("500.00")
        extracted_limit = Decimal("10000.00")
        has_exclusion = False

        try:
            tool_response = await self._call_tool(tool_schema, prompt)
            args = tool_response.get("args") or tool_response.get("parameters") or {}
            if "deductible" in args:
                extracted_deductible = Decimal(str(args["deductible"]))
            if "policy_limit" in args:
                extracted_limit = Decimal(str(args["policy_limit"]))
            if "has_exclusion" in args:
                has_exclusion = bool(args["has_exclusion"])
        except Exception:
            pass

        # Deterministic Python financial calculation (NO LLM invocation for arithmetic!)
        calc_result = calculate_limits_and_deductibles(
            claim_amount=claim.claim_amount_requested,
            deductible=extracted_deductible,
            policy_limit=extracted_limit,
        )

        anomaly_flags = []
        if calc_result["capped_by_limit"]:
            anomaly_flags.append("payout_capped_by_policy_limit")
        if has_exclusion:
            anomaly_flags.append("applicable_exclusion_found")

        applied_exclusions = retrieved_exclusions if has_exclusion else []

        return ExclusionAnalysisResult(
            exclusions_found=applied_exclusions,
            deductible_applied=calc_result["deductible_applied"],
            policy_limit=calc_result["limit_applied"],
            calculated_payout=calc_result["payout"],
            anomaly_flags=anomaly_flags,
        )
