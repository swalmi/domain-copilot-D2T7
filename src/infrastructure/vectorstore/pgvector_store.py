from datetime import datetime, timezone
from uuid import UUID
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.vector_store import VectorStore
from src.infrastructure.db.models import ChunkModel, DocumentModel
from src.infrastructure.ingestion.document_loader import (
    compute_chunk_hash,
    compute_document_hash,
)


def _apply_filters(stmt, filters: dict | None):
    if not filters:
        return stmt

    conditions = []
    if "policy_id" in filters and filters["policy_id"]:
        conditions.append(ChunkModel.policy_id == filters["policy_id"])
    if "policy_type" in filters and filters["policy_type"]:
        conditions.append(ChunkModel.policy_type == filters["policy_type"])
    if "effective_date_before" in filters and filters["effective_date_before"]:
        conditions.append(
            ChunkModel.effective_date <= filters["effective_date_before"]
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector implementation of the VectorStore domain interface."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize PgVectorStore with an active SQLAlchemy AsyncSession."""
        self._session = session

    async def search(
        self, query_embedding: list[float], filters: dict, top_k: int
    ) -> list[CitedChunk]:
        """Search for relevant policy chunks using dense vector similarity embeddings."""
        stmt = select(ChunkModel, DocumentModel.filename).join(
            DocumentModel, ChunkModel.document_id == DocumentModel.id
        )
        stmt = _apply_filters(stmt, filters)
        stmt = stmt.order_by(
            ChunkModel.embedding.cosine_distance(query_embedding)
        ).limit(top_k)

        result = await self._session.execute(stmt)
        rows = result.all()

        cited_chunks: list[CitedChunk] = []
        for chunk_obj, filename in rows:
            cited_chunks.append(
                CitedChunk(
                    chunk_id=chunk_obj.id,
                    text=chunk_obj.text,
                    source_document=filename,
                    section=chunk_obj.section or "",
                    page=chunk_obj.page or 1,
                    policy_id=chunk_obj.policy_id,
                    version=chunk_obj.version,
                    effective_date=chunk_obj.effective_date,
                    chunk_type=chunk_obj.chunk_type,
                    policy_type=chunk_obj.policy_type,
                )
            )
        return cited_chunks

    async def keyword_search(
        self, query_text: str, filters: dict, top_k: int
    ) -> list[CitedChunk]:
        """Search for relevant policy chunks using Postgres full-text keyword matching."""
        ts_vector = func.to_tsvector("english", ChunkModel.text)
        ts_query = func.plainto_tsquery("english", query_text)

        stmt = (
            select(ChunkModel, DocumentModel.filename)
            .join(DocumentModel, ChunkModel.document_id == DocumentModel.id)
            .where(ts_vector.op("@@")(ts_query))
        )
        stmt = _apply_filters(stmt, filters)
        stmt = stmt.order_by(func.ts_rank(ts_vector, ts_query).desc()).limit(top_k)

        result = await self._session.execute(stmt)
        rows = result.all()

        cited_chunks: list[CitedChunk] = []
        for chunk_obj, filename in rows:
            cited_chunks.append(
                CitedChunk(
                    chunk_id=chunk_obj.id,
                    text=chunk_obj.text,
                    source_document=filename,
                    section=chunk_obj.section or "",
                    page=chunk_obj.page or 1,
                    policy_id=chunk_obj.policy_id,
                    version=chunk_obj.version,
                    effective_date=chunk_obj.effective_date,
                    chunk_type=chunk_obj.chunk_type,
                    policy_type=chunk_obj.policy_type,
                )
            )
        return cited_chunks

    async def chunk_exists(self, content_hash: str) -> bool:
        """Check if a chunk with the specified content hash already exists in the database."""
        stmt = select(ChunkModel.id).where(ChunkModel.content_hash == content_hash)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def upsert(self, chunk: CitedChunk, embedding: list[float]) -> None:
        """Insert a policy chunk and its vector embedding idempotently into the store."""
        content_hash = compute_chunk_hash(chunk.text)

        if await self.chunk_exists(content_hash):
            return

        doc_id = None
        try:
            doc_id = UUID(chunk.source_document)
        except (ValueError, TypeError):
            pass

        if not doc_id:
            doc_stmt = select(DocumentModel).where(
                DocumentModel.filename == chunk.source_document
            )
            doc_res = await self._session.execute(doc_stmt)
            doc_obj = doc_res.scalar_one_or_none()
            if not doc_obj:
                doc_obj = DocumentModel(
                    id=uuid.uuid4(),
                    filename=chunk.source_document,
                    content_hash=compute_document_hash(
                        chunk.source_document.encode("utf-8")
                    ),
                    status="PROCESSED",
                    created_at=datetime.now(timezone.utc),
                )
                self._session.add(doc_obj)
                await self._session.flush()
            doc_id = doc_obj.id

        new_chunk = ChunkModel(
            id=chunk.chunk_id,
            document_id=doc_id,
            policy_id=chunk.policy_id,
            policy_type=getattr(chunk, "policy_type", "home"),
            version=chunk.version,
            effective_date=chunk.effective_date,
            section=chunk.section,
            chunk_type=chunk.chunk_type,
            page=chunk.page,
            text=chunk.text,
            content_hash=content_hash,
            embedding=embedding,
        )
        self._session.add(new_chunk)
        await self._session.commit()
