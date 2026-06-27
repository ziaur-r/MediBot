#!/usr/bin/env python
"""
Test script to verify the refactored build/load architecture.
"""
import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from app.core.config import settings
from app.dependencies import _is_index_ready, build_rag_index, _assemble_rag_service, load_rag_service_into_state
from app.main import app as fastapi_app

def test_index_status():
    """Test 1: Check if index status file works."""
    logger.info("\n=== Test 1: Index Status ===")
    ready = _is_index_ready()
    logger.info(f"Index ready: {ready}")
    status_file = Path(settings.qdrant_path) / ".rag_ready"
    logger.info(f"Status file: {status_file}")
    logger.info(f"Status file exists: {status_file.exists()}")
    return ready

def test_build_index():
    """Test 2: Build index and verify status."""
    logger.info("\n=== Test 2: Build Index ===")
    try:
        build_rag_index()
        logger.info("✓ Index build completed")
        ready = _is_index_ready()
        logger.info(f"✓ Index ready after build: {ready}")
        return ready
    except Exception as e:
        logger.error(f"✗ Build failed: {e}")
        return False

def test_load_rag_service():
    """Test 3: Load RAG service and verify it's assembled."""
    logger.info("\n=== Test 3: Load RAG Service ===")
    try:
        service = _assemble_rag_service()
        logger.info(f"✓ RAGService assembled")
        logger.info(f"  - Retriever: {type(service._retriever).__name__}")
        logger.info(f"  - Reranker: {type(service._reranker).__name__}")
        logger.info(f"  - LLM: {type(service._llm).__name__}")
        logger.info(f"  - SQL Chain: {type(service._sql_chain).__name__}")
        logger.info(f"  - LangChain Chain: {'enabled' if service._langchain_hybrid_chain else 'disabled'}")
        return True
    except Exception as e:
        logger.error(f"✗ Load failed: {e}")
        return False

def test_app_lifespan():
    """Test 4: Verify app lifespan loads service into state."""
    logger.info("\n=== Test 4: App Lifespan ===")
    try:
        load_rag_service_into_state(fastapi_app)
        has_service = hasattr(fastapi_app.state, 'rag_service') and fastapi_app.state.rag_service is not None
        logger.info(f"{'✓' if has_service else '✗'} RAGService in app.state: {has_service}")
        return has_service
    except Exception as e:
        logger.error(f"✗ Lifespan failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Testing refactored build/load architecture...\n")
    
    results = {
        "Index status": test_index_status(),
        "Build index": test_build_index(),
        "Load RAG service": test_load_rag_service(),
        "App lifespan": test_app_lifespan(),
    }
    
    logger.info("\n=== Summary ===")
    for name, result in results.items():
        status = "✓" if result else "✗"
        logger.info(f"{status} {name}")
    
    all_passed = all(results.values())
    logger.info(f"\n{'✓ All tests passed!' if all_passed else '✗ Some tests failed'}")
    exit(0 if all_passed else 1)
