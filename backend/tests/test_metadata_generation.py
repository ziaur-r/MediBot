from pathlib import Path

from app.retrieval.vector_store import VectorStoreClient


def test_chunk_metadata_fields_exist() -> None:
    store = VectorStoreClient(data_root=Path("knowledge_data"), enable_qdrant=False)
    store.connect()

    chunks = store.get_chunks()
    assert chunks

    first = chunks[0].metadata
    assert first.source_document
    assert first.collection
    assert isinstance(first.access_roles, list)
    assert first.section_title
    assert first.chunk_type in {"text", "table", "heading", "code"}
