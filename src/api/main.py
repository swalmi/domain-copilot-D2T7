from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Return health status of the API application instance."""
    return {"status": "ok", "app": settings.app_title}
