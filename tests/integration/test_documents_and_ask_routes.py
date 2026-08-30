from io import BytesIO
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest
import pytest_asyncio
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
from src.infrastructure.db.models import Base, UserModel

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
        role="claims_handler",
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

    mock_ask_case = AsyncMock(spec=AskQuestionUseCase)
    mock_ask_case.execute.return_value = {
        "answer": "Water damage is covered up to $10,000 policy limit.",
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

    # 4. Ask Question POST /ask
    ask_res = client.post(
        "/ask",
        json={
            "query": "Is water damage covered?",
            "policy_id": "POL-1001",
            "policy_type": "home",
        },
    )
    assert ask_res.status_code == 200
    data = ask_res.json()
    assert data["refused"] is False
    assert "Water damage is covered" in data["answer"]
    assert len(data["citations"]) == 1
    assert data["citations"][0]["policy_id"] == "POL-1001"
