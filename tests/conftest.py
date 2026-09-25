import os
import socket

import pytest


def _resolves(host: str) -> bool:
    try:
        socket.gethostbyname(host)
        return True
    except OSError:
        return False


def _load_dotenv_kv(path: str) -> dict[str, str]:
    kv: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                kv[key.strip()] = value.strip()
    except OSError:
        pass
    return kv


# Rewrite Docker service hostnames (db/redis/ollama) to localhost when running the
# suite on the host, where those names do not resolve. Real env vars take
# precedence over .env in pydantic-settings, so exporting here is enough — but it
# must happen BEFORE any src.* import (celery_app captures settings at import time).
_ENV_KV = _load_dotenv_kv(os.path.join(os.path.dirname(__file__), "..", ".env"))
for _key, _host in (
    ("DATABASE_URL", "db"),
    ("REDIS_URL", "redis"),
    ("OLLAMA_BASE_URL", "ollama"),
):
    _value = os.environ.get(_key) or _ENV_KV.get(_key)
    if _value and not _resolves(_host):
        _value = (
            _value.replace(f"@{_host}:", "@localhost:").replace(f"//{_host}:", "//localhost:")
        )
        os.environ[_key] = _value

from src.api.limiter import limiter  # noqa: E402
from src.api.main import app  # noqa: E402

import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Dedicated scratch database for tests that INSERT/TRUNCATE corpus tables, so the
# seeded demo corpus in `domain_copilot` survives a full `pytest` run.
TEST_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/domain_copilot_test"
ADMIN_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"


@pytest_asyncio.fixture
async def isolated_db_session() -> AsyncSession:
    """Session on a scratch database with schema ready and corpus tables emptied.

    Creates `domain_copilot_test` on first use, ensures the pgvector extension and
    all tables exist, and truncates documents/chunks before and after each test.
    """
    admin = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'domain_copilot_test'")
        )
        if exists.scalar() is None:
            await conn.execute(text("CREATE DATABASE domain_copilot_test"))
    await admin.dispose()

    from src.infrastructure.db.models import Base

    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        await session.execute(text("TRUNCATE TABLE chunks, documents CASCADE;"))
        await session.commit()
        yield session
        await session.execute(text("TRUNCATE TABLE chunks, documents CASCADE;"))
        await session.commit()
    await engine.dispose()


@pytest.fixture(autouse=True)
def disable_rate_limiter() -> None:
    """Disable rate limiting during automated test suite execution to prevent 429 collisions."""
    app.state.limiter.enabled = False
    limiter.enabled = False
    yield
    app.state.limiter.enabled = True
    limiter.enabled = True
