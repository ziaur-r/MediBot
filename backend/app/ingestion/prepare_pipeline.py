from __future__ import annotations

import app.utils.ssl_fix as _ssl_fix
_ssl_fix.apply()

from pathlib import Path

from app.core.config import settings
from app.database.sqlite_executor import SQLiteExecutor
from app.db.vector_store import VectorStoreClient
from app.embeddings.huggingface import HuggingFaceDenseEmbedder
from app.ingestion.docling_ingestor import DoclingIngestor
from langchain_qdrant import FastEmbedSparse


def prepare_rag_pipeline() -> None:
    print(f"Knowledge base path: {Path(settings.knowledge_base_path).resolve()}", flush=True)
    print(f"Qdrant path: {Path(settings.qdrant_ingest_path).resolve()}", flush=True)
    print(f"SQLite path: {Path(settings.sqlite_db_path).resolve()}", flush=True)

    dense_embedder = HuggingFaceDenseEmbedder()
    sparse_embedder = FastEmbedSparse(model_name="Qdrant/bm25", batch_size=32)
    try:
        vector_store = VectorStoreClient(
            data_root=Path(settings.knowledge_base_path),
            qdrant_path=Path(settings.qdrant_ingest_path),
            collection_name=settings.qdrant_collection_name,
            dense_embedder=dense_embedder,
            sparse_embedder=sparse_embedder,
            ingestor=DoclingIngestor(),
            enable_qdrant=True,
            reset_index_on_connect=True,
        )
        vector_store.connect()
    except Exception as exc:
        print(f"RAG preparation failed: {exc}", flush=True)
        raise

    sqlite_executor = SQLiteExecutor(settings.sqlite_db_path)
    schema = sqlite_executor.inspect_schema()
    print(f"Prepared {len(vector_store.get_chunks())} chunks in collection '{settings.qdrant_collection_name}'.")
    print(f"SQL-RAG schema tables: {sorted(schema)}")


if __name__ == "__main__":
    prepare_rag_pipeline()