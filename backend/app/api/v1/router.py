from fastapi import APIRouter

from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.collections import router as collections_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.login import router as login_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(login_router, tags=["auth"])
api_router.include_router(admin_router, tags=["admin"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(collections_router, tags=["collections"])
