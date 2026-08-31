from uuid import UUID
import json
import asyncio
import redis.asyncio as redis
from src.infrastructure.config import get_settings


_PAUSE_KEY_PREFIX = "pause:run:"
_PAUSE_CHANNEL_PREFIX = "pause:chan:"


def _key(run_id: UUID) -> str:
    return f"{_PAUSE_KEY_PREFIX}{run_id}"


def _channel(run_id: UUID) -> str:
    return f"{_PAUSE_CHANNEL_PREFIX}{run_id}"


async def pause_run(run_id: UUID) -> None:
    """Mark the run as paused in Redis and publish a pause event."""
    settings = get_settings()
    r = redis.from_url(settings.redis_url)
    await r.set(_key(run_id), "1")
    try:
        await r.publish(_channel(run_id), json.dumps({"action": "paused"}))
    finally:
        await r.close()


async def resume_run(run_id: UUID) -> None:
    """Resume a previously paused run: delete Redis key and publish resume event."""
    settings = get_settings()
    r = redis.from_url(settings.redis_url)
    try:
        await r.delete(_key(run_id))
        await r.publish(_channel(run_id), json.dumps({"action": "resumed"}))
    finally:
        await r.close()


async def is_paused(run_id: UUID) -> bool:
    settings = get_settings()
    r = redis.from_url(settings.redis_url)
    try:
        val = await r.get(_key(run_id))
        return val is not None
    finally:
        await r.close()


async def wait_if_paused(run_id: UUID) -> None:
    """If run is paused, wait until resumed. Uses Redis pub/sub to avoid busy polling.

    This function returns immediately if the run is not paused. If paused it subscribes
    to a run-specific channel and waits for a 'resumed' message.
    """
    settings = get_settings()
    r = redis.from_url(settings.redis_url)
    try:
        val = await r.get(_key(run_id))
        if not val:
            return

        # Subscribe and wait for resume message
        pubsub = r.pubsub()
        await pubsub.subscribe(_channel(run_id))
        try:
            async for message in pubsub.listen():
                # message example: {'type':'message','pattern':None,'channel':b'...','data':b'...'}
                if message is None:
                    continue
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                try:
                    payload = json.loads(data)
                except Exception:
                    payload = None
                if isinstance(payload, dict) and payload.get("action") == "resumed":
                    break
        finally:
            await pubsub.unsubscribe(_channel(run_id))
            await pubsub.close()
    finally:
        await r.close()
