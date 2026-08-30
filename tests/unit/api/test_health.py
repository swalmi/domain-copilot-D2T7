from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.deps import get_db_session
from src.api.main import app

client = TestClient(app)


def test_liveness_endpoint_returns_200() -> None:
    """Verify that GET /health always returns HTTP 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_success() -> None:
    """Verify that GET /ready returns 200 when database and redis checks succeed."""
    mock_session = AsyncMock()
    mock_session.execute.return_value = None

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db_session] = mock_get_db

    with patch("redis.asyncio.from_url") as mock_redis_from_url:
        mock_redis_client = AsyncMock()
        mock_redis_client.ping.return_value = True
        mock_redis_from_url.return_value = mock_redis_client

        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["redis"] == "ok"

    app.dependency_overrides.clear()


def test_readiness_endpoint_db_failure() -> None:
    """Verify that GET /ready returns 503 when database execution fails."""
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB Connection Refused")

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db_session] = mock_get_db

    with patch("redis.asyncio.from_url") as mock_redis_from_url:
        mock_redis_client = AsyncMock()
        mock_redis_client.ping.return_value = True
        mock_redis_from_url.return_value = mock_redis_client

        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "failed" in data["checks"]["database"]

    app.dependency_overrides.clear()


def test_readiness_endpoint_redis_failure() -> None:
    """Verify that GET /ready returns 503 when redis connection fails."""
    mock_session = AsyncMock()
    mock_session.execute.return_value = None

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db_session] = mock_get_db

    with patch("redis.asyncio.from_url") as mock_redis_from_url:
        mock_redis_client = AsyncMock()
        mock_redis_client.ping.side_effect = Exception("Redis Unavailable")
        mock_redis_from_url.return_value = mock_redis_client

        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "failed" in data["checks"]["redis"]

    app.dependency_overrides.clear()
