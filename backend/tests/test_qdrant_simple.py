#!/usr/bin/env python
"""Test Qdrant without filter vs with filter."""
from pathlib import Path
from app.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client import models

qdrant_path = Path(settings.qdrant_path)
collection_name = settings.qdrant_collection_name

client = QdrantClient(path=str(qdrant_path))

try:
    # Create a simple dense vector (all ones, 384-dim)
    query_vector = [1.0] * 384
    
    print("Testing search WITHOUT filter...\n")
    result_no_filter = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=5,
        with_payload=True,
    )
    
    print(f"Results without filter: {len(result_no_filter)}")
    for idx, point in enumerate(result_no_filter[:3], start=1):
        meta = point.payload.get('metadata', {})
        content = point.payload.get('page_content', '')[:60].replace('\n', ' ')
        print(f"  [{idx}] {meta.get('source_document')} | access_roles={meta.get('access_roles')} | collection={meta.get('collection')}")
        print(f"        {content}...")
    
    # Now test with filter
    print("\n\nTesting search WITH filter...\n")
    
    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="access_roles",
                match=models.MatchAny(any=["admin"]),
            ),
            models.FieldCondition(
                key="collection",
                match=models.MatchAny(any=["nursing"]),
            ),
        ]
    )
    
    print(f"Filter: {query_filter}\n")
    
    result_with_filter = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=5,
        with_payload=True,
    )
    
    print(f"Results WITH filter: {len(result_with_filter)}")
    for idx, point in enumerate(result_with_filter[:3], start=1):
        meta = point.payload.get('metadata', {})
        content = point.payload.get('page_content', '')[:60].replace('\n', ' ')
        print(f"  [{idx}] {meta.get('source_document')} | access_roles={meta.get('access_roles')} | collection={meta.get('collection')}")
        print(f"        {content}...")

finally:
    client.close()
