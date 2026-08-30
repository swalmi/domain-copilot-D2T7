import json
from collections.abc import AsyncIterator
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.deps import UserPayload, get_ask_question_use_case, get_current_user
from src.application.use_cases.ask_question import AskQuestionUseCase

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
    current_user: UserPayload = Depends(get_current_user),
    use_case: AskQuestionUseCase = Depends(get_ask_question_use_case),
) -> StreamingResponse:
    """Execute domain Q&A RAG pipeline streaming LLM answer tokens via Server-Sent Events (SSE)."""

    async def sse_event_generator() -> AsyncIterator[str]:
        async for event in use_case.execute_stream(
            query=payload.query,
            policy_id=payload.policy_id,
            policy_type=payload.policy_type,
            effective_date_before=payload.effective_date_before,
        ):
            if event["type"] == "token":
                yield f"data: {event['content']}\n\n"
            elif event["type"] == "done":
                metadata_payload = json.dumps(
                    {"citations": event["citations"], "refused": event["refused"]}
                )
                yield f"data: [DONE] {metadata_payload}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
