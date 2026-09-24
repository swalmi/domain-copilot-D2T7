from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.claim import Claim


class ClaimRepository(ABC):
    """Abstract interface defining persistence operations for insurance claims."""

    @abstractmethod
    async def save(self, claim: Claim) -> None:
        """Persist an insurance claim entity into storage."""

    @abstractmethod
    async def get_by_id(self, claim_id: UUID) -> Claim | None:
        """Retrieve an insurance claim entity by its unique identifier."""

    @abstractmethod
    async def list_pending_approvals(self) -> list[Claim]:
        """Retrieve all claims currently pending manual approval."""

    @abstractmethod
    async def list_all(self) -> list[Claim]:
        """Retrieve every claim regardless of status (admin review)."""

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[Claim]:
        """Retrieve all claims owned by a specific user."""

    @abstractmethod
    async def delete(self, claim_id: UUID) -> bool:
        """Permanently remove a claim; return True if a row was deleted."""
