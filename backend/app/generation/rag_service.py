from __future__ import annotations

import logging
import re

from app.auth.roles import ROLE_COLLECTIONS, SQL_ALLOWED_ROLES, UserRole
from app.generation.chains.sql_rag import SQLRAGChain
from app.retrieval.rerankers.interfaces import CrossEncoderReranker
from app.retrieval.retrievers.interfaces import HybridRetriever
from app.models.chat import ChatResponse, SourceCitation
from app.models.user import AuthenticatedUser
from app.generation.langchain_hybrid_chain import LangChainHybridQAChain
from app.generation.llm_client import LLMClient

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: CrossEncoderReranker,
        llm_client: LLMClient,
        sql_chain: SQLRAGChain,
        langchain_hybrid_chain: LangChainHybridQAChain | None = None,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._llm = llm_client
        self._sql_chain = sql_chain
        self._langchain_hybrid_chain = langchain_hybrid_chain

    def answer(self, question: str, user: AuthenticatedUser) -> ChatResponse:
        logger.info(
            "answer called role=%s question=%r llm_client=%s",
            user.role.value,
            question,
            type(self._llm).__name__,
        )
        # TODO - add more sophisticated intent detection (e.g. using semantic-router)
        if self._is_greeting_intent(question):
            logger.info("Routing question to greeting response")
            return ChatResponse(
                answer=self._welcome_message_for_role(user.role),
                sources=[],
                retrieval_type="greeting_welcome",
                role=user.role,
            )

        if self._is_sql_intent(question):
            logger.info("Routing question to SQL RAG")
            return self._answer_sql(question=question, role=user.role)
        logger.info("Routing question to hybrid RAG")
        return self._answer_hybrid(question=question, role=user.role)

    @staticmethod
    def _is_sql_intent(question: str) -> bool:
        q = question.lower()
        sql_triggers = ["total", "status", "report", "analytics", "trend", "claims", "claims", "ticket", "count", "sql"]
        return any(trigger in q for trigger in sql_triggers)

    @staticmethod
    def _is_greeting_intent(question: str) -> bool:
        tokens = re.findall(r"[a-z']+", question.lower())
        if not tokens:
            return False
        greeting_tokens = {"hi", "hello", "hey", "greetings", "hola"}
        return any(token in greeting_tokens for token in tokens[:6])

    @staticmethod
    def _welcome_message_for_role(role: UserRole) -> str:
        role_capabilities: dict[UserRole, str] = {
            UserRole.DOCTOR: "clinical guidance, treatment protocols, nursing references, and general policies",
            UserRole.NURSE: "nursing procedures, medication administration, patient-care guidance, and general policies",
            UserRole.BILLING_EXECUTIVE: "billing workflows, claim/RCM guidance, payer policies, and general hospital references",
            UserRole.TECHNICIAN: "equipment manuals, maintenance procedures, troubleshooting steps, and general policies",
            UserRole.ADMIN: "all available domains: clinical, nursing, billing, equipment, and general references",
        }
        collections = ", ".join(ROLE_COLLECTIONS[role])
        sql_note = (
            "You can also ask analytics/SQL questions."
            if role in SQL_ALLOWED_ROLES
            else "Analytical SQL questions are restricted for your role."
        )
        capabilities = role_capabilities.get(role, "your allowed knowledge-base documents")
        return (
            "Hello! Welcome to MediAssist. "
            f"Based on your role ({role.value}), I can help with {capabilities}. "
            f"Your accessible collections are: {collections}. "
            f"{sql_note}"
        )

    def _answer_sql(self, question: str, role: UserRole) -> ChatResponse:
        if role not in SQL_ALLOWED_ROLES:
            return ChatResponse(
                answer="You are not authorized to run analytical SQL queries.",
                sources=[],
                retrieval_type="sql_rag_refusal",
                role=role,
            )

        answer, sql_query, _result_rows = self._sql_chain.run(question)
        logger.info("retrieval_type=sql_rag role=%s sql_generated=%s", role.value, sql_query)
        return ChatResponse(
            answer=answer,
            sources=[],
            retrieval_type="sql_rag",
            role=role,
        )

    def _answer_hybrid(self, question: str, role: UserRole) -> ChatResponse:
        if self._langchain_hybrid_chain is not None:
            logger.info("Attempting LangChain retrieval chain for hybrid answer")
            chain_result = self._langchain_hybrid_chain.run(question=question, role=role, top_k=5)
            if chain_result is not None:
                answer, citations = chain_result
                logger.info(
                    "LangChain retrieval chain complete citations=%s answer_chars=%s",
                    len(citations),
                    len(answer),
                )
                return ChatResponse(
                    answer=answer,
                    sources=citations,
                    retrieval_type="hybrid_rag_langchain",
                    role=role,
                )

        chunks = self._retriever.retrieve(query=question, role=role, top_k=50)
        reranked = self._reranker.rerank(query=question, chunks=chunks, top_n=10)
        logger.info(
            "Hybrid retrieval complete raw_chunk_count=%s reranked_count=%s llm_client=%s",
            len(chunks),
            len(reranked),
            type(self._llm).__name__,
        )

        for idx, chunk in enumerate(chunks[:10], start=1):
            preview = " ".join(chunk.content.split())[:180]
            logger.info(
                "retrieved_chunk idx=%s source=%s collection=%s section=%s preview=%r",
                idx,
                chunk.metadata.source_document,
                chunk.metadata.collection,
                chunk.metadata.section_title,
                preview,
            )

        for idx, item in enumerate(reranked, start=1):
            preview = " ".join(item.chunk.content.split())[:180]
            logger.info(
                "reranked_chunk idx=%s score=%.4f source=%s collection=%s section=%s preview=%r",
                idx,
                item.score,
                item.chunk.metadata.source_document,
                item.chunk.metadata.collection,
                item.chunk.metadata.section_title,
                preview,
            )

        context_blocks = [item.chunk.content for item in reranked]
        logger.info(
            "Hybrid context prepared block_count=%s total_chars=%s",
            len(context_blocks),
            sum(len(block) for block in context_blocks),
        )
        prompt = (
            "Answer the question using only the provided context. "
            "If context is insufficient, say so clearly. "
            f"Question: {question}\n\nContext:\n" + "\n\n".join(context_blocks)
        )
        answer = self._llm.generate(prompt)
        logger.info("LLM answer generated chars=%s llm_client=%s", len(answer), type(self._llm).__name__)

        citations = [
            SourceCitation(
                source_document=item.chunk.metadata.source_document,
                section_title=item.chunk.metadata.section_title,
                collection=item.chunk.metadata.collection,
            )
            for item in reranked
        ]

        scores = [round(item.score, 4) for item in reranked]
        logger.info(
            "retrieval_type=hybrid role=%s qdrant_filter=%s reranker_scores=%s",
            role.value,
            getattr(self._retriever, "last_debug", None),
            scores,
        )

        return ChatResponse(
            answer=answer,
            sources=citations,
            retrieval_type="hybrid_rag",
            role=role,
        )
