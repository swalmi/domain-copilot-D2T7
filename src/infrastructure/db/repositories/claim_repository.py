from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.claim import Claim
from src.domain.interfaces.claim_repository import ClaimRepository
from src.infrastructure.db.models import ClaimModel


class SqlAlchemyClaimRepository(ClaimRepository):
    """SQLAlchemy-backed implementation of ClaimRepository using durable PostgreSQL storage.

    Claims persist in the ``claims`` table so that submission (API process),
    adjudication (Celery worker process) and GET-by-id (API process) all share
    the same record across process boundaries and API restarts.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with an active AsyncSession."""
        self._session = session

    @staticmethod
    def _to_model(claim: Claim, row: ClaimModel | None = None) -> ClaimModel:
        """Map a domain Claim entity onto a ClaimModel row (creating or updating)."""
        now = datetime.now(timezone.utc)
        if row is None:
            model = ClaimModel(
                id=claim.id,
                created_at=claim.created_at or now,
                updated_at=now,
            )
        else:
            model = row
            model.updated_at = now

        model.policy_number = claim.policy_number
        model.date_of_loss = claim.date_of_loss
        model.incident_description = claim.incident_description
        model.claim_amount_requested = claim.claim_amount_requested
        model.status = claim.status
        model.user_id = claim.user_id
        model.pipeline_stage = claim.pipeline_stage
        model.correlation_id = claim.correlation_id
        model.celery_task_id = claim.celery_task_id
        model.calculated_payout = claim.calculated_payout
        model.deductible_applied = claim.deductible_applied
        model.policy_limit = claim.policy_limit
        model.recommendation = claim.recommendation
        model.reasoning_text = claim.reasoning_text
        model.citations = claim.citations
        model.error_message = claim.error_message
        model.adjusted_payout = claim.adjusted_payout
        model.adjuster_notes = claim.adjuster_notes
        model.admin_justification = claim.admin_justification
        if claim.created_at is not None:
            model.created_at = claim.created_at
        return model

    @staticmethod
    def _to_entity(model: ClaimModel) -> Claim:
        """Map a ClaimModel row back onto a domain Claim entity."""
        return Claim(
            id=model.id,
            policy_number=model.policy_number,
            date_of_loss=model.date_of_loss,
            incident_description=model.incident_description,
            claim_amount_requested=Decimal(str(model.claim_amount_requested))
            if model.claim_amount_requested is not None
            else Decimal("0.00"),
            status=model.status,
            user_id=model.user_id,
            pipeline_stage=model.pipeline_stage,
            correlation_id=model.correlation_id,
            celery_task_id=model.celery_task_id,
            calculated_payout=Decimal(str(model.calculated_payout))
            if model.calculated_payout is not None
            else None,
            deductible_applied=Decimal(str(model.deductible_applied))
            if model.deductible_applied is not None
            else None,
            policy_limit=Decimal(str(model.policy_limit))
            if model.policy_limit is not None
            else None,
            recommendation=model.recommendation,
            reasoning_text=model.reasoning_text,
            citations=model.citations,
            error_message=model.error_message,
            adjusted_payout=Decimal(str(model.adjusted_payout))
            if model.adjusted_payout is not None
            else None,
            adjuster_notes=model.adjuster_notes,
            admin_justification=model.admin_justification,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, claim: Claim) -> None:
        """Persist or update a claim in PostgreSQL."""
        stmt = select(ClaimModel).where(ClaimModel.id == claim.id)
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        model = self._to_model(claim, row)
        if row is None:
            self._session.add(model)
        await self._session.commit()

    async def get_by_id(self, claim_id: UUID) -> Claim | None:
        """Retrieve a claim entity by unique ID from PostgreSQL."""
        stmt = select(ClaimModel).where(ClaimModel.id == claim_id)
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        return self._to_entity(row) if row is not None else None

    async def list_pending_approvals(self) -> list[Claim]:
        """Retrieve all claims currently pending manual approval."""
        stmt = (
            select(ClaimModel)
            .where(ClaimModel.status.in_(["pending_approval", "submitted", "processing", "report_ready"]))
            .order_by(ClaimModel.created_at.desc())
        )
        res = await self._session.execute(stmt)
        return [self._to_entity(row) for row in res.scalars().all()]

    async def list_all(self) -> list[Claim]:
        """Retrieve every claim regardless of status (admin review)."""
        stmt = select(ClaimModel).order_by(ClaimModel.created_at.desc())
        res = await self._session.execute(stmt)
        return [self._to_entity(row) for row in res.scalars().all()]

    async def list_by_user(self, user_id: UUID) -> list[Claim]:
        """Retrieve all claims owned by a specific user."""
        stmt = (
            select(ClaimModel)
            .where(ClaimModel.user_id == user_id)
            .order_by(ClaimModel.created_at.desc())
        )
        res = await self._session.execute(stmt)
        return [self._to_entity(row) for row in res.scalars().all()]

    async def delete(self, claim_id: UUID) -> bool:
        """Permanently remove a claim row; return True if one was deleted."""
        from sqlalchemy import delete as sa_delete

        stmt = sa_delete(ClaimModel).where(ClaimModel.id == claim_id)
        res = await self._session.execute(stmt)
        await self._session.commit()
        return bool(res.rowcount)


class InMemoryClaimRepository(ClaimRepository):
    """In-memory implementation of ClaimRepository for domain claims and tests."""

    def __init__(self) -> None:
        """Initialize in-memory storage dictionary."""
        self._claims: dict[UUID, Claim] = {}

    async def save(self, claim: Claim) -> None:
        """Persist or update a claim in memory."""
        self._claims[claim.id] = claim

    async def get_by_id(self, claim_id: UUID) -> Claim | None:
        """Retrieve a claim entity by unique ID from memory."""
        return self._claims.get(claim_id)

    async def list_pending_approvals(self) -> list[Claim]:
        """Retrieve all claims currently pending manual approval."""
        return [
            claim
            for claim in self._claims.values()
            if claim.status in ("pending_approval", "submitted", "processing", "report_ready")
        ]

    async def list_all(self) -> list[Claim]:
        """Retrieve every claim regardless of status (admin review)."""
        return list(self._claims.values())

    async def list_by_user(self, user_id: UUID) -> list[Claim]:
        """Retrieve all claims owned by a specific user."""
        return [c for c in self._claims.values() if c.user_id == user_id]

    async def delete(self, claim_id: UUID) -> bool:
        """Permanently remove a claim from memory; return True if present."""
        return self._claims.pop(claim_id, None) is not None