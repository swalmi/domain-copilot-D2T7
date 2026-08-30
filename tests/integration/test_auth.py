from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db_session, require_role
from src.api.main import app
from src.api.routes.auth import hash_password
from src.infrastructure.config import get_settings
from src.infrastructure.db.models import Base, UserModel

stub_router = APIRouter(prefix="/test-auth-stub", tags=["TestStub"])


@stub_router.get("/handler-only", dependencies=[Depends(require_role("claims_handler"))])
async def handler_only_endpoint() -> dict[str, str]:
    """Protected endpoint accessible only to claims_handler role."""
    return {"message": "Welcome Claims Handler"}


@stub_router.get("/adjuster-only", dependencies=[Depends(require_role("adjuster"))])
async def adjuster_only_endpoint() -> dict[str, str]:
    """Protected endpoint accessible only to adjuster role."""
    return {"message": "Welcome Adjuster"}


app.include_router(stub_router)
client = TestClient(app)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Fixture providing an active AsyncSession connected to the database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
    )



    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def setup_auth_db(db_session: AsyncSession) -> None:
    """Fixture seeding test user accounts into database for auth tests."""
    handler_user = UserModel(
        email="test_handler@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="claims_handler",
    )
    adjuster_user = UserModel(
        email="test_adjuster@domaincopilot.com",
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


def test_auth_login_sets_cookie_and_role_protection() -> None:
    """Test full login, cookie setting, 401 missing cookie, and 403 wrong role authorization."""
    # 1. Access protected route without cookie -> 401 Unauthorized
    res = client.get("/test-auth-stub/handler-only")
    assert res.status_code == 401

    # 2. Login as claims_handler -> 200 OK and access_token cookie set
    login_res = client.post(
        "/auth/login",
        json={"email": "test_handler@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.cookies

    # 3. Call handler-only endpoint with handler cookie -> 200 OK
    res_handler = client.get("/test-auth-stub/handler-only")
    assert res_handler.status_code == 200
    assert res_handler.json()["message"] == "Welcome Claims Handler"

    # 4. Call adjuster-only endpoint with handler cookie -> 403 Forbidden
    res_adjuster = client.get("/test-auth-stub/adjuster-only")
    assert res_adjuster.status_code == 403

    # 5. Logout -> 200 OK
    logout_res = client.post("/auth/logout")
    assert logout_res.status_code == 200
