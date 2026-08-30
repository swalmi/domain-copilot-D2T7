import asyncio
from decimal import Decimal
import logging
from uuid import UUID

from src.application.agents.adjudication_drafter import AdjudicationDrafter
from src.application.agents.coverage_matcher import CoverageMatcher
from src.application.agents.exclusion_analyst import ExclusionAnalyst
from src.application.contracts.adjudication_draft import AdjudicationDraft
from src.application.use_cases.ask_question import AskQuestionUseCase
from src.domain.entities.claim import Claim
from src.domain.interfaces.claim_repository import ClaimRepository
from src.domain.interfaces.llm_provider import LLMProvider
from src.domain.interfaces.vector_store import VectorStore
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

    async def _execute_with_retry(self, coro_func, timeout_seconds: float = 30.0):
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
        # 5. Circuit Breaker: Max iteration check per claim run
        if claim.id in self._active_runs:
            raise RuntimeError(
                f"Max iteration limit exceeded for claim workflow (Claim ID: {claim.id})"
            )

        self._active_runs.add(claim.id)
        try:
            # 1. Coverage Matcher Step
            try:
                matcher = CoverageMatcher(llm_provider=self._llm_provider)
                coverage_match = await self._execute_with_retry(
                    lambda: matcher.run(claim, self._vector_store)
                )
            except Exception as exc:
                logger.error(f"CoverageMatcher failed completely: {exc}. Activating graceful degradation.")
                ask_use_case = AskQuestionUseCase(
                    llm_provider=self._llm_provider,
                    vector_store=self._vector_store,
                )
                ask_res = await ask_use_case.execute(claim.incident_description)
                return AdjudicationDraft(
                    recommendation="deny",
                    calculated_payout=Decimal("0.00"),
                    reasoning_text=f"DEGRADED FALLBACK: {ask_res.get('answer')}",
                    citations=[],
                    confidence="low",
                )

            # 2. No-Match Short-Circuit
            if coverage_match.confidence == "no_match":
                claim.status = "refused"
                await self._claim_repo.save(claim)
                return AdjudicationDraft(
                    recommendation="deny",
                    calculated_payout=Decimal("0.00"),
                    reasoning_text="Claim refused: No matching policy coverage sections found.",
                    citations=[],
                    confidence="low",
                )

            # 3. Exclusion Analyst Step
            analyst = ExclusionAnalyst(llm_provider=self._llm_provider)
            exclusion_result = await self._execute_with_retry(
                lambda: analyst.run(claim, coverage_match, self._vector_store)
            )

            # 4. Adjudication Drafter Step
            drafter = AdjudicationDrafter(llm_provider=self._llm_provider)
            draft = await self._execute_with_retry(
                lambda: drafter.run(claim, coverage_match, exclusion_result, self._claim_repo)
            )

            return draft

        finally:
            self._active_runs.remove(claim.id)
