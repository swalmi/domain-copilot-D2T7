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
        email="cancel_user@domaincopilot.com",
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


@patch("src.api.routes.claims.celery_app.control.revoke")
@patch("src.api.routes.claims.process_claim_adjudication.delay")
def test_cancel_claim_route_and_task_revocation(
    mock_task_delay: MagicMock, mock_celery_revoke: MagicMock
) -> None:
    """Test POST /claims/{id}/cancel revokes Celery task and sets claim status to cancelled."""
    mock_task_delay.return_value.id = "celery-revoke-task-999"

    # 1. Login
    login_res = client.post(
        "/auth/login",
        json={"email": "cancel_user@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200

    # 2. Submit claim
    payload = {
        "policy_number": "POL-7777",
        "date_of_loss": "2026-05-01",
        "incident_description": "Hail damage to vehicle roof",
        "claim_amount_requested": "4500.00",
    }
    submit_res = client.post("/claims", json=payload)
    assert submit_res.status_code == 202
    claim_id = submit_res.json()["claim_id"]

    # 3. Cancel claim
    cancel_res = client.post(f"/claims/{claim_id}/cancel")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["status"] == "success"
    assert cancel_data["claim_status"] == "cancelled"
    mock_celery_revoke.assert_called_once_with("celery-revoke-task-999", terminate=True)

    # 4. Verify status in GET /claims/{id}
    status_res = client.get(f"/claims/{claim_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "cancelled"
