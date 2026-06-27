from __future__ import annotations

import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.auth.roles import UserRole
from app.auth.security import get_current_user
from app.dependencies import _is_index_ready, build_rag_index, _assemble_rag_service
from app.models.user import AuthenticatedUser

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

_build_in_progress = False


def _require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Verify user is admin."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _run_build_and_reload(app: Request.app.__class__) -> None:
    """Run build in background, then hot-reload into app.state."""
    global _build_in_progress
    try:
        build_rag_index()                        # blocks; writes index to disk
        app.state.rag_service = _assemble_rag_service()  # hot-reload into state
        logger.info("RAGService hot-reloaded after build")
    except Exception:
        logger.exception("RAG build failed")
    finally:
        _build_in_progress = False


@router.post("/rag/build")
def trigger_rag_build(
    request: Request,
    background_tasks: BackgroundTasks,
    _: AuthenticatedUser = Depends(_require_admin),
):
    """
    Kick off a full RAG rebuild in the background.
    The existing service keeps serving until the new one is ready.
    """
    global _build_in_progress
    if _build_in_progress:
        raise HTTPException(status_code=409, detail="Build already in progress")
    _build_in_progress = True
    background_tasks.add_task(_run_build_and_reload, request.app)
    return {"status": "build started"}


@router.get("/rag/status")
def rag_status(
    request: Request,
    _: AuthenticatedUser = Depends(_require_admin),
):
    """Check RAG index status."""
    return {
        "index_ready": _is_index_ready(),
        "service_loaded": request.app.state.rag_service is not None,
        "build_in_progress": _build_in_progress,
    }
