from __future__ import annotations

import logging
from typing import Any

import httpx

from app.auth.roles import ROLE_COLLECTIONS, UserRole
from app.db.vector_store import VectorStoreClient
from app.schemas.chat import SourceCitation

logger = logging.getLogger(__name__)


class LangChainHybridQAChain:
    def __init__(
        self,
        vector_store: VectorStoreClient,
        groq_api_key: str,
        groq_model: str,
        temperature: float = 0.0,
    ) -> None:
        self._vector_store = vector_store
        self._groq_api_key = groq_api_key
        self._groq_model = groq_model
        self._temperature = temperature

    @classmethod
    def create(
        cls,
        vector_store: VectorStoreClient,
        groq_api_key: str,
        groq_model: str,
        temperature: float = 0.0,
    ) -> LangChainHybridQAChain | None:
        if not groq_api_key.strip() or vector_store.langchain_vectorstore is None:
            return None

        try:
            #import langchain.chains  # noqa: F401
            import langchain_core.prompts  # noqa: F401
            import langchain_groq  # noqa: F401
        except ImportError:
            logger.info("LangChain hybrid QA chain dependencies missing; using fallback RAG path")
            return None

        return cls(
            vector_store=vector_store,
            groq_api_key=groq_api_key,
            groq_model=groq_model,
            temperature=temperature,
        )

    def run(self, question: str, role: UserRole, top_k: int = 5) -> tuple[str, list[SourceCitation]] | None:
        if self._vector_store.langchain_vectorstore is None:
            return None

        try:
            from langchain_groq import ChatGroq
            from langchain_classic.chains import create_retrieval_chain
            from langchain_classic.chains.combine_documents import create_stuff_documents_chain
            from langchain_classic.retrievers import ContextualCompressionRetriever
            from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
            from langchain_community.cross_encoders import HuggingFaceCrossEncoder
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.runnables import RunnableLambda
        except ImportError as e:
            logger.info("LangChain imports unavailable at runtime: %s; using fallback RAG path", e)
            return None

        allowed_collections = set(ROLE_COLLECTIONS[role])

        # Base retriever: fetch more candidates for reranking (hybrid search with k=5)
        broad_retriever = self._vector_store.langchain_vectorstore.as_retriever(
            search_kwargs={"k": max(50, top_k)}
        )

        # Wrap RBAC filtering as a Runnable so it can be composed with LangChain components
        def _filter_by_role(query: str) -> list:
            docs = broad_retriever.invoke(query)
            filtered = [
                doc for doc in docs
                if role.value in doc.metadata.get("access_roles", [])
                and doc.metadata.get("collection") in allowed_collections
            ]
            logger.debug(
                "Retrieval: query=%r retrieved=%d filtered=%d role=%s",
                query[:50],
                len(docs),
                len(filtered),
                role.value,
            )
            return filtered

        role_filtered_retriever = RunnableLambda(_filter_by_role)

        # Cross-encoder reranker: score candidates and keep top_n
        try:
            cross_encoder = HuggingFaceCrossEncoder(
                model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
            )
            reranker = CrossEncoderReranker(
                model=cross_encoder,
                top_n=10,
            )
            logger.info("Cross-encoder reranker ready: cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as exc:
            logger.warning("Cross-encoder initialization failed; using fallback retriever: %s", exc)
            reranker = None

        # Contextual compression retriever: applies reranking to filter results
        if reranker is not None:
            final_retriever = ContextualCompressionRetriever(
                base_compressor=reranker,
                base_retriever=role_filtered_retriever,
            )
            logger.info("Retrieval pipeline: Hybrid search → Top-10 candidates → Cross-encoder reranker → Top-3")
        else:
            final_retriever = role_filtered_retriever

        try:
            llm = ChatGroq(
                groq_api_key=self._groq_api_key,
                model=self._groq_model,
                temperature=self._temperature,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                http_client=httpx.Client(verify=False)
            )
        except Exception as exc:
            logger.warning("LangChain ChatGroq init failed; falling back to classic hybrid flow: %s", exc)
            return None

        system_prompt = (
            "You are MediBot assistant. Use only the provided context. "
            "If context is insufficient, say that clearly and do not fabricate details.\n\n"
            "Context:\n{context}"
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )

        try:
            question_answer_chain = create_stuff_documents_chain(llm, prompt)
            retrieval_chain = create_retrieval_chain(final_retriever, question_answer_chain)
            result: dict[str, Any] = retrieval_chain.invoke({"input": question})
        except Exception as exc:
            logger.warning("LangChain retrieval invoke failed; falling back to classic hybrid flow: %s", exc)
            return None

        answer = str(result.get("answer", "")).strip() or "No response generated by retrieval chain."
        context_docs = list(result.get("context", []))

        citations: list[SourceCitation] = []
        for doc in context_docs:
            metadata = getattr(doc, "metadata", {}) or {}
            citations.append(
                SourceCitation(
                    source_document=str(metadata.get("source_document", "unknown")),
                    section_title=str(metadata.get("section_title", "No Heading")),
                    collection=str(metadata.get("collection", "general")),
                )
            )

        return answer, citations
