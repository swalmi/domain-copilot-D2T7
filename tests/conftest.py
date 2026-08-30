import pytest
from src.api.main import app


@pytest.fixture(autouse=True)
def disable_rate_limiter() -> None:
    """Disable rate limiting during automated test suite execution to prevent 429 collisions."""
    app.state.limiter.enabled = False
    yield
    app.state.limiter.enabled = True
