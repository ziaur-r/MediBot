from fastapi import APIRouter, Depends

from app.auth.security import get_current_user
from app.dependencies import get_rag_service
from app.models.chat import ChatRequest, ChatResponse
from app.models.user import AuthenticatedUser
from app.generation.rag_service import RAGService

router = APIRouter()


@router.post("", response_model=ChatResponse)
def ask_question(
    payload: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
) -> ChatResponse:
    return rag_service.answer(question=payload.question, user=user)
