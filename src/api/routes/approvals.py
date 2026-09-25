from decimal import Decimal
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import UserPayload, get_claim_repository, require_role
from src.domain.interfaces.claim_repository import ClaimRepository
from src.infrastructure.observability.system_logger import emit_system_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class DecisionPayload(BaseModel):
    """Optional admin edits applied at the moment of approve/deny."""

    adjusted_payout: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    justification: str | None = Field(default=None, max_length=20000)
    notes: str | None = Field(default=None, max_length=5000)


class EditAndApproveRequest(BaseModel):
    """Payload schema for editing payout and notes before manual approval."""

    adjusted_payout: Decimal = Field(..., ge=Decimal("0.00"))
    adjuster_notes: str


def _serialize_approval(c) -> dict[str, Any]:
    """Serialize a claim for the admin approval queue with full review detail."""
    final_payout = (
        c.adjusted_payout if c.adjusted_payout is not None else c.calculated_payout
    )
    final_justification = c.admin_justification or c.reasoning_text or c.recommendation
    return {
        "id": str(c.id),
        "claim_id": str(c.id),
        "user_id": str(c.user_id) if c.user_id else None,
        "policy_number": c.policy_number,
        "date_of_loss": str(c.date_of_loss),
        "incident_description": c.incident_description,
        "claim_amount_requested": str(c.claim_amount_requested),
        "status": c.status,
        "pipeline_stage": c.pipeline_stage,
        "recommended_payout": str(c.calculated_payout)
        if c.calculated_payout is not None
        else None,
        "adjusted_payout": str(c.adjusted_payout)
        if c.adjusted_payout is not None
        else None,
        "final_payout": str(final_payout) if final_payout is not None else None,
        "deductible_applied": str(c.deductible_applied)
        if c.deductible_applied is not None
        else None,
        "policy_limit": str(c.policy_limit) if c.policy_limit is not None else None,
        "recommendation_reasoning": c.recommendation,
        "ai_justification": c.reasoning_text,
        "admin_justification": c.admin_justification,
        "final_justification": final_justification,
        "adjuster_notes": c.adjuster_notes,
        "citations": c.citations or [],
        "error_message": c.error_message,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_approvals(
    current_user: UserPayload = Depends(require_role("corp")),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> list[dict[str, Any]]:
    """Return every claim for adjuster review (pending and decided)."""
    claims = await claim_repo.list_all()
    return [_serialize_approval(c) for c in claims]


async def _load_claim(claim_id: UUID, claim_repo: ClaimRepository):
    claim = await claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    return claim


def _apply_decision_edits(claim, payload: DecisionPayload | None) -> dict[str, Any]:
    """Persist optional admin edits (payout / justification / notes) onto the claim."""
    applied: dict[str, Any] = {}
    if payload is None:
        return applied
    if payload.adjusted_payout is not None:
        claim.adjusted_payout = payload.adjusted_payout
        applied["adjusted_payout"] = str(payload.adjusted_payout)
    if payload.justification is not None and payload.justification.strip():
        claim.admin_justification = payload.justification
        applied["admin_justification"] = True
    if payload.notes is not None and payload.notes.strip():
        claim.adjuster_notes = payload.notes
        applied["adjuster_notes"] = payload.notes
    return applied


@router.post("/{claim_id}/approve", status_code=status.HTTP_200_OK)
async def approve_claim(
    claim_id: UUID,
    payload: DecisionPayload | None = None,
    current_user: UserPayload = Depends(require_role("corp")),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Approve a claim, optionally persisting payout/justification edits first."""
    claim = await _load_claim(claim_id, claim_repo)

    old_status = claim.status
    edits = _apply_decision_edits(claim, payload)
    claim.status = "approved"
    from datetime import datetime, timezone

    claim.updated_at = datetime.now(timezone.utc)
    await claim_repo.save(claim)

    logger.info(
        f"[AUDIT TRAIL] Adjuster {current_user.email} APPROVED claim {claim_id} "
        f"(Status: {old_status} -> approved, edits: {edits})"
    )
    emit_system_log(
        "approval",
        "approved",
        {
            "claim_id": str(claim_id),
            "reviewer": current_user.email,
            "old_status": old_status,
            "edits": edits,
        },
    )
    return {
        "status": "success",
        "claim_id": str(claim.id),
        "decision": "approved",
        "approved_by": current_user.email,
        "edits": edits,
    }


@router.post("/{claim_id}/reject", status_code=status.HTTP_200_OK)
async def reject_claim(
    claim_id: UUID,
    payload: DecisionPayload | None = None,
    current_user: UserPayload = Depends(require_role("corp")),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Deny a claim, optionally recording justification edits / adjuster notes."""
    claim = await _load_claim(claim_id, claim_repo)

    old_status = claim.status
    edits = _apply_decision_edits(claim, payload)
    claim.status = "rejected"
    from datetime import datetime, timezone

    claim.updated_at = datetime.now(timezone.utc)
    await claim_repo.save(claim)

    logger.info(
        f"[AUDIT TRAIL] Adjuster {current_user.email} REJECTED claim {claim_id} "
        f"(Status: {old_status} -> rejected, edits: {edits})"
    )
    emit_system_log(
        "approval",
        "rejected",
        {
            "claim_id": str(claim_id),
            "reviewer": current_user.email,
            "old_status": old_status,
            "edits": edits,
        },
    )
    return {
        "status": "success",
        "claim_id": str(claim.id),
        "decision": "rejected",
        "rejected_by": current_user.email,
        "edits": edits,
    }


@router.post("/{claim_id}/edit-and-approve", status_code=status.HTTP_200_OK)
async def edit_and_approve_claim(
    claim_id: UUID,
    payload: EditAndApproveRequest,
    current_user: UserPayload = Depends(require_role("corp")),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Edit claim payout/notes and approve (Strictly restricted to adjuster role)."""
    claim = await _load_claim(claim_id, claim_repo)

    old_status = claim.status
    claim.adjusted_payout = payload.adjusted_payout
    claim.adjuster_notes = payload.adjuster_notes
    claim.status = "approved"
    from datetime import datetime, timezone

    claim.updated_at = datetime.now(timezone.utc)
    await claim_repo.save(claim)

    logger.info(
        f"[AUDIT TRAIL] Adjuster {current_user.email} EDITED & APPROVED claim {claim_id} "
        f"with payout {payload.adjusted_payout} (Notes: {payload.adjuster_notes}) "
        f"(Status: {old_status} -> approved)"
    )
    emit_system_log(
        "approval",
        "edit_and_approved",
        {
            "claim_id": str(claim_id),
            "reviewer": current_user.email,
            "old_status": old_status,
            "adjusted_payout": str(payload.adjusted_payout),
            "adjuster_notes": payload.adjuster_notes,
        },
    )
    return {
        "status": "success",
        "claim_id": str(claim.id),
        "decision": "approved",
        "adjusted_payout": str(payload.adjusted_payout),
        "adjuster_notes": payload.adjuster_notes,
        "approved_by": current_user.email,
    }
