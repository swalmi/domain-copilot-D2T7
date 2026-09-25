import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

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
from src.infrastructure.observability.chunk_log import append_chunk_log
from src.infrastructure.observability.document_chunk_store import write_document_chunks
from src.infrastructure.observability.system_logger import emit_system_log
from src.infrastructure.observability.trace_logger import record_trace_event

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
        on_progress: Callable[[dict[str, Any]], None] | None = None,
        filename: str | None = None,
    ) -> dict:
        """Execute the ingestion pipeline for a policy document.

        :param on_progress: Optional callback invoked as each business stage of the
            pipeline (parsing, chunking, titling, embedding, storing, finalizing)
            transitions states, so a UI can render a live Jenkins-style pipeline.
        :param filename: Original uploaded filename. Falls back to the basename of
            ``file_path`` (e.g. a server-side temp path) when not provided.
        """
        # Correlation id for traceability of this ingestion run
        correlation_id = uuid.uuid4()

        def emit(step: str, status: str, **detail: Any) -> None:
            # Every stage transition lands in the single system_logs.txt sink
            # (visible live via ./scripts/system-logs) AND fans out to the SSE UI.
            emit_system_log(
                "ingestion",
                f"{step}_{status}",
                {"step": step, "status": status, **detail},
                correlation_id=correlation_id,
            )
            if on_progress is None:
                return
            on_progress({"step": step, "status": status, **detail})

        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
            doc_hash = compute_document_hash(raw_bytes)
            emit("parsing", "running")
            emit(
                "parsing",
                "completed",
                detail="Document read and hashed for duplicate detection",
            )
            record_trace_event(
                correlation_id,
                "IngestDocument",
                "input",
                {"file_path": file_path, "policy_id": policy_id, "content_hash": doc_hash},
            )
        except Exception as e:
            logger.error(f"Failed to read document {file_path}: {e}", exc_info=True)
            emit("parsing", "failed", detail=f"Could not read the document: {e}")
            record_trace_event(correlation_id, "IngestDocument", "error", {"error": str(e)})
            return {"status": "failed", "error": str(e), "correlation_id": str(correlation_id)}

        existing_doc_id = await self._document_repo.get_document_by_hash(doc_hash)
        if existing_doc_id is not None:
            record_trace_event(
                correlation_id,
                "IngestDocument",
                "decision",
                {"status": "already_ingested", "existing_document_id": str(existing_doc_id)},
            )
            return {"status": "already_ingested", "existing_document_id": str(existing_doc_id), "correlation_id": str(correlation_id)}

        doc_id = await self._document_repo.create_document(
            filename=filename or Path(file_path).name,
            content_hash=doc_hash,
            status="processing",
        )

        try:
            emit("chunking", "running")
            # Unstructured parsing is CPU-bound; keep the event loop responsive so
            # progress events (and the rest of the API) keep flowing during big files.
            # Internal per-second + per-element progress goes straight to the system
            # log (thread-safe file append) — never into the SSE queue, which is
            # bound to the event-loop thread.

            def _chunk_progress(info: dict[str, Any]) -> None:
                emit_system_log(
                    "ingestion",
                    "chunking_progress",
                    info,
                    correlation_id=correlation_id,
                )

            raw_chunks = await asyncio.to_thread(
                load_and_chunk,
                file_path=file_path,
                policy_id=policy_id,
                policy_type=policy_type,
                version=version,
                effective_date=effective_date,
                on_progress=_chunk_progress,
            )
            emit(
                "chunking",
                "completed",
                current=len(raw_chunks),
                total=len(raw_chunks),
                detail=f"Split document into {len(raw_chunks)} raw elements",
            )

            emit("titling", "running")

            def _titling_progress(info: dict[str, Any]) -> None:
                emit_system_log(
                    "ingestion",
                    "titling_progress",
                    info,
                    correlation_id=correlation_id,
                )

            chunks = await asyncio.to_thread(
                link_tables_to_titles, raw_chunks, _titling_progress
            )
            emit(
                "titling",
                "completed",
                current=len(chunks),
                total=len(chunks),
                detail=f"Enriched {len(chunks)} chunks with section titles",
            )
            record_trace_event(
                correlation_id,
                "IngestDocument",
                "processing",
                {"chunks_found": len(chunks)},
            )
            emit_system_log(
                "ingestion",
                "document_chunked",
                {
                    "document_id": str(doc_id),
                    "policy_id": policy_id,
                    "chunk_count": len(chunks),
                    "chunking_strategy": "markdown_structure+table_title_linker",
                },
                correlation_id=correlation_id,
            )
            chunk_start = time.perf_counter()

            emit("embedding", "running")
            emit("storing", "running")
            inserted_count = 0
            total_chunks = len(chunks)
            logged_chunks: list[dict[str, Any]] = []
            for idx, chunk_dict in enumerate(chunks):
                chunk_text = chunk_dict.get("text", "")
                if not chunk_text:
                    continue

                c_hash = compute_chunk_hash(chunk_text)
                # Record chunk pre-check
                record_trace_event(
                    correlation_id,
                    "IngestDocument:Chunk",
                    "precheck",
                    {"chunk_index": idx, "content_hash": c_hash},
                )
                if await self._vector_store.chunk_exists(c_hash):
                    record_trace_event(
                        correlation_id,
                        "IngestDocument:Chunk",
                        "skipped",
                        {"chunk_index": idx, "reason": "already_exists", "content_hash": c_hash},
                    )
                    continue

                embedding = await self._embedder.embed(chunk_text)
                emit(
                    "embedding",
                    "progress",
                    current=min(idx + 1, total_chunks),
                    total=total_chunks,
                    detail=f"Vectorizing chunk {idx + 1} of {total_chunks}",
                )

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
                logged_chunks.append(
                    {
                        "chunk_id": str(cited_chunk.chunk_id),
                        "section": cited_chunk.section,
                        "page": cited_chunk.page,
                        "chunk_type": cited_chunk.chunk_type,
                        "content_hash": c_hash,
                        "text": chunk_text,
                    }
                )
                emit(
                    "storing",
                    "progress",
                    current=min(idx + 1, total_chunks),
                    total=total_chunks,
                    detail=f"Saving chunk {idx + 1} of {total_chunks} to the database",
                )
                record_trace_event(
                    correlation_id,
                    "IngestDocument:Chunk",
                    "upserted",
                    {"chunk_index": idx, "chunk_id": str(cited_chunk.chunk_id), "content_hash": c_hash},
                )

            emit("embedding", "completed", current=inserted_count, total=total_chunks,
                 detail=f"Generated {inserted_count} vector embeddings")
            emit("storing", "completed", current=inserted_count, total=total_chunks,
                 detail=f"Saved {inserted_count} chunk{'' if inserted_count == 1 else 's'} to the vector database")

            emit("finalizing", "running")
            await self._document_repo.save_document_status(doc_id, "success")
            emit("finalizing", "completed",
                 detail=f"Document marked as ingested in {time.perf_counter() - chunk_start:.2f}s")
            emit_system_log(
                "ingestion",
                "document_completed",
                {
                    "document_id": str(doc_id),
                    "inserted_count": inserted_count,
                    "skipped_count": total_chunks - inserted_count,
                    "duration_s": round(time.perf_counter() - chunk_start, 3),
                },
                correlation_id=correlation_id,
            )
            record_trace_event(
                correlation_id,
                "IngestDocument",
                "completed",
                {"document_id": str(doc_id), "chunks_count": total_chunks, "inserted_count": inserted_count},
            )
            append_chunk_log(
                {
                    "correlation_id": str(correlation_id),
                    "document_id": str(doc_id),
                    "filename": filename or Path(file_path).name,
                    "policy_id": policy_id,
                    "policy_type": policy_type,
                    "version": version,
                    "effective_date": effective_date.isoformat(),
                    "status": "success",
                    "chunks_count": total_chunks,
                    "inserted_count": inserted_count,
                },
                logged_chunks,
            )
            write_document_chunks(
                doc_id,
                {
                    "filename": filename or Path(file_path).name,
                    "policy_id": policy_id,
                    "policy_type": policy_type,
                    "version": version,
                    "effective_date": effective_date.isoformat(),
                    "status": "success",
                    "chunks_count": total_chunks,
                    "inserted_count": inserted_count,
                },
                logged_chunks,
            )
            return {
                "status": "success",
                "document_id": str(doc_id),
                "chunks_count": total_chunks,
                "inserted_count": inserted_count,
                "correlation_id": str(correlation_id),
            }
        except Exception as e:
            logger.error(f"Ingestion processing failed for {file_path}: {e}", exc_info=True)
            emit("finalizing", "failed", detail=f"Pipeline failed: {e}")
            record_trace_event(correlation_id, "IngestDocument", "error", {"error": str(e)})
            await self._document_repo.save_document_status(doc_id, "failed")
            return {"status": "failed", "error": str(e), "correlation_id": str(correlation_id)}
