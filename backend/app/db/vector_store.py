from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from app.core.index_status import is_index_ready
from app.ingestion.docling_ingestor import DoclingIngestor
from app.models.chunk import Chunk, ChunkMetadata


logger = logging.getLogger(__name__)


class VectorStoreClient:
    def __init__(
        self,
        data_root: Path,
        qdrant_path: Path | None = None,
        collection_name: str = "mediassist_kb",
        ingestor: DoclingIngestor | None = None,
    ) -> None:
        self._data_root = data_root
        self._qdrant_path = qdrant_path or Path(".qdrant")
        self._collection_name = collection_name
        self._ingestor = ingestor
        self._ready = False
        self._chunks: list[Chunk] = []
        self._client: Any | None = None
        self._langchain_vectorstore: Any | None = None

    def connect(self) -> None:
        if is_index_ready(self._qdrant_path):
            if self._connect_to_existing_langchain_hybrid():
                self._ready = True
                return

        if self._connect_langchain_hybrid():
            self._ready = True

    def _connect_to_existing_langchain_hybrid(self) -> bool:
        """Connect to an existing LangChain Qdrant index without re-ingesting."""
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
        except ImportError:
            return False

        try:
            embed_model = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            dense_embeddings = HuggingFaceEmbeddings(
                model_name=embed_model,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25", batch_size=32)

            # Use path-based connection instead of passing a local client object.
            # This avoids serializing/pickling a sqlite3-backed client in runtime flows.
            self._langchain_vectorstore = QdrantVectorStore.from_existing_collection(
                collection_name=self._collection_name,
                path=str(self._qdrant_path),
                embedding=dense_embeddings,
                sparse_embedding=sparse_embeddings,
                vector_name="dense",
                sparse_vector_name="sparse",
                retrieval_mode=RetrievalMode.HYBRID,
            )
            logger.info("Connected to existing LangChain Qdrant index at %s", self._qdrant_path)
            self._client = None
            self._chunks = []  # Load on-demand if needed
            return True
        except Exception as exc:
            logger.debug("Could not connect to existing LangChain index: %s", exc)
            return False

    def _connect_langchain_hybrid(self) -> bool:
        try:
            from langchain_core.documents import Document
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
        except ImportError:
            return False

        if self._ingestor is None:
            logger.warning("_connect_langchain_hybrid called without an ingestor — skipping fresh build")
            return False

        if not self._data_root.exists():
            self._langchain_vectorstore = None
            return True

        try:
            all_chunks = self._ingestor.ingest_corpus(self._data_root)
        except Exception as exc:
            logger.error("Ingestion failed, hybrid index unavailable: %s", exc)
            return False

        documents = [
            Document(
                page_content=chunk.content,
                metadata={
                    "source_document": chunk.metadata.source_document,
                    "collection": chunk.metadata.collection,
                    "access_roles": chunk.metadata.access_roles,
                    "section_title": chunk.metadata.section_title,
                    "chunk_type": chunk.metadata.chunk_type,
                    "chunk_id": chunk.id,
                },
            )
            for chunk in all_chunks
        ]

        self._chunks = all_chunks

        if not documents:
            self._langchain_vectorstore = None
            return True

        self._qdrant_path.mkdir(parents=True, exist_ok=True)

        try:
            embed_model = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            dense_embeddings = HuggingFaceEmbeddings(
                model_name=embed_model,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25", batch_size=32)

            self._langchain_vectorstore = QdrantVectorStore.from_documents(
                documents=documents,
                embedding=dense_embeddings,
                sparse_embedding=sparse_embeddings,
                path=str(self._qdrant_path),
                collection_name=self._collection_name,
                vector_name="dense",
                sparse_vector_name="sparse",
                retrieval_mode=RetrievalMode.HYBRID,
            )
        except Exception as exc:
            logger.error("LangChain hybrid index build failed, fallback to legacy path: %s", exc)
            self._langchain_vectorstore = None
            return False

        self._client = None
        logger.info("LangChain hybrid Qdrant index ready docs=%s path=%s", len(documents), self._qdrant_path)
        return True

    def retrieve_hybrid(self, query: str, role: str, top_k: int, allowed_collections: set[str]) -> list[Chunk] | None:
        if self._langchain_vectorstore is None:
            return None

        # LangChain's HYBRID retrieval mode doesn't properly support Qdrant filters.
        # Workaround: retrieve MORE results without filter, then filter manually.
        retriever = self._langchain_vectorstore.as_retriever(search_kwargs={"k": max(100, top_k * 5)})
        docs = retriever.invoke(query)

        # Filter by role and collection
        filtered_docs = [
            doc
            for doc in docs
            if role in doc.metadata.get("access_roles", []) and doc.metadata.get("collection") in allowed_collections
        ]

        # Return top_k after filtering
        return [self._chunk_from_langchain_doc(doc, idx) for idx, doc in enumerate(filtered_docs[:top_k])]

    def is_ready(self) -> bool:
        return self._ready

    def get_chunks(self) -> list[Chunk]:
        if not self._ready:
            self.connect()
        return self._chunks

    def close(self) -> None:
        """Close and release Qdrant client lock."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None

    @property
    def client(self) -> Any | None:
        return self._client

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def langchain_vectorstore(self) -> Any | None:
        return self._langchain_vectorstore

    def _chunk_from_langchain_doc(self, doc: Any, idx: int) -> Chunk:
        metadata = getattr(doc, "metadata", {}) or {}
        chunk_id = str(metadata.get("chunk_id", f"langchain::{idx}"))
        content = str(getattr(doc, "page_content", ""))
        return Chunk(
            id=chunk_id,
            content=content,
            metadata=ChunkMetadata(
                source_document=str(metadata.get("source_document", "unknown")),
                collection=str(metadata.get("collection", "general")),
                access_roles=list(metadata.get("access_roles", [])),
                section_title=str(metadata.get("section_title", "No Heading")),
                chunk_type=self._normalize_chunk_type(str(metadata.get("chunk_type", "text"))),
            ),
        )

    @staticmethod
    def _normalize_chunk_type(value: str) -> str:
        normalized = value.lower().strip()
        if normalized in {"text", "table", "heading", "code"}:
            return normalized
        return "text"
