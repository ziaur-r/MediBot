from __future__ import annotations

from pathlib import Path


def get_index_ready_file(qdrant_path: Path) -> Path:
    """Return the marker file used to indicate a completed index build."""
    return qdrant_path / ".rag_ready"


def is_index_ready(qdrant_path: Path) -> bool:
    """True when a completed index build marker exists."""
    return get_index_ready_file(qdrant_path).exists()


def mark_index_not_ready(qdrant_path: Path) -> None:
    """Remove ready marker before a rebuild starts."""
    get_index_ready_file(qdrant_path).unlink(missing_ok=True)


def mark_index_ready(qdrant_path: Path) -> None:
    """Create ready marker after rebuild completes."""
    qdrant_path.mkdir(parents=True, exist_ok=True)
    get_index_ready_file(qdrant_path).touch()
