from datetime import datetime, timezone
from uuid import UUID
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces.document_repository import DocumentRepository
from src.infrastructure.db.models import DocumentModel


class SqlalchemyDocumentRepository(DocumentRepository):
    """SQLAlchemy implementation of the DocumentRepository domain interface."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with an active AsyncSession."""
        self._session = session

    async def create_document(
        self, filename: str, content_hash: str, status: str
    ) -> UUID:
        """Create a new document record and return its generated UUID."""
        doc_id = uuid.uuid4()
        doc = DocumentModel(
            id=doc_id,
            filename=filename,
            content_hash=content_hash,
            status=status,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(doc)
        await self._session.commit()
        return doc_id

    async def save_document_status(self, document_id: UUID, status: str) -> None:
        """Update the processing status of a policy document."""
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        res = await self._session.execute(stmt)
        doc = res.scalar_one_or_none()
        if doc:
            doc.status = status
            await self._session.commit()

    async def get_document_by_hash(self, content_hash: str) -> UUID | None:
        """Retrieve a policy document ID by its content hash to prevent duplicate ingestion."""
        stmt = select(DocumentModel.id).where(DocumentModel.content_hash == content_hash)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()
