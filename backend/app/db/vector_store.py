from __future__ import annotations

import logging
import os
from hashlib import sha1
from pathlib import Path
from typing import Any

from app.auth.roles import ROLE_COLLECTIONS
from app.embeddings.interfaces import DenseEmbedder, SparseEmbedder
from app.ingestion.docling_ingestor import DoclingIngestor
from app.models.chunk import Chunk, ChunkMetadata


logger = logging.getLogger(__name__)


class VectorStoreClient:
    def __init__(
        self,
        data_root: Path,
        qdrant_path: Path | None = None,
        collection_name: str = "mediassist_kb",
        dense_embedder: DenseEmbedder | None = None,
        sparse_embedder: SparseEmbedder | None = None,
        ingestor: DoclingIngestor | None = None,
        enable_qdrant: bool = True,
        reset_index_on_connect: bool = False,
    ) -> None:
        #from app.embeddings.simple import HashDenseEmbedder, TermFrequencySparseEmbedder

        self._data_root = data_root
        self._qdrant_path = qdrant_path or Path(".qdrant")
        self._collection_name = collection_name
        self._dense = dense_embedder
        self._sparse = sparse_embedder
        self._ingestor = ingestor
        self._enable_qdrant = enable_qdrant
        self._reset_index_on_connect = reset_index_on_connect
        self._ready = False
        self._chunks: list[Chunk] = []
        self._client: Any | None = None
        self._langchain_vectorstore: Any | None = None

    def connect(self) -> None:
        if not self._enable_qdrant:
            self._chunks = self._load_markdown_only_chunks()
            self._ready = True
            return

        self._chunks = self._load_chunks()

        # Full reset should only happen for explicit ingestion runs, not API request-time connect.
        if self._reset_index_on_connect:
            import shutil

            if self._qdrant_path.exists():
                try:
                    logger.info("Removing entire Qdrant directory for fresh ingestion: %s", self._qdrant_path)
                    shutil.rmtree(str(self._qdrant_path))
                except Exception as exc:
                    logger.warning("Could not remove Qdrant directory: %s", exc)

        if self._connect_langchain_hybrid():
            self._ready = True
            return

        logger.info("Falling back to legacy Qdrant ingestion path")
        self._connect_legacy_qdrant()
        self._ready = True

    def _connect_langchain_hybrid(self) -> bool:
        try:
            from docling.chunking import HybridChunker
            from docling.document_converter import DocumentConverter
            from langchain_core.documents import Document
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
        except ImportError:
            return False

        if not self._data_root.exists():
            self._langchain_vectorstore = None
            return True

        try:
            converter = DocumentConverter()
            chunker = HybridChunker()
        except Exception as exc:
            logger.warning("LangChain hybrid chunker unavailable, fallback to legacy path: %s", exc)
            return False
        documents: list[Document] = []

        for file_path in sorted(self._data_root.rglob("*")):
            if not file_path.is_file() or "db" in file_path.parts:
                continue
            if file_path.suffix.lower() not in {".md", ".pdf"}:
                continue

            rel = file_path.relative_to(self._data_root)
            collection = rel.parts[0] if rel.parts else "general"
            access_roles = [role.value for role, collections in ROLE_COLLECTIONS.items() if collection in collections]

            if file_path.suffix.lower() == ".pdf":
                try:
                    doc_result = converter.convert(str(file_path))
                    docling_document = getattr(doc_result, "document", doc_result)
                    for idx, chunk in enumerate(chunker.chunk(docling_document)):
                        chunk_text = getattr(chunk, "text", "").strip()
                        if not chunk_text:
                            continue

                        meta = getattr(chunk, "meta", None)
                        headings = getattr(meta, "headings", None) or []
                        heading_path = " > ".join(headings) if headings else "No Heading"

                        element_type = "unknown"
                        doc_items = getattr(meta, "doc_items", None) or []
                        if doc_items:
                            label = getattr(doc_items[0], "label", None)
                            if label is not None:
                                element_type = str(label)

                        documents.append(
                            Document(
                                page_content=f"{heading_path}\n\n{chunk_text}",
                                metadata={
                                    "source_document": file_path.name,
                                    "collection": collection,
                                    "access_roles": access_roles,
                                    "section_title": heading_path,
                                    "chunk_type": element_type,
                                    "chunk_id": f"{collection}/{file_path.name}::{idx}",
                                },
                            )
                        )
                except Exception:
                    logger.exception("Docling hybrid chunking failed for %s", file_path)
                    chunks = self._ingestor.ingest_file(file_path, collection, access_roles)
                    for chunk in chunks:
                        documents.append(
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
                        )
            else:
                chunks = self._ingestor.ingest_file(file_path, collection, access_roles)
                for chunk in chunks:
                    documents.append(
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
                    )

        self._chunks = [
            Chunk(
                id=str(doc.metadata.get("chunk_id", f"chunk::{idx}")),
                content=doc.page_content,
                metadata=ChunkMetadata(
                    source_document=str(doc.metadata.get("source_document", "unknown")),
                    collection=str(doc.metadata.get("collection", "general")),
                    access_roles=list(doc.metadata.get("access_roles", [])),
                    section_title=str(doc.metadata.get("section_title", "No Heading")),
                    chunk_type=self._normalize_chunk_type(str(doc.metadata.get("chunk_type", "text"))),
                ),
            )
            for idx, doc in enumerate(documents)
        ]

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
                force_recreate=self._reset_index_on_connect,
            )
        except Exception as exc:
            logger.warning("LangChain hybrid index build failed, fallback to legacy path: %s", exc)
            self._langchain_vectorstore = None
            return False
        self._client = None
        logger.info("LangChain hybrid Qdrant index ready docs=%s path=%s", len(documents), self._qdrant_path)
        return True

    def _connect_legacy_qdrant(self) -> None:

        try:
            from qdrant_client import QdrantClient, models
        except ImportError:
            self._client = None
            return

        self._qdrant_path.mkdir(parents=True, exist_ok=True)
        self._client = QdrantClient(path=str(self._qdrant_path))

        # Create collection with correct embedder dimensions
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config={
                "dense": models.VectorParams(
                    size=len(self._dense.embed("dimension probe")),
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={"sparse": models.SparseVectorParams()},
        )

        self._client.upsert(
            collection_name=self._collection_name,
            points=[self._to_point_struct(chunk, models) for chunk in self._chunks],
            wait=True,
        )

    def retrieve_hybrid(self, query: str, role: str, top_k: int, allowed_collections: set[str]) -> list[Chunk] | None:
        if self._langchain_vectorstore is None:
            return None

        from qdrant_client import models

        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="access_roles",
                    match=models.MatchAny(any=[role]),
                ),
                models.FieldCondition(
                    key="collection",
                    match=models.MatchAny(any=sorted(allowed_collections)),
                ),
            ]
        )
        retriever = self._langchain_vectorstore.as_retriever(
            search_kwargs={"k": top_k, "filter": query_filter}
        )
        docs = retriever.invoke(query)
        return [self._chunk_from_langchain_doc(doc, idx) for idx, doc in enumerate(docs)]

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

    def _load_chunks(self) -> list[Chunk]:
        if not self._data_root.exists():
            return []

        try:
            return self._ingestor.ingest_corpus(self._data_root)
        except Exception:
            # Keep the app functional when PDF ingestion fails (e.g., missing deps/network/SSL).
            return self._load_markdown_only_chunks()

    @property
    def client(self) -> Any | None:
        return self._client

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def langchain_vectorstore(self) -> Any | None:
        return self._langchain_vectorstore

    def _to_point_struct(self, chunk: Chunk, models: Any) -> Any:
        dense_vector = self._dense.embed(chunk.content)
        sparse_vector = self._sparse.embed_sparse(chunk.content)
        ordered_sparse = sorted(
            ((self._sparse_index(token), weight) for token, weight in sparse_vector.items()),
            key=lambda item: item[0],
        )
        indices = [index for index, _ in ordered_sparse]
        values = [value for _, value in ordered_sparse]

        return models.PointStruct(
            id=self._point_id(chunk.id),
            vector={
                "dense": dense_vector,
                "sparse": models.SparseVector(indices=indices, values=values),
            },
            payload={
                "content": chunk.content,
                "source_document": chunk.metadata.source_document,
                "collection": chunk.metadata.collection,
                "access_roles": chunk.metadata.access_roles,
                "section_title": chunk.metadata.section_title,
                "chunk_type": chunk.metadata.chunk_type,
                "chunk_id": chunk.id,
            },
        )

    @staticmethod
    def _point_id(value: str) -> int:
        return int(sha1(value.encode("utf-8")).hexdigest()[:16], 16)

    @staticmethod
    def _sparse_index(token: str) -> int:
        return int(sha1(token.encode("utf-8")).hexdigest()[:8], 16)

    def _load_markdown_only_chunks(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        for file_path in sorted(self._data_root.rglob("*")):
            if not file_path.is_file():
                continue
            if "db" in file_path.parts:
                continue
            if file_path.suffix.lower() not in {".md", ".pdf"}:
                continue

            rel = file_path.relative_to(self._data_root)
            collection = rel.parts[0] if rel.parts else "general"
            access_roles = [role.value for role, collections in ROLE_COLLECTIONS.items() if collection in collections]
            if file_path.suffix.lower() == ".md":
                chunks.extend(self._ingestor.ingest_file(file_path, collection, access_roles))
                continue

            # Fallback placeholder for PDFs when conversion is unavailable (e.g., SSL/model download issues).
            section_title = file_path.stem.replace("_", " ").title()
            chunks.append(
                Chunk(
                    id=f"{collection}/{file_path.name}::fallback",
                    content=(
                        f"Section: {section_title}\n\n"
                        f"Content:\nSource document: {file_path.name}. "
                        "Full PDF text is unavailable in markdown-only fallback mode."
                    ),
                    metadata=ChunkMetadata(
                        source_document=file_path.name,
                        collection=collection,
                        access_roles=access_roles,
                        section_title=section_title,
                        chunk_type="text",
                    ),
                )
            )
        return chunks

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
