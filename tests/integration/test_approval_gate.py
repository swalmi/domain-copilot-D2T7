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
    """Fixture seeding client and corp user accounts."""
    client_user = UserModel(
        email="client@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="client",
    )
    corp_user = UserModel(
        email="corp@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="corp",
    )
    db_session.add(client_user)
    db_session.add(corp_user)
    await db_session.commit()

    async def mock_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = mock_get_db
    yield
    app.dependency_overrides.clear()


@patch("src.api.routes.claims.process_claim_adjudication.delay")
def test_approval_gate_rbac_enforcement(mock_task_delay: MagicMock) -> None:
    """Verify client can submit claims but is blocked (403) from approvals, and corp can approve."""
    mock_task_delay.return_value.id = "celery-approval-task-123"

    # 1. Login as client and submit a claim -> 202 Accepted
    client.post(
        "/auth/login",
        json={"email": "client@domaincopilot.com", "password": "Pass123!"},
    )
    submit_res = client.post(
        "/claims",
        json={
            "policy_number": "POL-9999",
            "date_of_loss": "2026-04-10",
            "incident_description": "Storm damage to roof",
            "claim_amount_requested": "12000.00",
        },
    )
    assert submit_res.status_code == 202
    created_claim_id = submit_res.json()["claim_id"]

    # 2. Client tries to approve -> 403 Forbidden
    approve_attempt = client.post(f"/approvals/{created_claim_id}/approve")
    assert approve_attempt.status_code == 403

    # Logout client
    client.post("/auth/logout")

    # 3. Login as corp
    corp_login = client.post(
        "/auth/login",
        json={"email": "corp@domaincopilot.com", "password": "Pass123!"},
    )
    assert corp_login.status_code == 200

    # 4. List pending approvals as corp -> 200 OK
    list_res = client.get("/approvals")
    assert list_res.status_code == 200
    assert isinstance(list_res.json(), list)

    # 5. Approve the submitted claim as corp -> 200 OK
    approve_res = client.post(f"/approvals/{created_claim_id}/approve")
    assert approve_res.status_code == 200
    assert approve_res.json()["decision"] == "approved"

    # Verify claim status updated to approved
    claim_status_res = client.get(f"/claims/{created_claim_id}")
    assert claim_status_res.status_code == 200
    assert claim_status_res.json()["status"] == "approved"
