import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.agents.adjudication_drafter import AdjudicationDrafter
from src.application.agents.coverage_matcher import CoverageMatcher
from src.application.agents.decision_text import ensure_decision_text
from src.application.agents.exclusion_analyst import ExclusionAnalyst
from src.application.contracts.adjudication_draft import AdjudicationDraft
from src.application.contracts.coverage_match_result import CoverageMatchResult
from src.application.contracts.exclusion_analysis_result import ExclusionAnalysisResult
from src.application.use_cases.ask_question import AskQuestionUseCase
from src.domain.entities.claim import Claim
from src.domain.interfaces.claim_repository import ClaimRepository
from src.domain.interfaces.llm_provider import LLMProvider
from src.domain.interfaces.vector_store import VectorStore
from src.infrastructure.observability.claim_logger import append_claim_log
from src.infrastructure.observability.pause_registry import wait_if_paused
from src.infrastructure.observability.retrieval_logger import create_retrieval_log
from src.infrastructure.observability.system_logger import emit_system_log
from src.infrastructure.observability.trace_logger import traced_step

logger = logging.getLogger(__name__)


class RunAdjudicationWorkflowUseCase:
    """Pipeline orchestrator for executing claim adjudication agent workflows with resilience safeguards."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        vector_store: VectorStore,
        claim_repo: ClaimRepository,
    ) -> None:
        """Initialize orchestrator with dependencies and iteration circuit breaker."""
        self._llm_provider = llm_provider
        self._vector_store = vector_store
        self._claim_repo = claim_repo
        self._active_runs: set[UUID] = set()

    async def _execute_with_retry(self, coro_func, timeout_seconds: float = 180.0):
        """Helper executing coroutine with timeout and 1-time exponential backoff retry."""
        try:
            return await asyncio.wait_for(coro_func(), timeout=timeout_seconds)
        except Exception as exc:
            logger.warning(f"Step execution failed: {exc}. Retrying in 2 seconds...")
            await asyncio.sleep(2.0)
            return await asyncio.wait_for(coro_func(), timeout=timeout_seconds)

    @traced_step("RunAdjudicationWorkflow")
    async def execute(self, claim: Claim, correlation_id: UUID) -> AdjudicationDraft:
        """Execute linear claim adjudication pipeline (Coverage -> Exclusion -> Drafter)."""
        emit_system_log(
            "adjudication",
            "workflow_started",
            {"claim_id": str(claim.id), "incident": claim.incident_description},
            correlation_id=correlation_id,
        )
        # 5. Circuit Breaker: Max iteration check per claim run
        if claim.id in self._active_runs:
            raise RuntimeError(
                f"Max iteration limit exceeded for claim workflow (Claim ID: {claim.id})"
            )

        self._active_runs.add(claim.id)
        coverage_match: CoverageMatchResult | None = None
        exclusion_result: ExclusionAnalysisResult | None = None
        draft: AdjudicationDraft | None = None
        tool_responses: dict[str, list[dict[str, Any]]] = {}

        def on_progress(info: dict[str, Any]) -> None:
            emit_system_log(
                "adjudication",
                "agent_progress",
                info,
                correlation_id=correlation_id,
            )

        def _log_claim(status: str, error_message: str | None = None) -> None:
            try:
                append_claim_log(
                    {
                        "claim_id": str(claim.id),
                        "correlation_id": str(correlation_id),
                        "submitted_at": claim.created_at.isoformat() if claim.created_at else None,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "status": status,
                        "error_message": error_message,
                        "policy_number": claim.policy_number,
                        "date_of_loss": claim.date_of_loss.isoformat(),
                        "incident_description": claim.incident_description,
                        "claim_amount_requested": str(claim.claim_amount_requested),
                        "coverage_match": {
                            "policy_id": coverage_match.policy_id if coverage_match else None,
                            "confidence": coverage_match.confidence if coverage_match else None,
                            "applicable_coverage_sections": [
                                s.model_dump(mode="json") for s in (coverage_match.applicable_coverage_sections if coverage_match else [])
                            ],
                        } if coverage_match else None,
                        "exclusion_analysis": {
                            "exclusions_found": [
                                e.model_dump(mode="json") for e in (exclusion_result.exclusions_found if exclusion_result else [])
                            ],
                            "deductible_applied": str(exclusion_result.deductible_applied) if exclusion_result else None,
                            "policy_limit": str(exclusion_result.policy_limit) if exclusion_result else None,
                            "calculated_payout": str(exclusion_result.calculated_payout) if exclusion_result else None,
                            "anomaly_flags": exclusion_result.anomaly_flags if exclusion_result else [],
                        } if exclusion_result else None,
                        "draft": draft.model_dump(mode="json") if draft else None,
                    }
                )
            except Exception:
                pass

        try:
            # 1. Coverage Matcher Step
            claim.pipeline_stage = "reading_policy"
            await self._claim_repo.save(claim)
            try:
                matcher = CoverageMatcher(llm_provider=self._llm_provider, on_progress=on_progress)
                coverage_match = await self._execute_with_retry(
                    lambda: matcher.run(claim, self._vector_store)
                )
                tool_responses["CoverageMatcher"] = matcher.tool_responses
                claim.pipeline_stage = (
                    "matched" if coverage_match.confidence != "no_match" else "not_matched"
                )
                await self._claim_repo.save(claim)
                emit_system_log(
                    "adjudication",
                    "coverage_matcher_completed",
                    {
                        "claim_id": str(claim.id),
                        "confidence": coverage_match.confidence,
                    },
                    correlation_id=correlation_id,
                )
            except Exception as exc:
                logger.error(f"CoverageMatcher failed completely: {exc}. Activating graceful degradation.")
                emit_system_log(
                    "adjudication",
                    "coverage_matcher_failed_degraded",
                    {"claim_id": str(claim.id), "error": str(exc)},
                    correlation_id=correlation_id,
                )
                ask_use_case = AskQuestionUseCase(
                    llm_provider=self._llm_provider,
                    vector_store=self._vector_store,
                )
                ask_res = await ask_use_case.execute(claim.incident_description)
                create_retrieval_log(
                    coverage_match_result=None,
                    exclusion_result=None,
                    draft_result=None,
                    final_recommendation="deny",
                    query=claim.incident_description,
                    refusal_reason=f"CoverageMatcher failed: {exc}",
                    agent_tool_responses=tool_responses,
                    llm_forward={"skip_reason": "drafter_not_invoked: coverage matcher failed, degraded fallback used"},
                    expansion_note="not_applicable: agent tool retrieval scores chunks directly without parent expansion",
                )
                _log_claim("degraded")
                return AdjudicationDraft(
                    recommendation="deny",
                    calculated_payout=Decimal("0.00"),
                    reasoning_text=ensure_decision_text(
                        f"DEGRADED FALLBACK: {ask_res.get('answer')}",
                        fallback=(
                            "DEGRADED FALLBACK: coverage matching failed and the "
                            "language model did not return a usable justification; "
                            "claim denied pending manual review."
                        ),
                    ),
                    citations=[],
                    confidence="low",
                )

            # 2. No-Match Short-Circuit
            if coverage_match.confidence == "no_match":
                claim.status = "refused"
                await self._claim_repo.save(claim)
                emit_system_log(
                    "adjudication",
                    "refused_no_match",
                    {"claim_id": str(claim.id)},
                    correlation_id=correlation_id,
                )
                create_retrieval_log(
                    coverage_match_result=coverage_match,
                    exclusion_result=None,
                    draft_result=None,
                    final_recommendation="deny",
                    query=claim.incident_description,
                    refusal_reason="No matching policy coverage sections found",
                    agent_tool_responses=tool_responses,
                    llm_forward={"skip_reason": "drafter_not_invoked: coverage confidence was no_match"},
                    expansion_note="not_applicable: agent tool retrieval scores chunks directly without parent expansion",
                )
                _log_claim("refused")
                return AdjudicationDraft(
                    recommendation="deny",
                    calculated_payout=Decimal("0.00"),
                    reasoning_text="Claim refused: No matching policy coverage sections found.",
                    citations=[],
                    confidence="low",
                )

            # 3. Exclusion Analyst Step
            claim.pipeline_stage = "building_report"
            await self._claim_repo.save(claim)
            # Respect pause requests between agent steps
            await wait_if_paused(claim.id)
            analyst = ExclusionAnalyst(llm_provider=self._llm_provider, on_progress=on_progress)
            exclusion_result = await self._execute_with_retry(
                lambda: analyst.run(claim, coverage_match, self._vector_store)
            )
            tool_responses["ExclusionAnalyst"] = analyst.tool_responses
            emit_system_log(
                "adjudication",
                "exclusion_analyst_completed",
                {"claim_id": str(claim.id)},
                correlation_id=correlation_id,
            )

            # 4. Adjudication Drafter Step
            await wait_if_paused(claim.id)
            drafter = AdjudicationDrafter(llm_provider=self._llm_provider, on_progress=on_progress)
            draft = await self._execute_with_retry(
                lambda: drafter.run(claim, coverage_match, exclusion_result, self._claim_repo)
            )
            tool_responses["AdjudicationDrafter"] = drafter.tool_responses
            emit_system_log(
                "adjudication",
                "adjudication_completed",
                {
                    "claim_id": str(claim.id),
                    "recommendation": draft.recommendation,
                    "calculated_payout": str(draft.calculated_payout),
                    "confidence": draft.confidence,
                },
                correlation_id=correlation_id,
            )

            _log_claim("completed")
            create_retrieval_log(
                coverage_match_result=coverage_match,
                exclusion_result=exclusion_result,
                draft_result=draft,
                final_recommendation=draft.recommendation if draft else None,
                query=claim.incident_description,
                refusal_reason=None,
                agent_tool_responses=tool_responses,
                llm_forward=drafter.generation_record or None,
                expansion_note="not_applicable: agent tool retrieval scores chunks directly without parent expansion",
            )
            return draft

        finally:
            self._active_runs.remove(claim.id)
