import asyncio
import json
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from evaluation.score_refusal import score_refusal_correctness
from evaluation.score_retrieval import score_hit_rate
from src.application.use_cases.ask_question import AskQuestionUseCase
from src.infrastructure.llm.ollama_provider import OllamaProvider
from src.infrastructure.llm.openrouter_provider import OpenRouterProvider
from src.infrastructure.llm.provider_router import ProviderRouter
from src.infrastructure.vectorstore.pgvector_store import PgVectorStore


async def main() -> None:
    engine = create_async_engine(
        "postgresql+psycopg://postgres:postgres@localhost:5432/domain_copilot"
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    with open("evaluation/golden_set.json", "r") as f:
        golden_set = json.load(f)

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    api_key = os.getenv("OPENROUTER_API_KEY", "mock_key")

    primary = OllamaProvider(base_url=ollama_url)
    fallback = OpenRouterProvider(api_key=api_key)
    llm_provider = ProviderRouter(primary=primary, fallback=fallback)

    async with session_factory() as session:
        vector_store = PgVectorStore(session)
        ask_use_case = AskQuestionUseCase(
            llm_provider=llm_provider, vector_store=vector_store
        )

        print("--- RUNNING RETRIEVAL HIT-RATE EVALUATION ---")
        hit_rate = await score_hit_rate(golden_set, ask_use_case)
        print(f"Resulting Hit-Rate: {hit_rate:.2%}")

        print("--- RUNNING REFUSAL CORRECTNESS EVALUATION ---")
        refusal_rate = await score_refusal_correctness(golden_set, ask_use_case)
        print(f"Resulting Refusal Correctness: {refusal_rate:.2%}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
