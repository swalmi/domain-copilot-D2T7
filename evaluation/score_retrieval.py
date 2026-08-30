"""Retrieval hit-rate evaluation metric scoring script."""

import logging

from src.application.use_cases.ask_question import AskQuestionUseCase

logger = logging.getLogger(__name__)


async def score_hit_rate(
    golden_set: list[dict], ask_use_case: AskQuestionUseCase
) -> float:
    """Compute retrieval hit-rate across golden set items expecting policy citations."""
    relevant_items = [
        item
        for item in golden_set
        if item.get("category") not in ["out_of_corpus", "prompt_injection"]
        and item.get("expected_chunk_keywords")
    ]

    if not relevant_items:
        return 1.0

    hits = 0
    for item in relevant_items:
        question = item["question"]
        expected_keywords = [kw.lower() for kw in item["expected_chunk_keywords"]]

        res = await ask_use_case.execute(query=question, filters={})
        citations = res.get("citations", [])

        # Check if any citation text contains at least one expected keyword
        hit_found = False
        for citation in citations:
            snippet = (citation.get("text") or "").lower()
            if any(kw in snippet for kw in expected_keywords):
                hit_found = True
                break

        if hit_found:
            hits += 1

    hit_rate = hits / len(relevant_items)
    logger.info(f"Retrieval Hit-Rate: {hits}/{len(relevant_items)} ({hit_rate:.2%})")
    return hit_rate
