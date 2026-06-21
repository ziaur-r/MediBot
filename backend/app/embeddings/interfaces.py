from __future__ import annotations

from typing import Protocol


class DenseEmbedder(Protocol):
    def embed(self, text: str) -> list[float]:
        ...


class SparseEmbedder(Protocol):
    def embed_sparse(self, text: str) -> dict[str, float]:
        ...
