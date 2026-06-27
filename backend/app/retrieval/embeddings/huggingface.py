from __future__ import annotations

import os

from app.retrieval.embeddings.interfaces import DenseEmbedder


class HuggingFaceDenseEmbedder(DenseEmbedder):
    """Dense embedder backed by LangChain HuggingFaceEmbeddings."""

    def __init__(self, model_name: str | None = None) -> None:
        from langchain_huggingface import HuggingFaceEmbeddings

        selected_model = model_name or os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self._embeddings = HuggingFaceEmbeddings(
            model_name=selected_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def embed(self, text: str) -> list[float]:
        return list(self._embeddings.embed_query(text))
