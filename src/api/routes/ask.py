from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, status
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


@router.post("", status_code=status.HTTP_200_OK)
async def ask_question(
    payload: AskRequest,
    current_user: UserPayload = Depends(get_current_user),
    use_case: AskQuestionUseCase = Depends(get_ask_question_use_case),
) -> dict[str, Any]:
    """Execute domain Q&A RAG pipeline and return cited answer as JSON response."""
    result = await use_case.execute(
        query=payload.query,
        policy_id=payload.policy_id,
        policy_type=payload.policy_type,
        effective_date_before=payload.effective_date_before,
    )
    return result
