from datetime import date
from typing import ClassVar

from src.application.agents.base_agent import BaseAgent
from src.application.contracts.coverage_match_result import CoverageMatchResult
from src.application.retrieval.prompt_loader import load_prompt
from src.application.tools.search_policies import search_policies
from src.domain.entities.claim import Claim
from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.llm_provider import LLMProvider
from src.domain.interfaces.vector_store import VectorStore


class CoverageMatcher(BaseAgent):
    """Agent responsible for matching submitted claims to policy coverage sections."""

    ALLOWED_TOOLS: ClassVar[list[str]] = ["search_policies"]

    def __init__(
        self, llm_provider: LLMProvider, name: str = "CoverageMatcher"
    ) -> None:
        """Initialize CoverageMatcher with LLM provider and agent name."""
        super().__init__(llm_provider=llm_provider, name=name)

    async def run(
        self, claim: Claim, vector_store: VectorStore
    ) -> CoverageMatchResult:
        """Run coverage matching against vector store policy sections for a given claim."""
        candidates: list[CitedChunk] = await search_policies(
            vector_store=vector_store,
            embedder=self.llm_provider,
            query=claim.incident_description,
            policy_id=claim.policy_number,
            effective_date_before=claim.date_of_loss,
            top_k=5,
        )

        if not candidates:
            return CoverageMatchResult(
                policy_id=claim.policy_number,
                version_effective_date=claim.date_of_loss,
                applicable_coverage_sections=[],
                confidence="no_match",
            )

        top_candidate = candidates[0]

        tool_schema = {
            "type": "function",
            "function": {
                "name": "search_policies",
                "description": "Select matching policy coverage section and output confidence evaluation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "confidence": {
                            "type": "string",
                            "enum": ["matched", "no_match", "ambiguous"],
                            "description": "Confidence of coverage match.",
                        },
                    },
                    "required": ["confidence"],
                },
            },
        }

        sections_formatted = "\n\n".join(
            f"[{c.policy_id} v{c.version} page {c.page} section '{c.section}'] {c.text}"
            for c in candidates
        )

        prompt_template = load_prompt("coverage_matcher", "v1")
        prompt = prompt_template.format(
            policy_number=claim.policy_number,
            date_of_loss=claim.date_of_loss.isoformat(),
            incident_description=claim.incident_description,
            retrieved_sections=sections_formatted,
        )

        try:
            tool_response = await self._call_tool(tool_schema, prompt)
            args = tool_response.get("args") or tool_response.get("parameters") or {}
            confidence_val = args.get("confidence", "matched")
        except Exception:
            confidence_val = "matched"

        if confidence_val not in ["matched", "no_match", "ambiguous"]:
            confidence_val = "matched"

        return CoverageMatchResult(
            policy_id=top_candidate.policy_id,
            version_effective_date=top_candidate.effective_date,
            applicable_coverage_sections=candidates if confidence_val != "no_match" else [],
            confidence=confidence_val,  # type: ignore[arg-type]
        )
