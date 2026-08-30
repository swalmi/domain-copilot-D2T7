from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_ask_question_use_case, get_db_session
from src.api.main import app
from src.api.routes.auth import hash_password
from src.application.use_cases.ask_question import AskQuestionUseCase
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
async def setup_sse_test_env(db_session: AsyncSession) -> None:
    """Fixture seeding test user and overriding AskQuestionUseCase with streaming tokens."""
    user = UserModel(
        email="sse_user@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="claims_handler",
    )
    db_session.add(user)
    await db_session.commit()

    async def mock_get_db():
        yield db_session

    async def mock_execute_stream(*args, **kwargs):
        yield {"type": "token", "content": "Token1 "}
        yield {"type": "token", "content": "Token2 "}
        yield {"type": "token", "content": "Token3"}
        yield {
            "type": "done",
            "citations": [
                {
                    "chunk_id": "33333333-3333-3333-3333-333333333333",
                    "source": "policy_doc.pdf",
                    "section": "Exclusions",
                    "page": 12,
                    "policy_id": "POL-2002",
                }
            ],
            "refused": False,
        }

    mock_ask_case = AsyncMock(spec=AskQuestionUseCase)
    mock_ask_case.execute_stream.side_effect = mock_execute_stream

    app.dependency_overrides[get_db_session] = mock_get_db
    app.dependency_overrides[get_ask_question_use_case] = lambda: mock_ask_case

    yield
    app.dependency_overrides.clear()


def test_sse_token_streaming_endpoint() -> None:
    """Verify POST /ask returns text/event-stream with incremental tokens and final [DONE] payload."""
    login_res = client.post(
        "/auth/login",
        json={"email": "sse_user@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200

    res = client.post(
        "/ask",
        json={"query": "What are the exclusion details?"},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    sse_lines = res.text.strip().split("\n\n")
    assert len(sse_lines) >= 4
    assert sse_lines[0] == "data: Token1 "
    assert sse_lines[1] == "data: Token2 "
    assert sse_lines[2] == "data: Token3"
    assert sse_lines[3].startswith("data: [DONE]")
    assert "POL-2002" in sse_lines[3]
