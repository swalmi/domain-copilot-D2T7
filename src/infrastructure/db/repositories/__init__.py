"""Repositories package."""

from src.infrastructure.db.repositories.document_repository import (
    SqlalchemyDocumentRepository,
)

__all__ = ["SqlalchemyDocumentRepository"]
