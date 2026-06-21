from pathlib import Path

from app.auth.roles import UserRole
from app.db.vector_store import VectorStoreClient
from app.embeddings.simple import HashDenseEmbedder, TermFrequencySparseEmbedder
from app.retrievers.hybrid import InMemoryHybridRetriever


def test_retriever_applies_role_filter() -> None:
    store = VectorStoreClient(data_root=Path("mediassist_data"), enable_qdrant=False)
    store.connect()

    retriever = InMemoryHybridRetriever(
        vector_store=store,
        dense_embedder=HashDenseEmbedder(),
        sparse_embedder=TermFrequencySparseEmbedder(),
    )

    billing_results = retriever.retrieve("claim submission", role=UserRole.BILLING_EXECUTIVE, top_k=10)
    nurse_results = retriever.retrieve("claim submission", role=UserRole.NURSE, top_k=10)

    assert billing_results
    assert all(chunk.metadata.collection == "billing" for chunk in billing_results)
    assert all(chunk.metadata.collection != "billing" for chunk in nurse_results)
    assert retriever.last_debug.filter_payload["must"][0]["key"] == "access_roles"
