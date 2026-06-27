#!/usr/bin/env python
"""Test retrieval end-to-end to find chunk drop."""
import logging
logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')

from pathlib import Path
from app.core.config import settings
from app.auth.roles import UserRole
from app.retrieval.embeddings.simple import HashDenseEmbedder, TermFrequencySparseEmbedder
from app.retrieval.vector_store import VectorStoreClient
from app.retrieval.retrievers.hybrid import InMemoryHybridRetriever

# Load index
print("\n=== Loading Vector Store ===")
vs = VectorStoreClient(
    data_root=Path(settings.knowledge_base_path),
    qdrant_path=Path(settings.qdrant_path),
    collection_name=settings.qdrant_collection_name,
    dense_embedder=HashDenseEmbedder(dimension=96),
    sparse_embedder=TermFrequencySparseEmbedder(),
    ingestor=None,
    enable_qdrant=True,
)
vs.connect()

print(f"LangChain vectorstore: {vs.langchain_vectorstore}")
print(f"LangChain vectorstore type: {type(vs.langchain_vectorstore)}")
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
    print(f"Retriever: {retriever}")
    
    docs = retriever.invoke(query)
    print(f"LangChain direct retrieve result: {len(docs)} docs")
    for idx, doc in enumerate(docs[:3], start=1):
        preview = doc.page_content[:80].replace('\n', ' ')
        meta = doc.metadata
        print(f"  [{idx}] {meta.get('source_document')} | {meta.get('section_title')}: {preview}...")

vs.close()

# Try through InMemoryHybridRetriever
print("\n=== Testing InMemoryHybridRetriever ===")
dense = HashDenseEmbedder(dimension=96)
sparse = TermFrequencySparseEmbedder()
retriever_obj = InMemoryHybridRetriever(vs, dense, sparse)

query = "infection control procedures"
print(f"Query: {query}")

chunks = retriever_obj.retrieve(query=query, role=UserRole.ADMIN, top_k=10)
print(f"Retrieved chunks: {len(chunks)}")
for idx, chunk in enumerate(chunks[:5], start=1):
    preview = chunk.content[:100].replace('\n', ' ')
    print(f"  [{idx}] {chunk.metadata.source_document} | {chunk.metadata.section_title}: {preview}...")
