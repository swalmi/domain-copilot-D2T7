from uuid import uuid4

from fastapi.testclient import TestClient
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db_session
from src.api.main import app
from src.api.routes.auth import hash_password
from src.infrastructure.db.models import Base, UserModel
from src.infrastructure.observability.trace_logger import record_trace_event

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
        email="trace_user@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="corp",
    )
    db_session.add(user)
    await db_session.commit()

    async def mock_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = mock_get_db
    yield
    app.dependency_overrides.clear()


def test_get_run_trace_events() -> None:
    """Test GET /runs/{correlation_id} returns sequential execution trace events."""
    # 1. Login
    login_res = client.post(
        "/auth/login",
        json={"email": "trace_user@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200

    # 2. Record trace events for correlation_id
    correlation_id = uuid4()
    record_trace_event(
        correlation_id=correlation_id,
        step_name="CoverageMatcher",
        event_type="input",
        payload={"claim_id": "111"},
    )
    record_trace_event(
        correlation_id=correlation_id,
        step_name="CoverageMatcher",
        event_type="output",
        payload={"confidence": "matched"},
    )
    record_trace_event(
        correlation_id=correlation_id,
        step_name="AdjudicationDrafter",
        event_type="decision",
        payload={"recommendation": "approve", "payout": "5000.00"},
    )

    # 3. GET /runs/{correlation_id}
    res = client.get(f"/runs/{correlation_id}")
    assert res.status_code == 200
    events = res.json()
    assert len(events) == 3
    assert events[0]["step_name"] == "CoverageMatcher"
    assert events[0]["event_type"] == "input"
    assert events[1]["event_type"] == "output"
    assert events[2]["step_name"] == "AdjudicationDrafter"
    assert events[2]["event_type"] == "decision"
