#!/usr/bin/env python
"""Check Qdrant collection directly."""
from pathlib import Path
from app.core.config import settings
from qdrant_client import QdrantClient

qdrant_path = Path(settings.qdrant_path)
collection_name = settings.qdrant_collection_name

print(f"Qdrant path: {qdrant_path}")
print(f"Collection name: {collection_name}")
print(f"Qdrant path exists: {qdrant_path.exists()}")

client = QdrantClient(path=str(qdrant_path))

# Get collection info
try:
    collections = client.get_collections()
    print(f"\nCollections in Qdrant: {[c.name for c in collections.collections]}")
    
    if collection_name in [c.name for c in collections.collections]:
        info = client.get_collection(collection_name)
        print(f"\nCollection '{collection_name}' info:")
        print(f"  Points count: {info.points_count}")
        print(f"  Vectors count: {info.vectors_count}")
        print(f"  Config: {info.config}")
        
        # Try to get some points
        print(f"\nFetching first 5 points...")
        result = client.scroll(collection_name=collection_name, limit=5)
        points, _ = result
        print(f"Got {len(points)} points")
        
        for idx, point in enumerate(points[:3], start=1):
            print(f"\nPoint {idx}:")
            print(f"  ID: {point.id}")
            print(f"  Payload keys: {list(point.payload.keys()) if point.payload else 'None'}")
            if point.payload:
                print(f"  Sample payload: {str(point.payload)[:200]}...")
    else:
        print(f"\nCollection '{collection_name}' NOT FOUND")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    client.close()
