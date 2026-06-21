from __future__ import annotations

from app.models.chunk import Chunk
from app.rerankers.interfaces import RerankedChunk


class LexicalCrossEncoderReranker:
    """Deterministic reranker used as a local fallback for cross-encoder behavior."""

    def rerank(self, query: str, chunks: list[Chunk], top_n: int = 3) -> list[RerankedChunk]:
        q_tokens = {token.lower() for token in query.split()}

        scored: list[RerankedChunk] = []
        for chunk in chunks:
            c_tokens = {token.lower() for token in chunk.content.split()}
            overlap = len(q_tokens.intersection(c_tokens))
            score = overlap / max(1, len(q_tokens))
            scored.append(RerankedChunk(chunk=chunk, score=score))

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_n]
