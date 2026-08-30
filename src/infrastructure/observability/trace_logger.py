import functools
import logging
import time
from typing import Any, Callable
from uuid import UUID

logger = logging.getLogger("trace_logger")


def traced_step(step_name: str) -> Callable:
    """Decorator tracking execution duration, status, and correlation_id for workflow steps."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            correlation_id = kwargs.get("correlation_id")
            if not correlation_id and len(args) > 1 and isinstance(args[1], UUID):
                correlation_id = args[1]

            start_time = time.time()
            cid_str = str(correlation_id) if correlation_id else "N/A"
            logger.info(f"[TRACE START] Step: {step_name} | CorrelationID: {cid_str}")

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(
                    f"[TRACE SUCCESS] Step: {step_name} | CorrelationID: {cid_str} "
                    f"| Duration: {duration:.3f}s"
                )
                return result
            except Exception as exc:
                duration = time.time() - start_time
                logger.error(
                    f"[TRACE FAILED] Step: {step_name} | CorrelationID: {cid_str} "
                    f"| Duration: {duration:.3f}s | Error: {str(exc)}"
                )
                raise

        return wrapper

    return decorator
