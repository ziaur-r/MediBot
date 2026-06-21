#!/usr/bin/env python
"""Test retrieval with correct embedder."""
import logging
logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')

from pathlib import Path
from app.core.config import settings
from app.auth.roles import UserRole
from app.embeddings.huggingface import HuggingFaceDenseEmbedder
from app.embeddings.simple import TermFrequencySparseEmbedder
from app.db.vector_store import VectorStoreClient
from app.retrievers.hybrid import InMemoryHybridRetriever

# Load index with CORRECT embedders
print("\n=== Loading Vector Store with HuggingFace Embedder ===")
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

print(f"LangChain vectorstore: {vs.langchain_vectorstore}")
print(f"Chunks loaded: {len(vs.get_chunks())}")

# Try direct retrieval from langchain vectorstore
print("\n=== Testing Direct LangChain Retrieval ===")
if vs.langchain_vectorstore:
    query = "infection control procedures"
    print(f"Query: {query}")
    
    from qdrant_client import models
    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="access_roles",
                match=models.MatchAny(any=["admin"]),
            ),
            models.FieldCondition(
                key="collection",
                match=models.MatchAny(any=["clinical", "nursing", "general", "billing", "equipment"]),
            ),
        ]
    )
    
    retriever = vs.langchain_vectorstore.as_retriever(
        search_kwargs={"k": 10, "filter": query_filter}
    )
    
    docs = retriever.invoke(query)
    print(f"LangChain direct retrieve result: {len(docs)} docs")
    for idx, doc in enumerate(docs[:5], start=1):
        preview = doc.page_content[:100].replace('\n', ' ')
        meta = doc.metadata
        print(f"  [{idx}] {meta.get('source_document')} | {meta.get('section_title')}: {preview}...")

vs.close()

# Try through InMemoryHybridRetriever
print("\n=== Testing InMemoryHybridRetriever ===")
retriever_obj = InMemoryHybridRetriever(vs, dense, sparse)

chunks = retriever_obj.retrieve(query="infection control procedures", role=UserRole.ADMIN, top_k=10)
print(f"Retrieved chunks: {len(chunks)}")
for idx, chunk in enumerate(chunks[:5], start=1):
    preview = chunk.content[:100].replace('\n', ' ')
    print(f"  [{idx}] {chunk.metadata.source_document} | {chunk.metadata.section_title}: {preview}...")

# Test another query
print("\n=== Testing Another Query ===")
chunks2 = retriever_obj.retrieve(query="medication dosage", role=UserRole.DOCTOR, top_k=5)
print(f"Retrieved chunks for 'medication dosage' (doctor role): {len(chunks2)}")
for idx, chunk in enumerate(chunks2[:3], start=1):
    preview = chunk.content[:100].replace('\n', ' ')
    print(f"  [{idx}] {chunk.metadata.source_document}: {preview}...")
