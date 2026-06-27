from app.models.chunk import Chunk, ChunkMetadata
from app.retrieval.rerankers.cross_encoder import HuggingFaceCrossEncoderReranker


def test_cross_encoder_reranker_initialization() -> None:
    """Test that cross-encoder reranker initializes without errors."""
    reranker = HuggingFaceCrossEncoderReranker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    assert reranker is not None


def test_cross_encoder_reranker_fallback() -> None:
    """Test that reranker falls back to lexical scoring if model unavailable."""
    reranker = HuggingFaceCrossEncoderReranker(model_name="invalid-model")
    chunks = [
        Chunk(
            id="1",
            content="aspirin dosage guidelines adult",
            metadata=ChunkMetadata(
                source_document="a.md",
                collection="clinical",
                access_roles=["doctor"],
                section_title="Dosage",
                chunk_type="text",
            ),
        ),
        Chunk(
            id="2",
            content="cafeteria timings and menu",
            metadata=ChunkMetadata(
                source_document="b.md",
                collection="general",
                access_roles=["doctor"],
                section_title="Food",
                chunk_type="text",
            ),
        ),
    ]

    ranked = reranker.rerank("aspirin dosage", chunks, top_n=1)
    # Fallback to lexical should still work
    assert len(ranked) == 1
    assert ranked[0].chunk.id == "1"


def test_cross_encoder_reranker_empty_chunks() -> None:
    """Test that reranker handles empty chunk list."""
    reranker = HuggingFaceCrossEncoderReranker()
    ranked = reranker.rerank("test query", [], top_n=3)
    assert ranked == []


def test_cross_encoder_reranker_top_n() -> None:
    """Test that reranker respects top_n parameter."""
    reranker = HuggingFaceCrossEncoderReranker()
    chunks = [
        Chunk(
            id=str(i),
            content=f"content {i}",
            metadata=ChunkMetadata(
                source_document="doc.md",
                collection="general",
                access_roles=["admin"],
                section_title=f"Section {i}",
                chunk_type="text",
            ),
        )
        for i in range(10)
    ]

    ranked = reranker.rerank("query", chunks, top_n=3)
    assert len(ranked) <= 3
