import asyncio
import logging
import src.api.deps as _deps
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.api.deps import build_provider_router, get_session_factory
from src.application.contracts.adjudication_draft import AdjudicationDraft
from src.application.use_cases.run_adjudication import RunAdjudicationWorkflowUseCase
from src.domain.entities.claim import Claim
from src.infrastructure.db.repositories.claim_repository import (
    SqlAlchemyClaimRepository,
)
from src.infrastructure.tasks.celery_app import celery_app
from src.infrastructure.observability.claim_logger import append_claim_log
from src.infrastructure.observability.system_logger import emit_system_log
from src.infrastructure.vectorstore.pgvector_store import PgVectorStore

logger = logging.getLogger(__name__)


def apply_draft_to_claim(claim: Claim, draft: AdjudicationDraft) -> None:
    """Persist the adjudication report onto the durable claim record.

    ``recommendation`` holds the machine decision (approve/partial/deny) and
    ``reasoning_text`` holds the human-readable justification — the corp UI shows
    them in different columns, so a justification must never land in
    ``recommendation`` (and vice versa).
    """
    claim.calculated_payout = draft.calculated_payout
    claim.deductible_applied = draft.deductible_applied
    claim.policy_limit = draft.policy_limit
    claim.recommendation = str(draft.recommendation)
    claim.reasoning_text = draft.reasoning_text
    claim.citations = [c.model_dump(mode="json") for c in draft.citations] or None
    claim.status = "report_ready"
    claim.pipeline_stage = "done"
    claim.updated_at = datetime.now(timezone.utc)


@celery_app.task(name="process_claim_adjudication", bind=True)
def process_claim_adjudication(self: Any, claim_data: dict[str, Any]) -> dict[str, Any]:
    """Celery background task executing claim adjudication workflow asynchronously.

    The workflow persists every status transition and the final payout report to
    PostgreSQL through ``SqlAlchemyClaimRepository``, so a client polling
    ``GET /claims/{id}`` receives live state regardless of which process runs it.
    """

    async def _run() -> dict[str, Any]:
        _deps._async_session_factory = None
        emit_system_log(
            "adjudication",
            "claim_task_started",
            {"claim_id": claim_data.get("id"), "task_id": self.request.id},
        )

        llm_provider = build_provider_router()
        session_factory = get_session_factory()

        async with session_factory() as session:
            claim_repo = SqlAlchemyClaimRepository(session=session)

            # Load the durable claim row so ownership, celery_task_id and any
            # prior fields survive the round-trip through the Celery payload.
            claim = await claim_repo.get_by_id(UUID(claim_data["id"]))
            if claim is None:
                claim = Claim(**claim_data)

            correlation_id = claim.correlation_id or (
                UUID(self.request.id) if self.request.id else claim.id
            )

            claim.correlation_id = correlation_id
            claim.celery_task_id = self.request.id
            claim.status = "processing"
            claim.pipeline_stage = "understanding"
            claim.updated_at = datetime.now(timezone.utc)
            await claim_repo.save(claim)

            vector_store = PgVectorStore(session=session)
            use_case = RunAdjudicationWorkflowUseCase(
                llm_provider=llm_provider,
                vector_store=vector_store,
                claim_repo=claim_repo,
            )
            try:
                draft = await use_case.execute(claim=claim, correlation_id=correlation_id)
            except Exception as exc:
                claim.status = "failed"
                claim.error_message = str(exc)
                claim.updated_at = datetime.now(timezone.utc)
                async with session_factory() as fresh_session:
                    await SqlAlchemyClaimRepository(session=fresh_session).save(claim)
                emit_system_log(
                    "adjudication",
                    "claim_task_failed",
                    {
                        "claim_id": str(claim.id),
                        "error": str(exc),
                        "correlation_id": str(correlation_id),
                    },
                    correlation_id=correlation_id,
                )
                try:
                    append_claim_log(
                        {
                            "claim_id": str(claim.id),
                            "correlation_id": str(correlation_id),
                            "submitted_at": claim.created_at.isoformat() if claim.created_at else None,
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "status": "failed",
                            "error_message": str(exc),
                            "policy_number": claim.policy_number,
                            "date_of_loss": claim.date_of_loss.isoformat(),
                            "incident_description": claim.incident_description,
                            "claim_amount_requested": str(claim.claim_amount_requested),
                            "coverage_match": None,
                            "exclusion_analysis": None,
                            "draft": None,
                        }
                    )
                except Exception:
                    pass
                raise

            # Persist the adjudication report onto the durable claim record.
            apply_draft_to_claim(claim, draft)
            # Hold for human review: client must submit, then adjuster decides.
            await claim_repo.save(claim)

        updated_claim = claim
        emit_system_log(
            "adjudication",
            "claim_task_finished",
            {
                "claim_id": str(claim.id),
                "correlation_id": str(correlation_id),
                "status": updated_claim.status,
                "recommendation": str(draft.recommendation),
                "calculated_payout": str(draft.calculated_payout),
            },
        )
        return {
            "status": "success",
            "claim_id": str(claim.id),
            "correlation_id": str(correlation_id),
            "recommendation": draft.recommendation,
            "calculated_payout": str(draft.calculated_payout),
            "reasoning_text": draft.reasoning_text,
            "final_claim_status": updated_claim.status,
        }

    return asyncio.run(_run())