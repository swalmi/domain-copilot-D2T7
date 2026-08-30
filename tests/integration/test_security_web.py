from io import BytesIO

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
        email="sec_user@domaincopilot.com",
        hashed_password=hash_password("Pass123!"),
        role="claims_handler",
    )
    db_session.add(user)
    await db_session.commit()

    async def mock_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = mock_get_db
    yield
    app.dependency_overrides.clear()


def test_security_headers_present_in_responses() -> None:
    """Verify OWASP recommended security headers are present in HTTP responses."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "max-age=31536000" in res.headers["Strict-Transport-Security"]


def test_upload_validation_rejects_renamed_executable() -> None:
    """Verify POST /documents rejects an executable file renamed as a PDF."""
    # Login first
    login_res = client.post(
        "/auth/login",
        json={"email": "sec_user@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200

    # Fake executable file with MZ signature renamed as pdf
    exe_bytes = BytesIO(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xffFake EXE Payload")

    res = client.post(
        "/documents",
        files={"file": ("malicious_doc.pdf", exe_bytes, "application/pdf")},
        data={"policy_id": "POL-1001", "policy_type": "home", "version": "v1"},
    )
    assert res.status_code == 400
    assert "Invalid file content signature" in res.json()["detail"]


def test_upload_validation_accepts_valid_text_document() -> None:
    """Verify POST /documents accepts text file with valid content and extension."""
    login_res = client.post(
        "/auth/login",
        json={"email": "sec_user@domaincopilot.com", "password": "Pass123!"},
    )
    assert login_res.status_code == 200

    valid_text_bytes = BytesIO(b"SECTION I - COVERAGE\nSample policy terms for testing upload validation.")

    res = client.post(
        "/documents",
        files={"file": ("valid_policy.txt", valid_text_bytes, "text/plain")},
        data={"policy_id": "POL-1001", "policy_type": "home", "version": "v1"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

