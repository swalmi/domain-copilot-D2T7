"""API routes package."""

from src.api.routes.auth import router as auth_router
from src.api.routes.health import router as health_router

__all__ = ["health_router", "auth_router"]

