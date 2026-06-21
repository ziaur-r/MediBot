from __future__ import annotations

from typing import Protocol

from app.auth.roles import UserRole
from app.models.chunk import Chunk


class HybridRetriever(Protocol):
    def retrieve(self, query: str, role: UserRole, top_k: int = 10) -> list[Chunk]:
        ...
