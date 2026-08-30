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
    """Fixture seeding claims_handler and adjuster user accounts."""
    handler_user = UserModel(
        email="handler@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="claims_handler",
    )
    adjuster_user = UserModel(
        email="adjuster@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="adjuster",
    )
    db_session.add(handler_user)
    db_session.add(adjuster_user)
    await db_session.commit()

    async def mock_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = mock_get_db
    yield
    app.dependency_overrides.clear()


def test_approval_gate_rbac_enforcement() -> None:
    """Verify claims_handler is blocked (403) and adjuster can list and approve claims (200)."""
    # 1. Login as claims_handler and try to approve an unapproved claim -> 403 Forbidden
    client.post(
        "/auth/login",
        json={"email": "handler@domaincopilot.com", "password": "Pass123!"},
    )

    approve_attempt = client.post("/approvals/11111111-1111-1111-1111-111111111111/approve")
    assert approve_attempt.status_code == 403

    # Logout handler
    client.post("/auth/logout")

    # 2. Login as adjuster
    adjuster_login = client.post(
        "/auth/login",
        json={"email": "adjuster@domaincopilot.com", "password": "Pass123!"},
    )
    assert adjuster_login.status_code == 200

    # 3. List pending approvals as adjuster -> 200 OK
    list_res = client.get("/approvals")
    assert list_res.status_code == 200
    assert isinstance(list_res.json(), list)

    # 4. Submit claim and approve as adjuster -> 200 OK
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

    approve_res = client.post(f"/approvals/{created_claim_id}/approve")
    assert approve_res.status_code == 200
    assert approve_res.json()["decision"] == "approved"

    # Verify claim status updated to approved
    claim_status_res = client.get(f"/claims/{created_claim_id}")
    assert claim_status_res.status_code == 200
    assert claim_status_res.json()["status"] == "approved"
