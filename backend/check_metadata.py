#!/usr/bin/env python
"""Check metadata on Qdrant points."""
from pathlib import Path
from app.core.config import settings
from qdrant_client import QdrantClient
import json

qdrant_path = Path(settings.qdrant_path)
collection_name = settings.qdrant_collection_name

client = QdrantClient(path=str(qdrant_path))

try:
    result = client.scroll(collection_name=collection_name, limit=10)
    points, _ = result
    
    print(f"Found {len(points)} points\n")
    
    for idx, point in enumerate(points[:5], start=1):
        meta = point.payload.get('metadata', {})
        print(f"Point {idx}:")
        print(f"  Metadata keys: {list(meta.keys())}")
        print(f"  Metadata: {json.dumps(meta, indent=2)}")
        
        # Check access_roles field specifically
        if 'access_roles' in meta:
            print(f"  access_roles: {meta['access_roles']}")
        else:
            print(f"  ❌ NO access_roles field!")
        
        # Check collection field
        if 'collection' in meta:
            print(f"  collection: {meta['collection']}")
        else:
            print(f"  ❌ NO collection field!")
        
        print()

finally:
    client.close()
