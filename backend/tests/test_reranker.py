from app.models.chunk import Chunk, ChunkMetadata
from app.rerankers.simple import LexicalCrossEncoderReranker


def test_reranker_prefers_high_overlap() -> None:
    reranker = LexicalCrossEncoderReranker()
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
    assert ranked[0].chunk.id == "1"
