from __future__ import annotations

import getpass
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
# Load backend/.env.local regardless of current working directory.
load_dotenv(dotenv_path=_BACKEND_ROOT / ".env")

from app.chains.sql_rag import SQLRAGChain
from app.core.config import settings
from app.database.sqlite_executor import SQLiteExecutor
from app.db.vector_store import VectorStoreClient
from app.embeddings.huggingface import HuggingFaceDenseEmbedder
from app.embeddings.simple import HashDenseEmbedder, TermFrequencySparseEmbedder
from app.ingestion.docling_ingestor import DoclingIngestor
from app.rerankers.simple import LexicalCrossEncoderReranker
from app.retrievers.hybrid import InMemoryHybridRetriever
from app.services.langchain_hybrid_chain import LangChainHybridQAChain
from app.services.llm_client import GroqLLMClient, StubLLMClient
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)
_cached_rag_service: RAGService | None = None
_cached_service_key: tuple[bool, bool, str, float] | None = None


def get_rag_service() -> RAGService:
    global _cached_rag_service
    global _cached_service_key

    is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    groq_api_key = (os.getenv("GROQ_API_KEY") or settings.groq_api_key).strip()

    if not groq_api_key and not is_pytest:
        groq_api_key = getpass.getpass("Enter Groq API key (leave blank to use stub LLM): ").strip()
        if groq_api_key:
            # Keep it available for this process after first prompt.
            os.environ["GROQ_API_KEY"] = groq_api_key

    service_key = (
        settings.enable_qdrant and not is_pytest,
        bool(groq_api_key),
        settings.groq_model,
        settings.groq_temperature,
    )

    logger.info(
        "get_rag_service called pytest=%s qdrant_enabled=%s groq_key_present=%s groq_model=%s",
        is_pytest,
        settings.enable_qdrant and not is_pytest,
        bool(groq_api_key),
        settings.groq_model,
    )

    if _cached_rag_service is not None and _cached_service_key == service_key:
        logger.info("Reusing cached RAGService llm_client=%s", type(_cached_rag_service._llm).__name__)
        return _cached_rag_service

    logger.info("Building new RAGService for service_key=%s", service_key)

    dense_embedder = HashDenseEmbedder(dimension=96) if is_pytest else HuggingFaceDenseEmbedder()
    sparse_embedder = TermFrequencySparseEmbedder()
    vector_store = VectorStoreClient(
        data_root=Path(settings.knowledge_base_path),
        qdrant_path=Path(settings.qdrant_path),
        collection_name=settings.qdrant_collection_name,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        ingestor=DoclingIngestor(),
        enable_qdrant=settings.enable_qdrant and not is_pytest,
    )
    vector_store.connect()
    # Close Qdrant client immediately after initialization to release lock.
    # Chunks are loaded into memory, so client is no longer needed.
    vector_store.close()

    retriever = InMemoryHybridRetriever(vector_store, dense_embedder, sparse_embedder)
    reranker = LexicalCrossEncoderReranker()

    if groq_api_key and not is_pytest:
        try:
            llm_client = GroqLLMClient(
                api_key=groq_api_key,
                model=settings.groq_model,
                temperature=settings.groq_temperature,
            )
            logger.info("Using GroqLLMClient with model=%s", settings.groq_model)
        except Exception as exc:
            logger.warning("Groq client initialization failed, falling back to stub: %s", exc)
            llm_client = StubLLMClient()
    else:
        logger.info("Using StubLLMClient groq_key_present=%s pytest=%s", bool(groq_api_key), is_pytest)
        llm_client = StubLLMClient()

    sqlite_executor = SQLiteExecutor(db_path=settings.sqlite_db_path)
    sql_chain = SQLRAGChain(llm_client=llm_client, sqlite_executor=sqlite_executor)

    langchain_hybrid_chain = LangChainHybridQAChain.create(
        vector_store=vector_store,
        groq_api_key=groq_api_key,
        groq_model=settings.groq_model,
        temperature=0.0,
    )
    if langchain_hybrid_chain is not None:
        logger.info("LangChain hybrid retrieval chain enabled")
    else:
        logger.info("LangChain hybrid retrieval chain disabled; using fallback hybrid flow")

    service = RAGService(
        retriever=retriever,
        reranker=reranker,
        llm_client=llm_client,
        sql_chain=sql_chain,
        langchain_hybrid_chain=langchain_hybrid_chain,
    )
    _cached_rag_service = service
    _cached_service_key = service_key
    logger.info("RAGService ready llm_client=%s", type(llm_client).__name__)
    return service
