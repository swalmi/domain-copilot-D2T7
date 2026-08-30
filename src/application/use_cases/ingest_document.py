from datetime import date
import logging
from pathlib import Path
from typing import Literal
from uuid import UUID
import uuid

from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.document_repository import DocumentRepository
from src.domain.interfaces.llm_provider import LLMProvider
from src.domain.interfaces.vector_store import VectorStore
from src.infrastructure.embeddings.cached_embedder import CachedEmbedder
from src.infrastructure.ingestion.document_loader import (
    compute_chunk_hash,
    compute_document_hash,
    load_and_chunk,
)
from src.infrastructure.ingestion.table_title_linker import link_tables_to_titles

logger = logging.getLogger(__name__)


class IngestDocumentUseCase:
    """Use case for processing, embedding, and storing policy document chunks."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        vector_store: VectorStore,
        document_repo: DocumentRepository,
    ) -> None:
        """Initialize use case with required infrastructure providers and repositories."""
        self._llm_provider = llm_provider
        self._embedder = CachedEmbedder(llm_provider)
        self._vector_store = vector_store
        self._document_repo = document_repo

    async def execute(
        self,
        file_path: str,
        policy_id: str,
        policy_type: Literal["auto", "home", "liability"] | str,
        version: str,
        effective_date: date,
    ) -> dict:
        """Execute the ingestion pipeline for a policy document."""
        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
            doc_hash = compute_document_hash(raw_bytes)
        except Exception as e:
            logger.error(f"Failed to read document {file_path}: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

        existing_doc_id = await self._document_repo.get_document_by_hash(doc_hash)
        if existing_doc_id is not None:
            return {"status": "already_ingested"}

        doc_id = await self._document_repo.create_document(
            filename=Path(file_path).name,
            content_hash=doc_hash,
            status="processing",
        )

        try:
            raw_chunks = load_and_chunk(
                file_path=file_path,
                policy_id=policy_id,
                policy_type=policy_type,
                version=version,
                effective_date=effective_date,
            )
            chunks = link_tables_to_titles(raw_chunks)

            inserted_count = 0
            for chunk_dict in chunks:
                chunk_text = chunk_dict.get("text", "")
                if not chunk_text:
                    continue

                c_hash = compute_chunk_hash(chunk_text)
                if await self._vector_store.chunk_exists(c_hash):
                    continue

                embedding = await self._embedder.embed(chunk_text)

                c_id = chunk_dict.get("element_id")
                chunk_uuid = None
                try:
                    chunk_uuid = UUID(c_id) if c_id else uuid.uuid4()
                except (ValueError, TypeError):
                    chunk_uuid = uuid.uuid4()

                cited_chunk = CitedChunk(
                    chunk_id=chunk_uuid,
                    text=chunk_text,
                    source_document=str(doc_id),
                    section=chunk_dict.get("section") or "",
                    page=chunk_dict.get("page_number") or 1,
                    policy_id=policy_id,
                    version=version,
                    effective_date=effective_date,
                    chunk_type=chunk_dict.get("chunk_type", "narrative"),
                    policy_type=policy_type,
                )

                await self._vector_store.upsert(cited_chunk, embedding)
                inserted_count += 1

            await self._document_repo.save_document_status(doc_id, "success")
            return {
                "status": "success",
                "document_id": str(doc_id),
                "chunks_count": len(chunks),
                "inserted_count": inserted_count,
            }
        except Exception as e:
            logger.error(f"Ingestion processing failed for {file_path}: {e}", exc_info=True)
            await self._document_repo.save_document_status(doc_id, "failed")
            return {"status": "failed", "error": str(e)}
