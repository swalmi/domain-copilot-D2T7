from decimal import Decimal
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import UserPayload, get_claim_repository, require_role
from src.domain.interfaces.claim_repository import ClaimRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class EditAndApproveRequest(BaseModel):
    """Payload schema for editing payout and notes before manual approval."""

    adjusted_payout: Decimal = Field(..., ge=Decimal("0.00"))
    adjuster_notes: str


@router.get("", status_code=status.HTTP_200_OK)
async def list_pending_approvals(
    current_user: UserPayload = Depends(require_role("corp")),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> list[dict[str, Any]]:
    """Return all pending claim decisions requiring manual adjuster review."""
    claims = await claim_repo.list_pending_approvals()
    return [
        {
            "id": str(c.id),
            "policy_number": c.policy_number,
            "date_of_loss": str(c.date_of_loss),
            "incident_description": c.incident_description,
            "claim_amount_requested": str(c.claim_amount_requested),
            "status": c.status,
        }
        for c in claims
    ]


@router.post("/{claim_id}/approve", status_code=status.HTTP_200_OK)
async def approve_claim(
    claim_id: UUID,
    current_user: UserPayload = Depends(require_role("corp")),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Approve a claim decision (Strictly restricted to adjuster role)."""
    claim = await claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )

    old_status = claim.status
    claim.status = "approved"
    await claim_repo.save(claim)

    logger.info(
        f"[AUDIT TRAIL] Adjuster {current_user.email} APPROVED claim {claim_id} (Status: {old_status} -> approved)"
    )
    return {
        "status": "success",
        "claim_id": str(claim.id),
        "decision": "approved",
        "approved_by": current_user.email,
    }


@router.post("/{claim_id}/reject", status_code=status.HTTP_200_OK)
async def reject_claim(
    claim_id: UUID,
    current_user: UserPayload = Depends(require_role("corp")),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Reject a claim decision (Strictly restricted to adjuster role)."""
    claim = await claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )

    old_status = claim.status
    claim.status = "rejected"
    await claim_repo.save(claim)

    logger.info(
        f"[AUDIT TRAIL] Adjuster {current_user.email} REJECTED claim {claim_id} (Status: {old_status} -> rejected)"
    )
    return {
        "status": "success",
        "claim_id": str(claim.id),
        "decision": "rejected",
        "rejected_by": current_user.email,
    }


@router.post("/{claim_id}/edit-and-approve", status_code=status.HTTP_200_OK)
async def edit_and_approve_claim(
    claim_id: UUID,
    payload: EditAndApproveRequest,
    current_user: UserPayload = Depends(require_role("corp")),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Edit claim payout/notes and approve (Strictly restricted to adjuster role)."""
    claim = await claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )

    old_status = claim.status
    claim.status = "approved"
    await claim_repo.save(claim)

    logger.info(
        f"[AUDIT TRAIL] Adjuster {current_user.email} EDITED & APPROVED claim {claim_id} "
        f"with payout {payload.adjusted_payout} (Notes: {payload.adjuster_notes}) "
        f"(Status: {old_status} -> approved)"
    )
    return {
        "status": "success",
        "claim_id": str(claim.id),
        "decision": "approved",
        "adjusted_payout": str(payload.adjusted_payout),
        "adjuster_notes": payload.adjuster_notes,
        "approved_by": current_user.email,
    }
