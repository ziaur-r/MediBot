from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

from app.auth.roles import ROLE_COLLECTIONS, UserRole
from app.ingestion.vector_store import VectorStoreClient
from app.retrieval.embeddings.interfaces import DenseEmbedder, SparseEmbedder
from app.models.chunk import Chunk


@dataclass
class RetrievalDebugInfo:
    filter_payload: dict[str, object]


class InMemoryHybridRetriever:
    def __init__(
        self,
        vector_store: VectorStoreClient,
        dense_embedder: DenseEmbedder,
        sparse_embedder: SparseEmbedder,
    ) -> None:
        self._vector_store = vector_store
        self._dense = dense_embedder
        self._sparse = sparse_embedder
        self._last_debug = RetrievalDebugInfo(filter_payload={})

    @property
    def last_debug(self) -> RetrievalDebugInfo:
        return self._last_debug

    @property
    def vector_store(self) -> VectorStoreClient:
        return self._vector_store

    def retrieve(self, query: str, role: UserRole, top_k: int = 10) -> list[Chunk]:
        allowed_collections = set(ROLE_COLLECTIONS[role])
        filter_payload = {
            "must": [
                {
                    "key": "access_roles",
                    "match": {"any": [role.value]},
                },
                {
                    "key": "collection",
                    "match": {"any": sorted(allowed_collections)},
                },
            ]
        }
        self._last_debug = RetrievalDebugInfo(filter_payload=filter_payload)

        hybrid_chunks = self._vector_store.retrieve_hybrid(
            query=query,
            role=role.value,
            top_k=top_k,
            allowed_collections=allowed_collections,
        )
        if hybrid_chunks:
            return hybrid_chunks

        if self._vector_store.client is not None:
            return self._retrieve_from_qdrant(query=query, role=role, top_k=top_k, allowed_collections=allowed_collections)

        query_dense = self._dense.embed(query)
        query_sparse = self._sparse.embed_sparse(query)

        filtered_chunks = [
            chunk
            for chunk in self._vector_store.get_chunks()
            if role.value in chunk.metadata.access_roles and chunk.metadata.collection in allowed_collections
        ]

        scored = []
        for chunk in filtered_chunks:
            dense_score = self._cosine(query_dense, self._dense.embed(chunk.content))
            sparse_score = self._sparse_dot(query_sparse, self._sparse.embed_sparse(chunk.content))
            fused_score = (0.65 * dense_score) + (0.35 * sparse_score)
            scored.append((fused_score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    def _retrieve_from_qdrant(self, query: str, role: UserRole, top_k: int, allowed_collections: set[str]) -> list[Chunk]:
        from qdrant_client import models

        query_dense = self._dense.embed(query)
        sparse_map = self._sparse.embed_sparse(query)
        ordered_sparse = sorted(
            ((self._sparse_index(token), weight) for token, weight in sparse_map.items()),
            key=lambda item: item[0],
        )
        sparse_vector = models.SparseVector(
            indices=[index for index, _ in ordered_sparse],
            values=[value for _, value in ordered_sparse],
        )
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="access_roles",
                    match=models.MatchAny(any=[role.value]),
                ),
                models.FieldCondition(
                    key="collection",
                    match=models.MatchAny(any=sorted(allowed_collections)),
                ),
            ]
        )

        response = self._vector_store.client.query_points(
            collection_name=self._vector_store.collection_name,
            prefetch=[
                models.Prefetch(query=query_dense, using="dense", limit=top_k),
                models.Prefetch(query=sparse_vector, using="sparse", limit=top_k),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        chunks: list[Chunk] = []
        for point in response.points:
            payload = point.payload or {}
            metadata = payload.copy()
            content = str(metadata.pop("content", ""))
            metadata.pop("chunk_id", None)
            chunks.append(
                Chunk(
                    id=str(payload.get("chunk_id", point.id)),
                    content=content,
                    metadata=metadata,
                )
            )
        return chunks

    @staticmethod
    def _sparse_index(token: str) -> int:
        return int(sha1(token.encode("utf-8")).hexdigest()[:8], 16)

    @staticmethod
    def _cosine(v1: list[float], v2: list[float]) -> float:
        if not v1 or not v2:
            return 0.0
        return float(sum(a * b for a, b in zip(v1, v2)))

    @staticmethod
    def _sparse_dot(v1: dict[str, float], v2: dict[str, float]) -> float:
        if not v1 or not v2:
            return 0.0
        common = set(v1).intersection(v2)
        return float(sum(v1[token] * v2[token] for token in common))
