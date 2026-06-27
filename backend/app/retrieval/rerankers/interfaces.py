from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models.chunk import Chunk


@dataclass
class RerankedChunk:
    chunk: Chunk
    score: float


class CrossEncoderReranker(Protocol):
    def rerank(self, query: str, chunks: list[Chunk], top_n: int = 3) -> list[RerankedChunk]:
        ...
