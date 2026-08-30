from collections.abc import Callable
from contextvars import ContextVar
from datetime import datetime, timezone
import functools
import logging
import time
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

logger = logging.getLogger("trace_logger")

correlation_id_ctx: ContextVar[UUID | None] = ContextVar(
    "correlation_id_ctx", default=None
)

# Global trace event repository storage in-memory for instant API querying & testing
_in_memory_trace_events: dict[UUID, list[dict[str, Any]]] = {}


def record_trace_event(
    correlation_id: UUID,
    step_name: str,
    event_type: str,
    payload: Any,
) -> dict[str, Any]:
    """Record a trace event row in storage with correlation_id for workflow auditing."""
    if isinstance(payload, BaseModel):
        serializable_payload = payload.model_dump(mode="json")
    elif isinstance(payload, dict | list | str | int | float | bool) or payload is None:
        serializable_payload = payload
    else:
        serializable_payload = str(payload)

    event = {
        "id": str(uuid4()),
        "correlation_id": str(correlation_id),
        "step_name": step_name,
        "event_type": event_type,
        "payload": serializable_payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if correlation_id not in _in_memory_trace_events:
        _in_memory_trace_events[correlation_id] = []
    _in_memory_trace_events[correlation_id].append(event)
    return event


def get_trace_events(correlation_id: UUID) -> list[dict[str, Any]]:
    """Retrieve ordered list of all trace events for a given correlation_id."""
    return _in_memory_trace_events.get(correlation_id, [])


def traced_step(step_name: str) -> Callable:
    """Decorator capturing function inputs, output/decision, exceptions into trace events."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            correlation_id = (
                kwargs.get("correlation_id")
                or (args[1] if len(args) > 1 and isinstance(args[1], UUID) else None)
                or correlation_id_ctx.get()
                or uuid4()
            )

            token = correlation_id_ctx.set(correlation_id)
            start_time = time.time()
            cid_str = str(correlation_id)

            logger.info(f"[TRACE START] Step: {step_name} | CorrelationID: {cid_str}")

            record_trace_event(
                correlation_id=correlation_id,
                step_name=step_name,
                event_type="input",
                payload={"kwargs_keys": list(kwargs.keys())},
            )

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(
                    f"[TRACE SUCCESS] Step: {step_name} | CorrelationID: {cid_str} | Duration: {duration:.3f}s"
                )

                record_trace_event(
                    correlation_id=correlation_id,
                    step_name=step_name,
                    event_type="decision" if "Drafter" in step_name else "output",
                    payload=result,
                )
                return result
            except Exception as exc:
                duration = time.time() - start_time
                logger.error(
                    f"[TRACE FAILED] Step: {step_name} | CorrelationID: {cid_str} | Duration: {duration:.3f}s | Error: {exc!s}"
                )
                record_trace_event(
                    correlation_id=correlation_id,
                    step_name=step_name,
                    event_type="error",
                    payload={"error": str(exc), "duration": duration},
                )
                raise
            finally:
                correlation_id_ctx.reset(token)

        return wrapper

    return decorator
