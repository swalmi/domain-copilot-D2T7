import uuid
from datetime import date
from io import BytesIO
from unittest.mock import AsyncMock

import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import (
    get_ask_question_use_case,
    get_db_session,
    get_ingest_document_use_case,
)
from src.api.main import app
from src.api.routes.auth import hash_password
from src.application.use_cases.ask_question import AskQuestionUseCase
from src.application.use_cases.ingest_document import IngestDocumentUseCase
from src.infrastructure.db.models import Base, ChunkModel, DocumentModel, UserModel

client = TestClient(app)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Fixture providing an active AsyncSession connected to SQLite in-memory database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_environment(db_session: AsyncSession) -> None:
    """Fixture seeding test user and overriding FastAPI database dependency."""
    user = UserModel(
        email="test_handler@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="corp",
    )
    db_session.add(user)
    await db_session.commit()

    async def mock_get_db():
        yield db_session

    mock_ingest_case = AsyncMock(spec=IngestDocumentUseCase)
    mock_ingest_case.execute.return_value = {
        "status": "success",
        "document_id": "11111111-1111-1111-1111-111111111111",
        "chunks_count": 2,
        "inserted_count": 2,
    }

    async def mock_execute_stream(*args, **kwargs):
        yield {"type": "token", "content": "Water damage is covered up to $10,000 policy limit."}
        yield {
            "type": "done",
            "citations": [
                {
                    "chunk_id": "22222222-2222-2222-2222-222222222222",
                    "text_snippet": "Water damage coverage terms",
                    "source": "sample_policy.txt",
                    "section": "Section II - Coverage",
                    "page": 3,
                    "policy_id": "POL-1001",
                    "version": "v1",
                }
            ],
            "refused": False,
        }

    mock_ask_case = AsyncMock(spec=AskQuestionUseCase)
    mock_ask_case.execute_stream.side_effect = mock_execute_stream

    app.dependency_overrides[get_db_session] = mock_get_db
    app.dependency_overrides[get_ingest_document_use_case] = lambda: mock_ingest_case
    app.dependency_overrides[get_ask_question_use_case] = lambda: mock_ask_case

    yield
    app.dependency_overrides.clear()


def test_documents_and_ask_routes_flow() -> None:
    """Test full flow: login, upload document, list documents, ask question with cited answer."""
    # 1. Login
    login_res = client.post(
        "/auth/login",
        json={"email": "test_handler@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200

    # 2. Upload Document POST /documents
    file_data = BytesIO(b"Sample policy text content for testing Q&A.")
    upload_res = client.post(
        "/documents",
        files={"file": ("sample_policy.txt", file_data, "text/plain")},
        data={
            "policy_id": "POL-1001",
            "policy_type": "home",
            "version": "v1",
            "effective_date": "2026-01-01",
        },
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["status"] == "success"

    # 3. List Documents GET /documents
    list_res = client.get("/documents")
    assert list_res.status_code == 200
    assert isinstance(list_res.json(), list)

    # 4. Ask Question POST /ask (SSE Streaming Response)
    ask_res = client.post(
        "/ask",
        json={
            "query": "Is water damage covered?",
            "policy_id": "POL-1001",
            "policy_type": "home",
        },
    )
    assert ask_res.status_code == 200
    assert "text/event-stream" in ask_res.headers["content-type"]
    sse_text = ask_res.text
    assert 'data: {"token": "Water damage is covered up to $10,000 policy limit."}' in sse_text
    assert "data: [DONE]" in sse_text
    assert "POL-1001" in sse_text



@pytest_asyncio.fixture
async def seeded_policy_document(db_session: AsyncSession) -> uuid.UUID:
    """Insert one document plus chunk rows carrying a policy id and payload."""
    # Must contain hex letters: SQLite gives the UUID column NUMERIC affinity,
    # and an all-digit id would be coerced to a real and break the round trip.
    doc_id = uuid.UUID("33333333-3333-4333-8333-33333333abce")
    db_session.add(
        DocumentModel(
            id=doc_id,
            filename="iso-pp-00-01.txt",
            content_hash="hash-list-documents-regression",
            status="success",
        )
    )
    for index in range(3):
        db_session.add(
            ChunkModel(
                document_id=doc_id,
                policy_id="ISO-PP-00-01",
                policy_type="home",
                version="v1",
                effective_date=date(2026, 1, 1),
                section=f"SECTION {index}",
                chunk_type="narrative",
                page=index + 1,
                text=f"coverage wording {index} " * 40,
                content_hash=f"chunk-hash-regression-{index}",
                embedding=[0.1] * 768,
            )
        )
    await db_session.commit()
    return doc_id


def test_list_documents_maps_policy_id_without_loading_chunk_payload(
    seeded_policy_document: uuid.UUID,
    db_session: AsyncSession,
) -> None:
    """GET /documents must resolve policy_id without selecting chunk payloads.

    The endpoint originally eager-loaded every chunk row (text plus a 768-d
    embedding) just to read one policy_id, which cost seconds on a seeded
    corpus. This guards both the response shape and the query shape.
    """
    statements: list[str] = []

    def _record(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        statements.append(statement)

    bind = db_session.bind
    sync_engine = getattr(bind, "sync_engine", bind)
    event.listen(sync_engine, "before_cursor_execute", _record)
    try:
        res = client.get("/documents")
    finally:
        event.remove(sync_engine, "before_cursor_execute", _record)

    assert res.status_code == 200
    payload = res.json()
    assert isinstance(payload, list)

    seeded = next(
        (doc for doc in payload if doc["id"] == str(seeded_policy_document)), None
    )
    assert seeded is not None, "seeded document missing from the listing"
    assert seeded["policy_id"] == "ISO-PP-00-01"

    heavy = [
        statement
        for statement in statements
        if "chunks.text" in statement or "chunks.embedding" in statement
    ]
    assert heavy == [], "listing must not pull chunk text/embeddings"
