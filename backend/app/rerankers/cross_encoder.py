from __future__ import annotations

import logging
from typing import Any

from app.models.chunk import Chunk
from app.rerankers.interfaces import RerankedChunk

logger = logging.getLogger(__name__)


class HuggingFaceCrossEncoderReranker:
    """Cross-encoder reranker using HuggingFace sentence-transformers."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        """Initialize the cross-encoder reranker.
        
        Args:
            model_name: HuggingFace model identifier for the cross-encoder.
                       Default: "cross-encoder/ms-marco-MiniLM-L-6-v2"
        """
        self._model_name = model_name
        self._model: Any = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialize the cross-encoder model."""
        if self._initialized:
            return

        try:
            from langchain_community.cross_encoders import HuggingFaceCrossEncoder
            
            self._model = HuggingFaceCrossEncoder(model_name=self._model_name)
            self._initialized = True
            logger.info("✅ Cross-encoder reranker initialized with model: %s", self._model_name)
        except ImportError as exc:
            logger.warning(
                "HuggingFaceCrossEncoder unavailable; falling back to lexical reranking: %s", 
                exc
            )
            self._model = None
            self._initialized = True

    def rerank(self, query: str, chunks: list[Chunk], top_n: int = 3) -> list[RerankedChunk]:
        """Rerank chunks using cross-encoder model.
        
        Args:
            query: The query string.
            chunks: List of chunks to rerank.
            top_n: Number of top chunks to return after reranking.
        
        Returns:
            List of reranked chunks sorted by relevance score.
        """
        self._ensure_initialized()

        if not chunks:
            return []

        # If model failed to initialize, fall back to lexical scoring
        if self._model is None:
            return self._lexical_fallback(query, chunks, top_n)

        try:
            # Prepare query-document pairs
            pairs = [[query, chunk.content] for chunk in chunks]
            
            # Get cross-encoder scores
            scores = self._model.score(pairs)
            
            # Create scored chunks
            scored: list[RerankedChunk] = []
            for chunk, score in zip(chunks, scores):
                scored.append(RerankedChunk(chunk=chunk, score=float(score)))
            
            # Sort by score (descending) and keep top_n
            scored.sort(key=lambda item: item.score, reverse=True)
            return scored[:top_n]
            
        except Exception as exc:
            logger.warning("Cross-encoder scoring failed, falling back to lexical: %s", exc)
            return self._lexical_fallback(query, chunks, top_n)

    @staticmethod
    def _lexical_fallback(query: str, chunks: list[Chunk], top_n: int) -> list[RerankedChunk]:
        """Fallback to lexical scoring when cross-encoder is unavailable."""
        q_tokens = {token.lower() for token in query.split()}
        scored: list[RerankedChunk] = []
        
        for chunk in chunks:
            c_tokens = {token.lower() for token in chunk.content.split()}
            overlap = len(q_tokens.intersection(c_tokens))
            score = overlap / max(1, len(q_tokens))
            scored.append(RerankedChunk(chunk=chunk, score=score))
        
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_n]
