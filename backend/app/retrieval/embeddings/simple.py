from __future__ import annotations

import math
import re
from collections import Counter

from app.retrieval.embeddings.interfaces import DenseEmbedder, SparseEmbedder

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class HashDenseEmbedder(DenseEmbedder):
    """Deterministic fallback embedder used for local development and tests."""

    def __init__(self, dimension: int = 64) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        for token in _tokens(text):
            idx = hash(token) % self.dimension
            vec[idx] += 1.0

        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]


class TermFrequencySparseEmbedder(SparseEmbedder):
    def embed_sparse(self, text: str) -> dict[str, float]:
        counts = Counter(_tokens(text))
        total = float(sum(counts.values()))
        if total == 0:
            return {}
        return {token: count / total for token, count in counts.items()}
