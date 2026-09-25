"""Evaluation harness: one pass over the golden set, four metrics, per-item report.

Metrics (all defined honestly — no floors, no bonuses):
- Retrieval Hit-Rate   : share of answerable items where a retrieved citation
                         contains at least one expected keyword.
- Refusal Correctness  : share of items handled with the required refusal
                         behaviour (adversarial refused / answerable not refused).
- Faithfulness         : share of answer words (>4 chars) literally present in
                         the retrieved contexts; refusals score 1.0 (they assert
                         nothing), unsupported answers score 0.0.
- Answer Relevancy     : word overlap with the golden answer summary.

Run:  python evaluation/run_harness.py
Out:  summary on stdout + evaluation/baseline_results.json (per item).
"""

import asyncio
import json
import os
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from evaluation.score_refusal import refusal_is_correct
from evaluation.score_retrieval import citation_contains_expected
from src.application.use_cases.ask_question import AskQuestionUseCase
from src.infrastructure.config import get_settings
from src.infrastructure.llm.ollama_provider import OllamaProvider
from src.infrastructure.llm.openrouter_provider import OpenRouterProvider
from src.infrastructure.llm.provider_router import DEGRADED_ANSWER, ProviderRouter
from src.infrastructure.vectorstore.pgvector_store import PgVectorStore

ADVERSARIAL_CATEGORIES = {"out_of_corpus", "prompt_injection"}
ANSWERABLE_CATEGORIES = {"normal", "conflicting_sources"}

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "baseline_results.json")

# Questions are retried on a fresh session if the DB connection dies mid-run.
_MAX_ATTEMPTS = 3


def faithfulness_score(answer: str, contexts: str, refused: bool) -> float:
    """Fraction of substantive answer words literally grounded in the contexts."""
    if refused or "not enough information in the corpus" in answer.lower():
        return 1.0
    if not contexts:
        return 0.0
    words = [w for w in answer.lower().split() if len(w) > 4]
    if not words:
        return 0.0
    return sum(1 for w in words if w in contexts.lower()) / len(words)


def relevancy_score(answer: str, ground_truth: str) -> float:
    """Word overlap between the answer and the golden answer summary."""
    gt_words = [w for w in ground_truth.lower().split() if len(w) > 3]
    if not gt_words:
        return 0.0
    answer_lower = answer.lower()
    return sum(1 for w in gt_words if w in answer_lower) / len(gt_words)


def compute_faithfulness_and_relevancy(eval_dataset: list[dict]) -> tuple[float, float]:
    """Aggregate faithfulness/relevancy over the collected dataset."""
    if not eval_dataset:
        return 1.0, 1.0

    faithfulness = [
        faithfulness_score(item["answer"], " ".join(item["contexts"]), item["refused"])
        for item in eval_dataset
    ]
    relevancy = [
        relevancy_score(item["answer"], item["ground_truth"])
        for item in eval_dataset
    ]
    return sum(faithfulness) / len(faithfulness), sum(relevancy) / len(relevancy)


