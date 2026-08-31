import pytest_asyncio
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db_session, require_role
from src.api.main import app
from src.api.routes.auth import hash_password
from src.infrastructure.db.models import Base, UserModel

stub_router = APIRouter(prefix="/test-auth-stub", tags=["TestStub"])


@stub_router.get("/client-only", dependencies=[Depends(require_role("client"))])
async def client_only_endpoint() -> dict[str, str]:
    """Protected endpoint accessible only to client role."""
    return {"message": "Welcome Client"}


@stub_router.get("/corp-only", dependencies=[Depends(require_role("corp"))])
async def corp_only_endpoint() -> dict[str, str]:
    """Protected endpoint accessible only to corp role."""
    return {"message": "Welcome Corp"}


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
        role="client",
    )
    adjuster_user = UserModel(
        email="test_adjuster@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="corp",
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
    res = client.get("/test-auth-stub/client-only")
    assert res.status_code == 401

    # 2. Login as claims_handler -> 200 OK and access_token cookie set
    login_res = client.post(
        "/auth/login",
        json={"email": "test_handler@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.cookies

    # 3. Call client-only endpoint with client cookie -> 200 OK
    res_client = client.get("/test-auth-stub/client-only")
    assert res_client.status_code == 200
    assert res_client.json()["message"] == "Welcome Client"

    # 4. Call corp-only endpoint with client cookie -> 403 Forbidden
    res_corp = client.get("/test-auth-stub/corp-only")
    assert res_corp.status_code == 403

    # 5. Logout -> 200 OK
    logout_res = client.post("/auth/logout")
    assert logout_res.status_code == 200


def test_auth_me_returns_profile() -> None:
    """Test GET /auth/me returns the authenticated user's profile."""
    client.post(
        "/auth/login",
        json={"email": "test_adjuster@domaincopilot.com", "password": "Pass123!"},
    )
    res = client.get("/auth/me")
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "test_adjuster@domaincopilot.com"
    assert body["role"] == "corp"
    client.post("/auth/logout")


def test_auth_signup_creates_user_and_sets_cookie() -> None:
    """Test POST /auth/signup registers a new user, hashes password, and sets session cookie."""
    res = client.post(
        "/auth/signup",
        json={
            "email": "new_client@domaincopilot.com",
            "password": "StrongPass99!",
            "role": "client",
        },
    )
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "client"
    assert "access_token" in res.cookies

    # Duplicate email -> 409 conflict
    dup = client.post(
        "/auth/signup",
        json={
            "email": "new_client@domaincopilot.com",
            "password": "StrongPass99!",
            "role": "corp",
        },
    )
    assert dup.status_code == 409
    client.post("/auth/logout")
