from datetime import date, datetime, timezone
import uuid

from src.infrastructure.db.models import ChunkModel, DocumentModel


def test_document_model_instantiation() -> None:
    """Verify DocumentModel attributes and table name."""
    doc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    doc = DocumentModel(
        id=doc_id,
        filename="policy.pdf",
        content_hash="abc123hash",
        status="PROCESSED",
        created_at=now,
    )

    assert doc.__tablename__ == "documents"
    assert doc.id == doc_id
    assert doc.filename == "policy.pdf"
    assert doc.content_hash == "abc123hash"
    assert doc.status == "PROCESSED"
    assert doc.created_at == now


def test_chunk_model_instantiation() -> None:
    """Verify ChunkModel attributes and table name."""
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    eff_date = date(2026, 1, 1)
    chunk = ChunkModel(
        id=chunk_id,
        document_id=doc_id,
        policy_id="POL-100",
        policy_type="home",
        version="1.0",
        effective_date=eff_date,
        section="SECTION I",
        chunk_type="narrative",
        page=1,
        text="Coverage terms text.",
        content_hash="chunkhash456",
        embedding=[0.1] * 768,
    )

    assert chunk.__tablename__ == "chunks"
    assert chunk.id == chunk_id
    assert chunk.document_id == doc_id
    assert chunk.policy_id == "POL-100"
    assert chunk.policy_type == "home"
    assert chunk.version == "1.0"
    assert chunk.effective_date == eff_date
    assert chunk.section == "SECTION I"
    assert chunk.chunk_type == "narrative"
    assert chunk.page == 1
    assert chunk.text == "Coverage terms text."
    assert chunk.content_hash == "chunkhash456"
    assert len(chunk.embedding) == 768
