from uuid import UUID

from src.domain.entities.claim import Claim
from src.domain.interfaces.claim_repository import ClaimRepository


class InMemoryClaimRepository(ClaimRepository):
    """In-memory implementation of ClaimRepository for domain claims."""

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
            if claim.status in ("pending_approval", "submitted", "processing")
        ]
