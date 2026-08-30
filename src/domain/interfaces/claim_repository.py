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
