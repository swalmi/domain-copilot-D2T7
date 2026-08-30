from datetime import date
from decimal import Decimal
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import UserPayload, get_claim_repository, get_current_user
from src.domain.entities.claim import Claim
from src.domain.interfaces.claim_repository import ClaimRepository
from src.infrastructure.tasks.celery_app import celery_app
from src.infrastructure.tasks.claim_tasks import process_claim_adjudication

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["Claims"])

# Map claim_id to task_id for Celery task revocation
_claim_task_map: dict[UUID, str] = {}


class CreateClaimRequest(BaseModel):
    """Payload schema for submitting a new insurance claim with unbounded consumption limits."""

    policy_number: str = Field(..., max_length=100)
    date_of_loss: date
    incident_description: str = Field(..., max_length=10000)
    claim_amount_requested: Decimal = Field(..., gt=Decimal("0.00"), le=Decimal("10000000.00"))



@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_claim(
    payload: CreateClaimRequest,
    current_user: UserPayload = Depends(get_current_user),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Submit a new insurance claim for asynchronous processing via Celery worker."""
    claim_id = uuid4()
    claim = Claim(
        id=claim_id,
        policy_number=payload.policy_number,
        date_of_loss=payload.date_of_loss,
        incident_description=payload.incident_description,
        claim_amount_requested=payload.claim_amount_requested,
        status="submitted",
    )
    await claim_repo.save(claim)

    claim_dict = {
        "id": str(claim.id),
        "policy_number": claim.policy_number,
        "date_of_loss": str(claim.date_of_loss),
        "incident_description": claim.incident_description,
        "claim_amount_requested": str(claim.claim_amount_requested),
        "status": claim.status,
    }

    task = process_claim_adjudication.delay(claim_dict)
    _claim_task_map[claim_id] = task.id

    return {
        "claim_id": str(claim_id),
        "task_id": task.id,
        "status": "pending",
    }


@router.get("/{claim_id}", status_code=status.HTTP_200_OK)
async def get_claim_status(
    claim_id: UUID,
    current_user: UserPayload = Depends(get_current_user),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Retrieve full current claim record by ID including status and details."""
    claim = await claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    return {
        "id": str(claim.id),
        "policy_number": claim.policy_number,
        "date_of_loss": str(claim.date_of_loss),
        "incident_description": claim.incident_description,
        "claim_amount_requested": str(claim.claim_amount_requested),
        "status": claim.status,
    }


@router.post("/{claim_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_claim(
    claim_id: UUID,
    current_user: UserPayload = Depends(get_current_user),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Cancel an active claim and revoke its background Celery task."""
    claim = await claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )

    task_id = _claim_task_map.get(claim_id)
    if task_id:
        try:
            celery_app.control.revoke(task_id, terminate=True)
            logger.info(f"[AUDIT TRAIL] Revoked Celery task {task_id} for claim {claim_id}")
        except Exception as exc:
            logger.warning(f"Failed to revoke Celery task {task_id}: {exc}")

    old_status = claim.status
    claim.status = "cancelled"
    await claim_repo.save(claim)

    logger.info(
        f"[AUDIT TRAIL] User {current_user.email} CANCELLED claim {claim_id} (Status: {old_status} -> cancelled)"
    )

    return {
        "status": "success",
        "claim_id": str(claim.id),
        "task_id": task_id,
        "claim_status": "cancelled",
        "message": "Claim cancelled and Celery task revoked.",
    }
