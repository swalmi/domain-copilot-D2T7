from abc import ABC, abstractmethod
from uuid import UUID


class DocumentRepository(ABC):
    """Abstract interface defining persistence operations for policy documents."""

    @abstractmethod
    async def save_document_status(self, document_id: UUID, status: str) -> None:
        """Update the processing status of a policy document."""

    @abstractmethod
    async def get_document_by_hash(self, content_hash: str) -> UUID | None:
        """Retrieve a policy document ID by its content hash to prevent duplicates."""
