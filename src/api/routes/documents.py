import asyncio
import json
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import (
    UserPayload,
    get_db_session,
    get_document_repository,
    get_ingest_document_use_case,
    require_role,
)
from src.application.use_cases.ingest_document import IngestDocumentUseCase
from src.domain.interfaces.document_repository import DocumentRepository
from src.infrastructure.db.models import DocumentModel
from src.infrastructure.observability.document_chunk_store import delete_document_chunks
from src.infrastructure.observability.system_logger import emit_system_log

router = APIRouter(prefix="/documents", tags=["Documents"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB limit
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def validate_uploaded_file(filename: str, contents: bytes) -> None:
    """Validate upload size, file extension, and magic-byte signatures for security."""
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum permitted limit of 10MB.",
        )

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format '{suffix}'. Only .pdf, .docx, and .txt files are permitted.",
        )

    # Magic byte signature sniffing
    if suffix == ".pdf" and not contents.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file content signature: File content does not match PDF magic bytes.",
        )
    if suffix == ".docx" and not contents.startswith(b"PK\x03\x04"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file content signature: File content does not match DOCX magic bytes.",
        )


@router.post("", status_code=status.HTTP_200_OK)
async def upload_document(
    file: UploadFile = File(...),
    policy_id: str = Form("POL-1001"),
    policy_type: str = Form("home"),
    version: str = Form("v1"),
    effective_date: date = Form(default_factory=date.today),
    current_user: UserPayload = Depends(require_role("corp")),
    ingest_use_case: IngestDocumentUseCase = Depends(get_ingest_document_use_case),
) -> dict[str, Any]:
    """Upload and synchronously ingest policy document file into vector database with validation."""
    contents = await file.read()
    validate_uploaded_file(file.filename or "document.pdf", contents)

    file_suffix = Path(file.filename or "uploaded.pdf").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    original_filename = file.filename or Path(tmp_path).name

    try:
        result = await ingest_use_case.execute(
            file_path=tmp_path,
            policy_id=policy_id,
            policy_type=policy_type,
            version=version,
            effective_date=effective_date,
            filename=original_filename,
        )
        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/stream", status_code=status.HTTP_200_OK)
async def upload_document_stream(
    file: UploadFile = File(...),
    policy_id: str = Form("POL-1001"),
    policy_type: str = Form("home"),
    version: str = Form("v1"),
    effective_date: date = Form(default_factory=date.today),
    current_user: UserPayload = Depends(require_role("corp")),
    ingest_use_case: IngestDocumentUseCase = Depends(get_ingest_document_use_case),
) -> StreamingResponse:
    """Ingest a policy document streaming per-stage progress via Server-Sent Events.

    Contract: each stage transitions with ``data: {"step": ..., "status": ...}``
    (status: running | progress | completed | failed), followed by a final
    ``data: {"done": true, "result": {...}}`` and a ``data: [DONE]`` terminator.
    This drives the Jenkins-style green-check pipeline in the frontend.
    """
    contents = await file.read()
    validate_uploaded_file(file.filename or "document.pdf", contents)

    file_suffix = Path(file.filename or "uploaded.pdf").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    original_filename = file.filename or Path(tmp_path).name

    async def sse_event_generator() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def run_pipeline() -> None:
            try:
                result = await ingest_use_case.execute(
                    file_path=tmp_path,
                    policy_id=policy_id,
                    policy_type=policy_type,
                    version=version,
                    effective_date=effective_date,
                    on_progress=lambda event: queue.put_nowait(event),
                    filename=original_filename,
                )
                await queue.put_nowait({"done": True, "result": result})
            except Exception as exc:
                await queue.put_nowait(
                    {"done": True, "error": str(exc), "result": {"status": "failed"}}
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        pipeline_task = asyncio.create_task(run_pipeline())
        try:
            finished = False
            while not finished:
                event = await queue.get()
                finished = bool(event.get("done"))
                yield f"data: {json.dumps(event, default=str)}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            pipeline_task.cancel()

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


@router.get("", status_code=status.HTTP_200_OK)
async def list_documents(
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retrieve list of all uploaded policy documents with processing status."""
    stmt = (
        select(DocumentModel)
        .options(selectinload(DocumentModel.chunks))
        .order_by(DocumentModel.created_at.desc())
    )
    res = await session.execute(stmt)
    documents = res.scalars().all()

    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "policy_id": doc.chunks[0].policy_id if doc.chunks else None,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in documents
    ]


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    document_repo: DocumentRepository = Depends(get_document_repository),
    _current_user: UserPayload = Depends(require_role("corp")),
) -> dict[str, Any]:
    """Remove a policy document from the knowledge base entirely.

    Cascades the deletion of all its chunks (and their fingerprints) so the
    document can no longer be hit by retrieval or deduplicated against.
    """
    stmt = (
        select(DocumentModel)
        .options(selectinload(DocumentModel.chunks))
        .where(DocumentModel.id == document_id)
    )
    res = await session.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found. It may already have been removed.",
        )

    deleted = await document_repo.delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found. It may already have been removed.",
        )

    emit_system_log(
        "ingestion",
        "document_deleted",
        {
            "document_id": str(document_id),
            "policy_id": doc.chunks[0].policy_id if doc.chunks else None,
            "chunks_removed": len(doc.chunks),
        },
    )
    delete_document_chunks(document_id)
    return {"deleted": True, "document_id": str(document_id)}
