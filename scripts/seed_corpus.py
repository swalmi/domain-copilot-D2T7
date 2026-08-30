import asyncio
from datetime import datetime
import json
import os
import sys
import time

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.use_cases.ingest_document import IngestDocumentUseCase
from src.domain.interfaces.llm_provider import LLMProvider
from src.infrastructure.db.repositories.document_repository import (
    SqlalchemyDocumentRepository,
)
from src.infrastructure.llm.ollama_provider import OllamaProvider
from src.infrastructure.vectorstore.pgvector_store import PgVectorStore


class FallbackDeterministicProvider(LLMProvider):
    """Fallback embedder for local seeding when Ollama is unavailable."""

    async def complete(self, prompt: str, system: str | None = None) -> str:
        return "response"

    async def stream(self, prompt: str, system: str | None = None):
        yield "response"

    async def call_tool(
        self, prompt: str, tools: list[dict], system: str | None = None
    ) -> dict:
        return {}

    async def embed(self, text: str) -> list[float]:
        import hashlib

        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [(b / 255.0) * 2 - 1 for b in (h * 24)[:768]]
        return vec


async def main() -> None:
    """Seed corpus documents into PostgreSQL vector database using IngestDocumentUseCase."""
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/domain_copilot",
    )
    if "@db:" in db_url and not os.path.exists("/.dockerenv"):
        db_url = db_url.replace("@db:", "@localhost:")

    manifest_path = "seed-data/manifest.json"
    if not os.path.exists(manifest_path):
        manifest_path = "data/metadata.json"

    if not os.path.exists(manifest_path):
        print(f"Error: Manifest file not found at seed-data/manifest.json or data/metadata.json")
        sys.exit(1)

    with open(manifest_path, "r") as f:
        entries = json.load(f)

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        provider: LLMProvider = OllamaProvider()
        await provider.embed("health check")
        print("Connected to OllamaProvider for embeddings.")
    except Exception:
        print("Ollama unavailable, using FallbackDeterministicProvider for local embeddings.")
        provider = FallbackDeterministicProvider()

    print(f"\nSeeding {len(entries)} documents from {manifest_path}...\n")
    print(f"{'Filename':<55} | {'Status':<16} | {'Chunks':<8}")
    print("-" * 85)

    summary_rows = []
    for entry in entries:
        file_path = entry["file"]
        if not os.path.exists(file_path) and not file_path.startswith("data/"):
            file_path = os.path.join("data", file_path)

        policy_id = entry["policy_id"]
        policy_type = entry["policy_type"]
        version = entry["version"]
        effective_date = datetime.strptime(
            entry["effective_date"], "%Y-%m-%d"
        ).date()

        async with session_factory() as session:
            vector_store = PgVectorStore(session)
            document_repo = SqlalchemyDocumentRepository(session)
            use_case = IngestDocumentUseCase(
                llm_provider=provider,
                vector_store=vector_store,
                document_repo=document_repo,
            )

            result = await use_case.execute(
                file_path=file_path,
                policy_id=policy_id,
                policy_type=policy_type,
                version=version,
                effective_date=effective_date,
            )

        status = result.get("status", "failed")
        chunk_count = result.get("chunks_count", 0) if status == "success" else 0
        filename_display = os.path.basename(file_path)

        summary_rows.append({
            "file": filename_display,
            "status": status,
            "chunks": chunk_count,
        })
        print(f"{filename_display:<55} | {status:<16} | {chunk_count:<8}")

    await engine.dispose()

    print("-" * 85)
    print("Corpus seeding completed.\n")


if __name__ == "__main__":
    asyncio.run(main())
