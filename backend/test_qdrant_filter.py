#!/usr/bin/env python
"""Test direct Qdrant query with filter."""
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
    
    # Build filter
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
    
    print("Testing direct Qdrant query_points() with filter...\n")
    
    result = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=query_filter,
        limit=10,
        with_payload=True,
        using="dense",
    )
    
    print(f"Direct query result: {len(result.points)} points")
    for idx, point in enumerate(result.points[:3], start=1):
        meta = point.payload.get('metadata', {})
        content = point.payload.get('page_content', '')[:80]
        print(f"  [{idx}] {meta.get('source_document')} | {content}...")
    
    # Now test with search
    print("\n\nTesting search() with filter...\n")
    result2 = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=10,
        with_payload=True,
        using="dense",
    )
    
    print(f"Search result: {len(result2)} points")
    for idx, point in enumerate(result2[:3], start=1):
        meta = point.payload.get('metadata', {})
        content = point.payload.get('page_content', '')[:80]
        print(f"  [{idx}] {meta.get('source_document')} | {content}...")

finally:
    client.close()
