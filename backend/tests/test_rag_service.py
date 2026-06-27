#!/usr/bin/env python
"""Test end-to-end RAG service."""
import asyncio
from pathlib import Path
from app.core.config import settings
from app.auth.roles import UserRole
from app.schemas.user import AuthenticatedUser
from app.retrieval.embeddings.huggingface import HuggingFaceDenseEmbedder
from app.retrieval.embeddings.simple import TermFrequencySparseEmbedder
from app.retrieval.vector_store import VectorStoreClient
from app.retrieval.retrievers.hybrid import InMemoryHybridRetriever
from app.retrieval.rerankers.simple import LexicalCrossEncoderReranker
from app.generation.llm_client import StubLLMClient
from app.generation.rag_service import RAGService
from app.generation.chains.sql_rag import SQLRAGChain
from app.database.sqlite_executor import SQLiteExecutor

# Build RAG service
print("=== Building RAG Service ===")
dense = HuggingFaceDenseEmbedder()
sparse = TermFrequencySparseEmbedder()

vs = VectorStoreClient(
    data_root=Path(settings.knowledge_base_path),
    qdrant_path=Path(settings.qdrant_path),
    collection_name=settings.qdrant_collection_name,
    dense_embedder=dense,
    sparse_embedder=sparse,
    ingestor=None,
    enable_qdrant=True,
)
vs.connect()

retriever = InMemoryHybridRetriever(vs, dense, sparse)
reranker = LexicalCrossEncoderReranker()
llm = StubLLMClient()
sqlite_executor = SQLiteExecutor(db_path=settings.sqlite_db_path)
sql_chain = SQLRAGChain(llm_client=llm, sqlite_executor=sqlite_executor)

rag_service = RAGService(
    retriever=retriever,
    reranker=reranker,
    llm_client=llm,
    sql_chain=sql_chain,
    langchain_hybrid_chain=None,
)

# Test queries
test_cases = [
    ("infection control procedures", UserRole.ADMIN),
    ("What are the hand hygiene guidelines?", UserRole.DOCTOR),
    ("Medication administration", UserRole.NURSE),
]

print("\n=== Testing Queries ===")
for query, role in test_cases:
    user = AuthenticatedUser(user_id="test", username="test", role=role)
    print(f"\nQuery: '{query}' (Role: {role.value})")
    
    response = rag_service.answer(question=query, user=user)
    
    print(f"  Answer length: {len(response.answer)} chars")
    print(f"  Sources found: {len(response.sources)}")
    for idx, source in enumerate(response.sources[:2], start=1):
        print(f"    [{idx}] {source.source_document} | {source.section_title}")
    print(f"  Retrieval type: {response.retrieval_type}")

vs.close()
