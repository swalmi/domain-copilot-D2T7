import asyncio
import logging
from typing import Any
from uuid import UUID

from src.api.deps import (
    get_claim_repository,
    get_run_adjudication_use_case,
)
from src.domain.entities.claim import Claim
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="process_claim_adjudication", bind=True)
def process_claim_adjudication(self: Any, claim_data: dict[str, Any]) -> dict[str, Any]:
    """Celery background task executing claim adjudication workflow asynchronously."""

    async def _run() -> dict[str, Any]:
        claim = Claim(**claim_data)

        # Wire dependencies using DI container
        claim_repo = get_claim_repository()
        use_case = get_run_adjudication_use_case()

        claim.status = "processing"
        await claim_repo.save(claim)

        correlation_id = UUID(self.request.id) if self.request.id else claim.id

        draft = await use_case.execute(claim=claim, correlation_id=correlation_id)

        # Fetch updated claim state
        updated_claim = await claim_repo.get_by_id(claim.id)
        return {
            "status": "success",
            "claim_id": str(claim.id),
            "recommendation": draft.recommendation,
            "calculated_payout": str(draft.calculated_payout),
            "reasoning_text": draft.reasoning_text,
            "final_claim_status": updated_claim.status if updated_claim else claim.status,
        }

    return asyncio.run(_run())
