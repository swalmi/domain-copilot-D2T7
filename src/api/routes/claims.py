from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import UserPayload, get_claim_repository, get_current_user
from src.domain.entities.claim import Claim
from src.domain.interfaces.claim_repository import ClaimRepository
from src.infrastructure.tasks.claim_tasks import process_claim_adjudication

router = APIRouter(prefix="/claims", tags=["Claims"])


class CreateClaimRequest(BaseModel):
    """Payload schema for submitting a new insurance claim."""

    policy_number: str
    date_of_loss: date
    incident_description: str
    claim_amount_requested: Decimal = Field(..., gt=Decimal("0.00"))


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
