from __future__ import annotations

from app.auth.roles import UserRole
from app.models.chunk import Chunk, ChunkMetadata
from app.rerankers.interfaces import RerankedChunk
from app.schemas.user import AuthenticatedUser
from app.services.rag_service import RAGService


class DummyRetriever:
    def __init__(self) -> None:
        self.called = False

    def retrieve(self, query: str, role: UserRole, top_k: int = 10) -> list[Chunk]:
        self.called = True
        return [
            Chunk(
                id="c1",
                content="Sample context",
                metadata=ChunkMetadata(
                    source_document="doc.md",
                    collection="general",
                    access_roles=[role.value],
                    section_title="Section",
                    chunk_type="text",
                ),
            )
        ]


class DummyReranker:
    def rerank(self, query: str, chunks: list[Chunk], top_n: int = 3) -> list[RerankedChunk]:
        return [RerankedChunk(chunk=c, score=1.0) for c in chunks[:top_n]]


class DummyLLM:
    def generate(self, prompt: str) -> str:
        return "ok"


class DummySQLChain:
    def run(self, question: str) -> tuple[str, str, list[dict[str, object]]]:
        return "sql", "SELECT 1", []


def test_greeting_returns_role_aware_welcome_without_retrieval() -> None:
    retriever = DummyRetriever()
    service = RAGService(
        retriever=retriever,
        reranker=DummyReranker(),
        llm_client=DummyLLM(),
        sql_chain=DummySQLChain(),
        langchain_hybrid_chain=None,
    )

    user = AuthenticatedUser(username="nurse.priya", role=UserRole.NURSE)
    response = service.answer("Hi, I have some query on patient care", user)

    assert response.retrieval_type == "greeting_welcome"
    assert response.role == UserRole.NURSE
    assert "welcome" in response.answer.lower()
    assert "nursing" in response.answer.lower()
    assert "general" in response.answer.lower()
    assert retriever.called is False


def test_non_greeting_follows_regular_hybrid_path() -> None:
    retriever = DummyRetriever()
    service = RAGService(
        retriever=retriever,
        reranker=DummyReranker(),
        llm_client=DummyLLM(),
        sql_chain=DummySQLChain(),
        langchain_hybrid_chain=None,
    )

    user = AuthenticatedUser(username="dr.mehta", role=UserRole.DOCTOR)
    response = service.answer("infection control protocol", user)

    assert response.retrieval_type == "hybrid_rag"
    assert retriever.called is True
