from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.limiter import limiter
from src.api.routes import (
    approvals_router,
    ask_router,
    auth_router,
    claims_router,
    documents_router,
    health_router,
    runs_router,
)
from src.infrastructure.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    description="Domain Copilot API for domain policy Q&A and automated claim adjudication.",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Callable[..., Any]) -> Response:
    """HTTP middleware adding OWASP recommended security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(ask_router)
app.include_router(claims_router)
app.include_router(runs_router)
app.include_router(approvals_router)
