from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
# Load backend/.env.local regardless of current working directory.
load_dotenv(dotenv_path=_BACKEND_ROOT / ".env")

from app.generation.chains.sql_rag import SQLRAGChain
from app.core.config import settings
from app.core.index_status import is_index_ready, mark_index_not_ready, mark_index_ready
from app.generation.chains.sqlite_executor import SQLiteExecutor
from app.ingestion.vector_store import VectorStoreClient
from app.retrieval.embeddings.huggingface import HuggingFaceDenseEmbedder
from app.retrieval.embeddings.simple import TermFrequencySparseEmbedder
from app.ingestion.docling_ingestor import DoclingIngestor
from app.retrieval.rerankers.cross_encoder import HuggingFaceCrossEncoderReranker
from app.retrieval.retrievers.hybrid import InMemoryHybridRetriever
from app.generation.langchain_hybrid_chain import LangChainHybridQAChain
from app.generation.llm_client import GroqLLMClient
from app.generation.rag_service import RAGService

logger = logging.getLogger(__name__)

# ── Status Check ──────────────────────────────────────────────────────────────

def _is_index_ready() -> bool:
    """True only if a completed build exists on disk."""
    return is_index_ready(Path(settings.qdrant_path))


# ── Embedders and LLM ─────────────────────────────────────────────────────────

def _make_embedders():
    """Factory for embedders based on test vs production."""
    dense = HuggingFaceDenseEmbedder()
    sparse = TermFrequencySparseEmbedder()
    return dense, sparse


def _make_llm_client() -> GroqLLMClient:
    """Factory for LLM client with fallback."""
    groq_api_key = (os.getenv("GROQ_API_KEY") or settings.groq_api_key).strip()
    if groq_api_key:
        try:
            return GroqLLMClient(
                api_key=groq_api_key,
                model=settings.groq_model,
                temperature=settings.groq_temperature,
            )
        except Exception as exc:
            logger.warning("Groq init failed, falling back to stub: %s", exc)
    return NotImplemented


def _make_vector_store(ingestor: DoclingIngestor | None = None) -> VectorStoreClient:
    """Construct, connect, and close a VectorStoreClient from current settings."""
    vs = VectorStoreClient(
        data_root=Path(settings.knowledge_base_path),
        qdrant_path=Path(settings.qdrant_path),
        collection_name=settings.qdrant_collection_name,
        ingestor=ingestor,
    )
    vs.connect()
    vs.close()
    return vs


# ── Build Phase (called once from admin endpoint) ───────────────────────────────

def build_rag_index() -> None:
    """
    Ingest documents, embed, and persist the Qdrant index to disk.
    Idempotent: re-running rebuilds from scratch and resets the ready flag.
    This is the ONLY place DoclingIngestor runs.
    """
    logger.info("RAG build started")
    mark_index_not_ready(Path(settings.qdrant_path))
    _make_vector_store(ingestor=DoclingIngestor())
    mark_index_ready(Path(settings.qdrant_path))
    logger.info("RAG build complete — index written to %s", settings.qdrant_path)


# ── Load Phase (called at app startup and after a build) ──────────────────────

def _assemble_rag_service() -> RAGService:
    """
    Connect to an already-built on-disk index and wire up the RAGService.
    No ingestion happens here.
    """
    dense_embedder, sparse_embedder = _make_embedders()
    llm_client = _make_llm_client()
    vector_store = _make_vector_store()

    retriever = InMemoryHybridRetriever(vector_store, dense_embedder, sparse_embedder)
    reranker = HuggingFaceCrossEncoderReranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
    sqlite_executor = SQLiteExecutor(db_path=settings.sqlite_db_path)
    sql_chain = SQLRAGChain(llm_client=llm_client, sqlite_executor=sqlite_executor)

    groq_api_key = (os.getenv("GROQ_API_KEY") or settings.groq_api_key).strip()
    langchain_hybrid_chain = LangChainHybridQAChain.create(
        vector_store=vector_store,
        groq_api_key=groq_api_key,
        groq_model=settings.groq_model,
        temperature=0.0,
    )

    return RAGService(
        retriever=retriever,
        reranker=reranker,
        llm_client=llm_client,
        sql_chain=sql_chain,
        langchain_hybrid_chain=langchain_hybrid_chain,
    )


def load_rag_service_into_state(app: FastAPI) -> None:
    """Called once at process startup. Skips gracefully if no index exists yet."""
    if not _is_index_ready():
        logger.warning("No RAG index found at startup — call POST /admin/rag/build first")
        app.state.rag_service = None
        return

    app.state.rag_service = _assemble_rag_service()
    logger.info("RAGService loaded into app.state")


# ── FastAPI dependency for chat routes ────────────────────────────────────────

def get_rag_service(request: Request) -> RAGService:
    """Retrieve RAGService from app.state, failing if not ready."""
    svc = getattr(request.app.state, "rag_service", None)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="RAG index not ready. Ask an admin to POST /admin/rag/build.",
        )
    return svc