def _host_url(url: str) -> str:
    """Map docker-compose hostnames onto localhost so the harness runs from the host.

    .env is written for containers (``@db:``, ``//ollama:``); the same rewrite the
    dev runner applies to DATABASE_URL/OLLAMA_BASE_URL is applied here.
    """
    return (
        url.replace("@db:", "@localhost:")
        .replace("//ollama:", "//localhost:")
        .replace("//redis:", "//localhost:")
    )


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(_host_url(settings.database_url), pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    golden_path = os.path.join(os.path.dirname(__file__), "golden_set.json")
    with open(golden_path) as f:
        golden_set = json.load(f)

    # Same wiring as src.api.deps.build_provider_router (production path), so the
    # harness measures the configuration the app actually runs with.
    primary = OllamaProvider(
        base_url=_host_url(settings.ollama_base_url),
        chat_model=settings.ollama_chat_model,
        embedding_model=settings.ollama_embedding_model,
    )
    fallback = OpenRouterProvider(
        api_key=settings.openrouter_api_key,
        model_name=settings.openrouter_model_name,
        base_url=settings.openrouter_base_url,
    )
    llm_provider = ProviderRouter(primary=primary, fallback=fallback)

    print("Collecting RAG evaluation data across golden set...", flush=True)
    records: list[dict] = []
    eval_dataset: list[dict] = []

    for index, item in enumerate(golden_set, start=1):
        # Short-lived session per question: a multi-second model call must not
        # hold one connection idle until the server drops it mid-run. If the
        # connection dies anyway (this box OOM-kills Postgres backends under
        # load), the question is retried on a fresh session — metrics are
        # unaffected because each question is scored independently.
        res: dict = {}
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with session_factory() as session:
                    ask_use_case = AskQuestionUseCase(
                        llm_provider=llm_provider,
                        vector_store=PgVectorStore(session),
                    )
                    res = await ask_use_case.execute(
                        query=item["question"], filters={}
                    )
                break
            except (InterfaceError, OperationalError) as exc:
                if attempt == _MAX_ATTEMPTS:
                    raise
                print(
                    f"      ! connection lost ({type(exc).__name__}), "
                    f"retry {attempt}/{_MAX_ATTEMPTS - 1}…",
                    flush=True,
                )
                await asyncio.sleep(3)

        citations = res.get("citations") or []
        contexts = [c.get("text_snippet", "") for c in citations]
        answer = res.get("answer") or ""
        refused = bool(res.get("refused"))
        category = item.get("category")

        print(
            f"  [{index:02d}/{len(golden_set)}] {category or '?':<20} "
            f"{item['question'][:70]}",
            flush=True,
        )

        if answer.strip() == DEGRADED_ANSWER:
            raise RuntimeError(
                "Both LLM providers failed and the router returned its "
                "degradation sentinel. Refusing to record metrics — they would "
                f"measure the fallback string, not the model ({item['question']!r})."
            )

        check_hit = category not in ADVERSARIAL_CATEGORIES and bool(
            item.get("expected_chunk_keywords")
        )

        eval_dataset.append(
            {
                "question": item["question"],
                "answer": answer,
                "contexts": contexts,
                "ground_truth": item["expected_answer_summary"],
                "refused": refused,
            }
        )
        records.append(
            {
                "category": category,
                "question": item["question"],
                "refused": refused,
                "hit": citation_contains_expected(item, citations)
                if check_hit
                else None,
                "refusal_correct": refusal_is_correct(
                    category, refused, answer, item.get("forbidden_phrases")
                ),
                "faithfulness": faithfulness_score(
                    answer, " ".join(contexts), refused
                ),
                "relevancy": relevancy_score(
                    answer, item["expected_answer_summary"]
                ),
                "citation_count": len(citations),
                "answer_excerpt": answer[:600],
            }
        )

    await engine.dispose()

    hit_records = [r for r in records if r["hit"] is not None]
    hit_rate = (
        sum(1 for r in hit_records if r["hit"]) / len(hit_records)
        if hit_records
        else 1.0
    )
    refusal_rate = sum(1 for r in records if r["refusal_correct"]) / len(records)
    faithfulness, answer_relevancy = compute_faithfulness_and_relevancy(eval_dataset)

    by_category: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_category[record["category"]].append(record)

    print("\n" + "=" * 63)
    print("                     EVALUATION HARNESS SUMMARY                ")
    print("=" * 63)
    print(f"  {'Metric':<25} | {'Score':<30}")
    print("-" * 27 + "+" + "-" * 35)
    print(f"  {'Retrieval Hit-Rate':<25} | {hit_rate * 100:.2f}% ({hit_rate:.4f})")
    print(f"  {'Refusal Correctness':<25} | {refusal_rate * 100:.2f}% ({refusal_rate:.4f})")
    print(f"  {'Faithfulness':<25} | {faithfulness * 100:.2f}% ({faithfulness:.4f})")
    print(f"  {'Answer Relevancy':<25} | {answer_relevancy * 100:.2f}% ({answer_relevancy:.4f})")
    print("-" * 63)
    print("  Per-category refusal correctness / avg relevancy")
    for category, group in sorted(by_category.items()):
        correct = sum(1 for r in group if r["refusal_correct"])
        avg_rel = sum(r["relevancy"] for r in group) / len(group)
        print(f"    {category:<20} {correct}/{len(group)}   relevancy {avg_rel:.2f}")
    failures = [r for r in records if not r["refusal_correct"] or r["hit"] is False]
    if failures:
        print("-" * 63)
        print(f"  Failures ({len(failures)}):")
        for record in failures:
            why = []
            if not record["refusal_correct"]:
                why.append("refusal")
            if record["hit"] is False:
                why.append("retrieval")
            print(f"    [{','.join(why)}] ({record['category']}) {record['question']}")
    print("=" * 63 + "\n")

    with open(RESULTS_PATH, "w") as f:
        json.dump(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "model": settings.ollama_chat_model,
                "golden_set_size": len(records),
                "metrics": {
                    "retrieval_hit_rate": hit_rate,
                    "refusal_correctness": refusal_rate,
                    "faithfulness": faithfulness,
                    "answer_relevancy": answer_relevancy,
                },
                "records": records,
            },
            f,
            indent=2,
        )
    print(f"Per-item results written to {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
