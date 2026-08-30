import asyncio
from datetime import datetime
import json
import os
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
    """Fallback embedder for local batch processing when Ollama is unavailable."""

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


async def run_ingestion() -> None:
    """Run IngestDocumentUseCase across all 20 documents in data/metadata.json."""
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/domain_copilot",
    )
    if "@db:" in db_url and not os.path.exists("/.dockerenv"):
        db_url = db_url.replace("@db:", "@localhost:")

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        provider: LLMProvider = OllamaProvider()
        await provider.embed("test connection")
        print("Using OllamaProvider for embeddings.")
    except Exception as e:
        print(f"Ollama unavailable ({e}), using FallbackDeterministicProvider for local embeddings.")
        provider = FallbackDeterministicProvider()

    metadata_path = "data/metadata.json"
    if not os.path.exists(metadata_path):
        print(f"Error: {metadata_path} not found.")
        return

    with open(metadata_path, "r") as f:
        docs = json.load(f)

    print(f"\n=========================================================================")
    print(f"STARTING CORPUS INGESTION: {len(docs)} Documents")
    print(f"=========================================================================\n")

    summary_results = []

    for idx, doc_meta in enumerate(docs, start=1):
        rel_file = doc_meta["file"]
        file_path = os.path.join("data", rel_file)
        policy_id = doc_meta["policy_id"]
        policy_type = doc_meta["policy_type"]
        version = doc_meta["version"]
        effective_date = datetime.strptime(
            doc_meta["effective_date"], "%Y-%m-%d"
        ).date()

        print(f"[{idx}/{len(docs)}] Ingesting {rel_file} (Policy: {policy_id}, Type: {policy_type})...")
        start_time = time.time()

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

        elapsed = time.time() - start_time
        result["file"] = rel_file
        result["policy_id"] = policy_id
        result["elapsed_seconds"] = round(elapsed, 2)
        summary_results.append(result)

        status = result.get("status")
        if status == "success":
            print(
                f"  ✅ SUCCESS in {result['elapsed_seconds']}s | "
                f"Chunks: {result.get('chunks_count')} | Inserted: {result.get('inserted_count')}"
            )
        elif status == "already_ingested":
            print(f"  ℹ️ ALREADY INGESTED in {result['elapsed_seconds']}s (Skipped)")
        else:
            print(f"  ❌ FAILED in {result['elapsed_seconds']}s | Error: {result.get('error')}")
        print("-" * 75)

    await engine.dispose()

    print("\n=========================================================================")
    print("FINAL INGESTION SUMMARY REPORT")
    print("=========================================================================")
    successes = [r for r in summary_results if r.get("status") == "success"]
    already = [r for r in summary_results if r.get("status") == "already_ingested"]
    failures = [r for r in summary_results if r.get("status") == "failed"]

    print(f"Total Processed: {len(summary_results)}")
    print(f"  - Successful:       {len(successes)}")
    print(f"  - Already Ingested: {len(already)}")
    print(f"  - Failed:           {len(failures)}")

    if failures:
        print("\nFailures Detail:")
        for f in failures:
            print(f"  * File: {f['file']} | Error: {f.get('error')}")


if __name__ == "__main__":
    asyncio.run(run_ingestion())
