#!/usr/bin/env python
"""Test LangChain retriever without filter."""
from pathlib import Path
from app.core.config import settings
from app.embeddings.huggingface import HuggingFaceDenseEmbedder
from app.embeddings.simple import TermFrequencySparseEmbedder
from app.db.vector_store import VectorStoreClient

# Load with correct embedders
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

if vs.langchain_vectorstore:
    query = "infection control"
    
    # Test 1: No filter, no search_kwargs
    print("\n=== Test 1: No filter, no search_kwargs ===")
    retriever1 = vs.langchain_vectorstore.as_retriever()
    docs1 = retriever1.invoke(query)
    print(f"Results: {len(docs1)}")
    for idx, doc in enumerate(docs1[:3], start=1):
        preview = doc.page_content[:80].replace('\n', ' ')
        print(f"  [{idx}] {preview}...")
    
    # Test 2: With search_kwargs but no filter
    print("\n=== Test 2: With search_kwargs, no filter ===")
    retriever2 = vs.langchain_vectorstore.as_retriever(search_kwargs={"k": 10})
    docs2 = retriever2.invoke(query)
    print(f"Results: {len(docs2)}")
    for idx, doc in enumerate(docs2[:3], start=1):
        preview = doc.page_content[:80].replace('\n', ' ')
        meta = doc.metadata
        print(f"  [{idx}] {meta.get('source_document')} | {preview}...")
    
    # Test 3: With filter
    print("\n=== Test 3: With filter ===")
    from qdrant_client import models
    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="access_roles",
                match=models.MatchAny(any=["admin"]),
            ),
            models.FieldCondition(
                key="collection",
                match=models.MatchAny(any=["nursing"]),
            ),
        ]
    )
    
    retriever3 = vs.langchain_vectorstore.as_retriever(
        search_kwargs={"k": 10, "filter": query_filter}
    )
    docs3 = retriever3.invoke(query)
    print(f"Results: {len(docs3)}")
    for idx, doc in enumerate(docs3[:3], start=1):
        preview = doc.page_content[:80].replace('\n', ' ')
        meta = doc.metadata
        print(f"  [{idx}] {meta.get('source_document')} | {preview}...")

vs.close()
