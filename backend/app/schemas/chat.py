from pydantic import BaseModel, Field

from app.auth.roles import UserRole


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")


class SourceCitation(BaseModel):
    source_document: str
    section_title: str
    collection: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    retrieval_type: str
    role: UserRole
