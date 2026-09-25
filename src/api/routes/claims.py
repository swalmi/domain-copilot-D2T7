from datetime import date, datetime, timezone
from decimal import Decimal
import logging
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.api.deps import (
    UserPayload,
    get_claim_repository,
    get_current_user,
    require_role,
)
from src.infrastructure.observability.pause_registry import pause_run, resume_run
from src.infrastructure.observability.system_logger import emit_system_log
from src.domain.entities.claim import Claim
from src.domain.interfaces.claim_repository import ClaimRepository
from src.infrastructure.tasks.celery_app import celery_app
from src.infrastructure.tasks.claim_tasks import process_claim_adjudication

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["Claims"])

# Map claim_id to task_id for Celery task revocation within this process.
# The durable celery_task_id on the Claim record is the authoritative source.
_claim_task_map: dict[UUID, str] = {}

# Twist T7 — idempotent submission. A retried POST with the same idempotency key
# resolves to the same claim id, so the replay finds the original row instead of
# creating a duplicate claim and a duplicate Celery job.
_IDEMPOTENCY_NAMESPACE = uuid5(NAMESPACE_URL, "insureAI/claim-submission")
_MIN_IDEMPOTENCY_KEY = 8
_MAX_IDEMPOTENCY_KEY = 128


def claim_id_for_idempotency_key(user_id: str, idempotency_key: str) -> UUID:
    """Derive the stable claim id that a retried submission must land on."""
    return uuid5(_IDEMPOTENCY_NAMESPACE, f"{user_id}:{idempotency_key}")

# Statuses a corp adjuster may permanently delete (a decision has been taken).
_CORP_DELETABLE_STATUSES = frozenset(
    {"approved", "rejected", "refused", "cancelled", "failed"}
)
# Statuses locked for corp delete until approve/deny happens.
_CORP_LOCKED_STATUSES = frozenset(
    {"submitted", "processing", "report_ready", "pending_approval"}
)


class CreateClaimRequest(BaseModel):
    """Payload schema for submitting a new insurance claim with unbounded consumption limits."""

    policy_number: str = Field(..., max_length=100)
    date_of_loss: date
    incident_description: str = Field(..., max_length=10000)
    claim_amount_requested: Decimal = Field(..., gt=Decimal("0.00"), le=Decimal("10000000.00"))
    idempotency_key: str | None = Field(
        default=None,
        min_length=_MIN_IDEMPOTENCY_KEY,
        max_length=_MAX_IDEMPOTENCY_KEY,
        description=(
            "Optional client-generated key. Retrying the submission with the same "
            "key returns the original claim instead of creating a duplicate."
        ),
    )


def serialize_claim(claim: Claim) -> dict[str, Any]:
    """Serialize a Claim entity into the full API response contract used by the UI."""
    final_payout = (
        claim.adjusted_payout if claim.adjusted_payout is not None else claim.calculated_payout
    )
    final_justification = claim.admin_justification or claim.reasoning_text
    return {
        "id": str(claim.id),
        "claim_id": str(claim.id),
        "correlation_id": str(claim.correlation_id) if claim.correlation_id else None,
        "user_id": str(claim.user_id) if claim.user_id else None,
        "policy_number": claim.policy_number,
        "date_of_loss": str(claim.date_of_loss),
        "incident_description": claim.incident_description,
        "claim_amount_requested": str(claim.claim_amount_requested),
        "status": claim.status,
        "pipeline_stage": claim.pipeline_stage,
        "calculated_payout": str(claim.calculated_payout) if claim.calculated_payout is not None else None,
        "deductible_applied": str(claim.deductible_applied) if claim.deductible_applied is not None else None,
        "policy_limit": str(claim.policy_limit) if claim.policy_limit is not None else None,
        "adjusted_payout": str(claim.adjusted_payout) if claim.adjusted_payout is not None else None,
        "final_payout": str(final_payout) if final_payout is not None else None,
        "adjuster_notes": claim.adjuster_notes,
        "admin_justification": claim.admin_justification,
        "recommendation": claim.recommendation,
        "reasoning_text": claim.reasoning_text,
        "final_justification": final_justification,
        "citations": claim.citations or [],
        "error_message": claim.error_message,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "updated_at": claim.updated_at.isoformat() if claim.updated_at else None,
    }


