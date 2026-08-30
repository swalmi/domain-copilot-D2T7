import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.infrastructure.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness_check() -> dict[str, str]:
    """Return HTTP 200 status indicating that the application process is live."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check(
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Check connections to PostgreSQL database and Redis cache, returning 200 if healthy or 503 on failure."""
    checks: dict[str, Any] = {"database": "ok", "redis": "ok"}
    is_healthy = True

    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Readiness check failed for PostgreSQL: %s", exc)
        checks["database"] = f"failed: {exc}"
        is_healthy = False

    settings = get_settings()
    redis_client = None
    try:
        redis_client = redis.from_url(settings.redis_url, socket_connect_timeout=2.0)
        await redis_client.ping()
    except Exception as exc:
        logger.warning("Readiness check failed for Redis: %s", exc)
        checks["redis"] = f"failed: {exc}"
        is_healthy = False
    finally:
        if redis_client:
            await redis_client.aclose()

    if is_healthy:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "checks": checks},
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "unhealthy", "checks": checks},
    )
