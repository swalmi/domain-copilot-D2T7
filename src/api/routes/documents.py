from datetime import date
from pathlib import Path
import tempfile
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import (
    UserPayload,
    get_current_user,
    get_db_session,
    get_ingest_document_use_case,
)
from src.application.use_cases.ingest_document import IngestDocumentUseCase
from src.infrastructure.db.models import DocumentModel

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", status_code=status.HTTP_200_OK)
async def upload_document(
    file: UploadFile = File(...),
    policy_id: str = Form("POL-1001"),
    policy_type: str = Form("home"),
    version: str = Form("v1"),
    effective_date: date = Form(default_factory=date.today),
    current_user: UserPayload = Depends(get_current_user),
    ingest_use_case: IngestDocumentUseCase = Depends(get_ingest_document_use_case),
) -> dict[str, Any]:
    """Upload and synchronously ingest policy document file into vector database."""
    file_suffix = Path(file.filename or "uploaded.txt").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = await ingest_use_case.execute(
            file_path=tmp_path,
            policy_id=policy_id,
            policy_type=policy_type,
            version=version,
            effective_date=effective_date,
        )
        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.get("", status_code=status.HTTP_200_OK)
async def list_documents(
    session: AsyncSession = Depends(get_db_session),
    current_user: UserPayload = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Retrieve list of all uploaded policy documents with processing status."""
    stmt = select(DocumentModel).order_by(DocumentModel.created_at.desc())
    res = await session.execute(stmt)
    documents = res.scalars().all()

    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in documents
    ]