def _assert_claim_access(claim: Claim, current_user: UserPayload) -> None:
    """Clients may only touch their own claims; corp may touch any claim."""
    if current_user.role == "corp":
        return
    if claim.user_id is None:
        return  # Legacy claim without ownership — allow authenticated read.
    if str(claim.user_id) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you do not own this claim.",
        )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_claim(
    payload: CreateClaimRequest,
    request: Request,
    current_user: UserPayload = Depends(require_role("client")),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Submit a new insurance claim for asynchronous processing via Celery worker.

    Idempotent when the client supplies an idempotency key — as an
    ``Idempotency-Key`` header or ``idempotency_key`` in the body. A replay
    returns the original claim (``idempotent_replay: true``) and never
    dispatches a second Celery job.
    """
    idempotency_key = request.headers.get("Idempotency-Key") or payload.idempotency_key
    if idempotency_key and not (
        _MIN_IDEMPOTENCY_KEY <= len(idempotency_key) <= _MAX_IDEMPOTENCY_KEY
        and idempotency_key.isprintable()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Idempotency key must be {_MIN_IDEMPOTENCY_KEY}-"
                f"{_MAX_IDEMPOTENCY_KEY} printable characters."
            ),
        )

    if idempotency_key:
        claim_id = claim_id_for_idempotency_key(current_user.id, idempotency_key)
        existing = await claim_repo.get_by_id(claim_id)
        if existing is not None:
            emit_system_log(
                "adjudication",
                "claim_submission_replayed",
                {
                    "claim_id": str(existing.id),
                    "idempotency_key_len": len(idempotency_key),
                    "status": existing.status,
                    "user_id": current_user.id,
                },
            )
            return {
                "claim_id": str(existing.id),
                "task_id": existing.celery_task_id,
                "correlation_id": str(existing.correlation_id)
                if existing.correlation_id
                else None,
                "status": existing.status,
                "idempotent_replay": True,
            }
    else:
        claim_id = uuid4()

    correlation_id = uuid4()
    claim = Claim(
        id=claim_id,
        policy_number=payload.policy_number,
        date_of_loss=payload.date_of_loss,
        incident_description=payload.incident_description,
        claim_amount_requested=payload.claim_amount_requested,
        status="submitted",
        user_id=UUID(current_user.id),
        pipeline_stage="understanding",
        correlation_id=correlation_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await claim_repo.save(claim)

    claim_dict = {
        "id": str(claim.id),
        "policy_number": claim.policy_number,
        "date_of_loss": str(claim.date_of_loss),
        "incident_description": claim.incident_description,
        "claim_amount_requested": str(claim.claim_amount_requested),
        "status": claim.status,
        "user_id": str(claim.user_id) if claim.user_id else None,
        "pipeline_stage": claim.pipeline_stage,
        "correlation_id": str(claim.correlation_id),
    }

    task = process_claim_adjudication.delay(claim_dict)
    claim.celery_task_id = task.id
    await claim_repo.save(claim)
    _claim_task_map[claim_id] = task.id
    emit_system_log(
        "adjudication",
        "claim_submitted",
        {
            "claim_id": str(claim_id),
            "task_id": task.id,
            "correlation_id": str(correlation_id),
            "policy_number": claim.policy_number,
            "claim_amount": str(claim.claim_amount_requested),
            "user_id": claim_dict["user_id"],
        },
    )

    return {
        "claim_id": str(claim_id),
        "task_id": task.id,
        "correlation_id": str(correlation_id),
        "status": "pending",
        "idempotent_replay": False,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_claims(
    current_user: UserPayload = Depends(get_current_user),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> list[dict[str, Any]]:
    """List claims: clients see their own, corp adjusters see every claim."""
    if current_user.role == "corp":
        claims = await claim_repo.list_all()
    else:
        claims = await claim_repo.list_by_user(UUID(current_user.id))
    return [serialize_claim(c) for c in claims]


@router.post("/{claim_id}/pause", status_code=status.HTTP_200_OK)
async def pause_claim(
    claim_id: UUID,
    current_user: UserPayload = Depends(require_role("corp")),
) -> dict[str, str]:
    """Pause an active claim workflow (cluster-safe using Redis pub/sub)."""
    await pause_run(claim_id)
    emit_system_log("adjudication", "claim_paused", {"claim_id": str(claim_id)})
    return {"status": "paused", "claim_id": str(claim_id)}


@router.post("/{claim_id}/resume", status_code=status.HTTP_200_OK)
async def resume_claim(
    claim_id: UUID,
    current_user: UserPayload = Depends(require_role("corp")),
) -> dict[str, str]:
    """Resume a previously paused claim workflow (cluster-safe)."""
    await resume_run(claim_id)
    emit_system_log("adjudication", "claim_resumed", {"claim_id": str(claim_id)})
    return {"status": "resumed", "claim_id": str(claim_id)}


@router.get("/{claim_id}", status_code=status.HTTP_200_OK)
async def get_claim_status(
    claim_id: UUID,
    current_user: UserPayload = Depends(get_current_user),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Retrieve the full adjudication result for a claim by its ID."""
    claim = await claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _assert_claim_access(claim, current_user)
    return serialize_claim(claim)


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
    _assert_claim_access(claim, current_user)

    task_id = claim.celery_task_id or _claim_task_map.get(claim_id)
    if task_id:
        try:
            celery_app.control.revoke(task_id, terminate=True)
            logger.info(f"[AUDIT TRAIL] Revoked Celery task {task_id} for claim {claim_id}")
        except Exception as exc:
            logger.warning(f"Failed to revoke Celery task {task_id}: {exc}")

    old_status = claim.status
    claim.status = "cancelled"
    claim.updated_at = datetime.now(timezone.utc)
    await claim_repo.save(claim)

    logger.info(
        f"[AUDIT TRAIL] User {current_user.email} CANCELLED claim {claim_id} (Status: {old_status} -> cancelled)"
    )
    emit_system_log(
        "adjudication",
        "claim_cancelled",
        {"claim_id": str(claim_id), "actor": current_user.email, "old_status": old_status},
    )

    return {
        "status": "success",
        "claim_id": str(claim.id),
        "task_id": task_id,
        "claim_status": "cancelled",
        "message": "Claim cancelled and Celery task revoked.",
    }


@router.delete("/{claim_id}", status_code=status.HTTP_200_OK)
async def delete_claim(
    claim_id: UUID,
    current_user: UserPayload = Depends(get_current_user),
    claim_repo: ClaimRepository = Depends(get_claim_repository),
) -> dict[str, Any]:
    """Delete a claim. Clients delete their own; corp only after a decision."""
    claim = await claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )

    if current_user.role == "corp":
        if claim.status in _CORP_LOCKED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot delete an undecided claim. "
                    "Approve or deny it first before deleting."
                ),
            )
        if claim.status not in _CORP_DELETABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Claim in status '{claim.status}' cannot be deleted.",
            )
    else:
        _assert_claim_access(claim, current_user)

    # Best-effort revoke if still tied to a live task.
    task_id = claim.celery_task_id or _claim_task_map.get(claim_id)
    if task_id and claim.status in ("submitted", "processing"):
        try:
            celery_app.control.revoke(task_id, terminate=True)
        except Exception as exc:
            logger.warning(f"Failed to revoke Celery task {task_id} during delete: {exc}")

    deleted = await claim_repo.delete(claim_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _claim_task_map.pop(claim_id, None)

    logger.info(
        f"[AUDIT TRAIL] User {current_user.email} DELETED claim {claim_id} (Status was: {claim.status})"
    )
    emit_system_log(
        "adjudication",
        "claim_deleted",
        {"claim_id": str(claim_id), "actor": current_user.email, "old_status": claim.status},
    )
    return {
        "status": "success",
        "claim_id": str(claim_id),
        "message": "Claim deleted permanently.",
    }
