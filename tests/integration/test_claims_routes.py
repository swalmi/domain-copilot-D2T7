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


@patch("src.api.routes.claims.process_claim_adjudication.delay")
def test_claim_submission_is_idempotent_for_a_retried_key(
    mock_task_delay: MagicMock,
) -> None:
    """Retrying a submission with the same idempotency key must not double-dispatch.

    Twist T7: a client that never saw the 202 (timeout, retry) replays the same
    request and gets the original claim back — one row, one Celery job.
    """
    mock_task_delay.return_value.id = "celery-task-idem-0001"

    login_res = client.post(
        "/auth/login",
        json={"email": "claims_user@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200

    payload = {
        "policy_number": "POL-7777",
        "date_of_loss": "2026-04-01",
        "incident_description": "Hail damage to roof shingles.",
        "claim_amount_requested": "4200.00",
        "idempotency_key": "retry-key-2026-04-01",
    }

    first = client.post("/claims", json=payload)
    assert first.status_code == 202
    first_data = first.json()
    assert first_data["idempotent_replay"] is False

    second = client.post("/claims", json=payload)
    assert second.status_code == 202
    second_data = second.json()
    assert second_data["idempotent_replay"] is True
    assert second_data["claim_id"] == first_data["claim_id"]
    assert second_data["correlation_id"] == first_data["correlation_id"]

    # Header form: same key, same claim; a different key creates a new claim.
    header_res = client.post(
        "/claims",
        json={k: v for k, v in payload.items() if k != "idempotency_key"},
        headers={"Idempotency-Key": "retry-key-2026-04-01"},
    )
    assert header_res.status_code == 202
    assert header_res.json()["claim_id"] == first_data["claim_id"]

    other = client.post(
        "/claims",
        json={k: v for k, v in payload.items() if k != "idempotency_key"},
        headers={"Idempotency-Key": "retry-key-2026-04-02"},
    )
    assert other.status_code == 202
    assert other.json()["claim_id"] != first_data["claim_id"]

    # One job for the first submission; replays never re-dispatch.
    assert mock_task_delay.call_count == 2

    listed = client.get("/claims")
    assert listed.status_code == 200
    claim_ids = {c["id"] for c in listed.json()}
    assert first_data["claim_id"] in claim_ids
    assert other.json()["claim_id"] in claim_ids
