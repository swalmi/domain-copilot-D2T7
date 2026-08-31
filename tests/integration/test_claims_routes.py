from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db_session
from src.api.main import app
from src.api.routes.auth import hash_password
from src.infrastructure.db.models import Base, UserModel

client = TestClient(app)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Fixture providing active AsyncSession connected to SQLite in-memory database."""
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
async def setup_test_env(db_session: AsyncSession) -> None:
    """Fixture seeding test user and overriding database dependency."""
    user = UserModel(
        email="claims_user@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="client",
    )
    db_session.add(user)
    await db_session.commit()

    async def mock_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = mock_get_db
    yield
    app.dependency_overrides.clear()


@patch("src.api.routes.claims.process_claim_adjudication.delay")
def test_claims_async_submission_and_retrieval(mock_task_delay: MagicMock) -> None:
    """Test claim submission POST /claims returns HTTP 202 and GET /claims/{id} returns claim record."""
    mock_task_delay.return_value.id = "celery-task-uuid-12345"

    # 1. Login
    login_res = client.post(
        "/auth/login",
        json={"email": "claims_user@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200

    # 2. POST /claims
    payload = {
        "policy_number": "POL-5555",
        "date_of_loss": "2026-03-15",
        "incident_description": "Water leak caused damage to hardwood floors.",
        "claim_amount_requested": "7500.00",
    }
    submit_res = client.post("/claims", json=payload)
    assert submit_res.status_code == 202
    data = submit_res.json()
    assert "claim_id" in data
    assert data["task_id"] == "celery-task-uuid-12345"
    assert data["status"] == "pending"
    mock_task_delay.assert_called_once()

    claim_id = data["claim_id"]

    # 3. GET /claims/{id}
    get_res = client.get(f"/claims/{claim_id}")
    assert get_res.status_code == 200
    claim_data = get_res.json()
    assert claim_data["id"] == claim_id
    assert claim_data["policy_number"] == "POL-5555"
    assert claim_data["status"] == "submitted"
