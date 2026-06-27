import asyncio
import logging
from contextlib import asynccontextmanager

import app.utils.ssl_fix as _ssl_fix
_ssl_fix.apply()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.dependencies import (
    _is_index_ready,
    build_rag_index,
    _assemble_rag_service,
    load_rag_service_into_state,
    is_build_in_progress,
    set_build_in_progress,
)
from app.utils.logging import configure_logging

logger = logging.getLogger(__name__)


async def _auto_build_on_first_run(app: FastAPI) -> None:
    """Run the initial index build in a thread pool, then hot-load the service."""
    set_build_in_progress(True)
    try:
        logger.info("No existing index found — running initial knowledge-base indexing...")
        await asyncio.to_thread(build_rag_index)
        app.state.rag_service = _assemble_rag_service()
        logger.info("Initial indexing complete — RAGService loaded into app.state")
    except Exception:
        logger.exception("Initial auto-indexing failed; start server and trigger /admin/rag/build manually")
    finally:
        set_build_in_progress(False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _is_index_ready():
        # Index already exists — load it immediately (fast path)
        load_rag_service_into_state(app)
    else:
        # First run: build in background so the server starts accepting requests
        # (health endpoint works; chat returns 503 until build finishes)
        app.state.rag_service = None
        asyncio.create_task(_auto_build_on_first_run(app))
    yield
    # Shutdown: cleanup (optional)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": "MediBot backend is running"}

    return app


app = create_app()
