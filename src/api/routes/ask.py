import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.deps import get_ask_question_use_case
from src.application.use_cases.ask_question import AskQuestionUseCase
from src.infrastructure.observability.system_logger import (
    emit_system_log,
    set_correlation_id,
)

router = APIRouter(prefix="/ask", tags=["Q&A"])


class AskRequest(BaseModel):
    """Payload schema for domain policy question answering query."""

    query: str
    policy_id: str | None = None
    policy_type: str | None = None
    effective_date_before: date | None = None


@router.post("")
async def ask_question(
    payload: AskRequest,
    request: Request,
    use_case: AskQuestionUseCase = Depends(get_ask_question_use_case),
) -> StreamingResponse:
    """Execute domain Q&A RAG pipeline streaming LLM answer tokens via Server-Sent Events (SSE).

    Contract (aligned with the frontend AskQAStream reader):
      token -> "data: {\\"token\\": \\"<content>\\"}"
      done  -> "data: {\\"done\\": true, \\"citations\\": [...], \\"refused\\": bool}"
      terminator -> "data: [DONE]"

    Client disconnects (abort / Stop button) cancel the generator so server-side
    LLM streaming stops promptly (FR-6).
    """

    async def sse_event_generator() -> AsyncIterator[str]:
        # Scope the structured logger records for this request under one correlation id.
        correlation_id = uuid.uuid4()
        set_correlation_id(correlation_id)
        cancelled = False
        try:
            async for event in use_case.execute_stream(
                query=payload.query,
                policy_id=payload.policy_id,
                policy_type=payload.policy_type,
                effective_date_before=payload.effective_date_before,
            ):
                # Stop as soon as the client closes the connection (FR-6).
                if await request.is_disconnected():
                    cancelled = True
                    break
                if event["type"] == "token":
                    yield f"data: {json.dumps({'token': event['content']})}\n\n"
                elif event["type"] == "done":
                    metadata_payload = json.dumps(
                        {
                            "done": True,
                            "citations": event["citations"],
                            "refused": event["refused"],
                            "correlation_id": str(correlation_id),
                        }
                    )
                    yield f"data: {metadata_payload}\n\n"
                    yield "data: [DONE]\n\n"
            if cancelled:
                emit_system_log(
                    "generation",
                    "stream_cancelled",
                    {"query": payload.query, "reason": "client_disconnected"},
                    correlation_id=correlation_id,
                )
                yield f"data: {json.dumps({'cancelled': True, 'correlation_id': str(correlation_id)})}\n\n"
                yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            emit_system_log(
                "generation",
                "stream_cancelled",
                {"query": payload.query, "reason": "task_cancelled"},
                correlation_id=correlation_id,
            )
            raise
        except Exception as exc:  # pragma: no cover - defensive; keeps the UI informed
            error_payload = json.dumps(
                {"done": True, "error": str(exc), "correlation_id": str(correlation_id)}
            )
            yield f"data: {error_payload}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
