from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import (
    ask_router,
    auth_router,
    documents_router,
    health_router,
)
from src.infrastructure.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    description="Domain Copilot API for domain policy Q&A and automated claim adjudication.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(ask_router)


