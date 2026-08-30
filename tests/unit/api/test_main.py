from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_docs_page_loads() -> None:
    """Verify that FastAPI automatic OpenAPI UI (/docs) loads successfully."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "html" in response.headers["content-type"]


def test_openapi_json_schema() -> None:
    """Verify OpenAPI schema title matches Domain Copilot configuration."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Domain Copilot"


def test_health_check_endpoint() -> None:
    """Verify system health check route returns OK status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

