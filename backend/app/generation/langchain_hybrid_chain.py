from __future__ import annotations

import logging
from typing import Any

import httpx

from app.auth.roles import ROLE_COLLECTIONS, UserRole
from app.ingestion.vector_store import VectorStoreClient
from app.models.chat import SourceCitation

logger = logging.getLogger(__name__)


class LangChainHybridQAChain:
    def __init__(
        self,
        vector_store: VectorStoreClient,
        llm: Any,
        prompt: Any,
        reranker: Any | None,
    ) -> None:
        self._vector_store = vector_store
        self._llm = llm
        self._prompt = prompt
        self._reranker = reranker  # pre-built CrossEncoderReranker or None

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
            from langchain_groq import ChatGroq
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_community.cross_encoders import HuggingFaceCrossEncoder
            from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
        except ImportError:
            logger.info("LangChain hybrid QA chain dependencies missing; using fallback RAG path")
            return None

        # Pre-build LLM client once — reused for every request
        try:
            llm = ChatGroq(
                groq_api_key=groq_api_key,
                model=groq_model,
                temperature=temperature,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                http_client=httpx.Client(verify=False),
            )
        except Exception as exc:
            logger.warning("LangChain ChatGroq init failed: %s", exc)
            return None

        # Pre-build prompt template once
        # system_prompt = (
        #     "You are MediBot assistant. Use only the provided context. "
        #     "In case user doesn't ask question but give reference to some text/keywords, you should answer based on the context provided. "
        #     "Only reply based on the context which is relevant to query and don't make less or more information. "
        #     "If context is insufficient, say that clearly and do not fabricate details.\n\n"
        #     "Context:\n{context}"
        # )

        system_prompt = """
            You are MediBot, the advanced intelligent assistant for MediAssist Health Network.
            Your task is to answer the user's medical or hospital-related question using ONLY the provided verified context.
            If the context does not contain enough information to answer the question, state that you do not know. Do not hallucinate.

            Context:\n{context}
            """.strip()
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )

        # Pre-load cross-encoder model once — most expensive operation
        reranker = None
        try:
            cross_encoder = HuggingFaceCrossEncoder(
                model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
            )
            reranker = CrossEncoderReranker(model=cross_encoder, top_n=10)
            logger.info("Cross-encoder reranker ready: cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as exc:
            logger.warning("Cross-encoder initialization failed; reranking disabled: %s", exc)

        return cls(
            vector_store=vector_store,
            llm=llm,
            prompt=prompt,
            reranker=reranker,
        )

    def run(self, question: str, role: UserRole, top_k: int = 5) -> tuple[str, list[SourceCitation]] | None:
        if self._vector_store.langchain_vectorstore is None:
            return None

        try:
            from langchain_classic.chains import create_retrieval_chain
            from langchain_classic.chains.combine_documents import create_stuff_documents_chain
            from langchain_classic.retrievers import ContextualCompressionRetriever
            from langchain_core.runnables import RunnableLambda
        except ImportError as e:
            logger.info("LangChain imports unavailable at runtime: %s; using fallback RAG path", e)
            return None

        allowed_collections = set(ROLE_COLLECTIONS[role])

        broad_retriever = self._vector_store.langchain_vectorstore.as_retriever(
            search_kwargs={"k": max(50, top_k)}
        )

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

        if self._reranker is not None:
            final_retriever = ContextualCompressionRetriever(
                base_compressor=self._reranker,
                base_retriever=role_filtered_retriever,
            )
        else:
            final_retriever = role_filtered_retriever

        # ── Permission check before invoking LLM ─────────────────────────────
        # Dry-run the retriever to check if ANY permitted docs exist for this query.
        # This avoids invoking the LLM chain when the user has no access at all.
        candidate_docs = _filter_by_role(question)

        if not candidate_docs:
            # Check whether docs exist but are access-blocked vs. genuinely not found
            all_docs      = broad_retriever.invoke(question)
            blocked_docs  = [
                doc for doc in all_docs
                if role.value not in doc.metadata.get("access_roles", [])
                or doc.metadata.get("collection") not in allowed_collections
            ]

            if blocked_docs:
                # Docs exist but role has no permission
                blocked_collections = sorted({
                    doc.metadata.get("collection", "unknown")
                    for doc in blocked_docs
                })
                allowed_display = sorted(allowed_collections)

                permission_msg = (
                    f"You don't have permission to access these documents "
                    f"(restricted to: {', '.join(blocked_collections)}).\n"
                    f"I can only answer questions from the following collections: "
                    f"{', '.join(allowed_display)}."
                )
                logger.info(
                    "Access denied: role=%s blocked_collections=%s allowed=%s",
                    role.value, blocked_collections, allowed_display,
                )
                return permission_msg, []   # empty citations — no accessible source

            else:
                # No docs found at all (not an access issue — genuinely out of scope)
                logger.info("No documents retrieved for query=%r role=%s", question[:50], role.value)
                return None
        # ─────────────────────────────────────────────────────────────────────

        try:
            question_answer_chain = create_stuff_documents_chain(self._llm, self._prompt)
            retrieval_chain       = create_retrieval_chain(final_retriever, question_answer_chain)
            result: dict[str, Any] = retrieval_chain.invoke({"input": question})
        except Exception as exc:
            logger.warning("LangChain retrieval invoke failed; falling back: %s", exc)
            return None

        answer       = str(result.get("answer", "")).strip() or "No response generated by retrieval chain."
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

