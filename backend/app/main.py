from contextlib import asynccontextmanager

import app.utils.ssl_fix as _ssl_fix
_ssl_fix.apply()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.dependencies import load_rag_service_into_state
from app.utils.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load RAGService once from persisted Qdrant index (don't rebuild)
    load_rag_service_into_state(app)
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
