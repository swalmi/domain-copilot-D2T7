"""API routes package."""

from src.api.routes.ask import router as ask_router
from src.api.routes.auth import router as auth_router
from src.api.routes.claims import router as claims_router
from src.api.routes.documents import router as documents_router
from src.api.routes.health import router as health_router

__all__ = [
    "ask_router",
    "auth_router",
    "claims_router",
    "documents_router",
    "health_router",
]
