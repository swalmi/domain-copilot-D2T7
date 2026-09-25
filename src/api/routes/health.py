import asyncio
import logging
from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.infrastructure.config import get_settings
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


def _ping_celery_workers(timeout: float = 2.0) -> dict[str, str]:
    """Synchronously discover responsive Celery workers (run in a thread)."""
    try:
        reply = celery_app.control.ping(timeout=timeout)
    except Exception as exc:
        logger.warning("Celery worker ping failed: %s", exc)
        return {}
    # Celery 5.x returns a list of {worker_name: {'ok': 'pong'}} dicts.
    alive: dict[str, str] = {}
    for entry in reply or []:
        if not isinstance(entry, dict):
            continue
        for worker_name, result in entry.items():
            if isinstance(result, dict):
                alive[worker_name] = "pong"
    return alive


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


@router.get("/health/worker")
async def worker_health_check() -> JSONResponse:
    """Ping the Celery broker for responsive workers, returning 200 with worker names or 503 when none respond."""
    workers = await asyncio.to_thread(_ping_celery_workers)
    if workers:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ok",
                "message": "at least one worker is alive",
                "workers": list(workers),
            },
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "unhealthy", "message": "no workers responding", "workers": []},
    )
