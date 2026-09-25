"""Retrieval hit-rate evaluation metric scoring script."""

import logging

from src.application.use_cases.ask_question import AskQuestionUseCase

logger = logging.getLogger(__name__)


def citation_contains_expected(item: dict, citations: list[dict]) -> bool:
    """True when at least one retrieved citation carries an expected keyword."""
    expected_keywords = [kw.lower() for kw in item.get("expected_chunk_keywords") or []]
    if not expected_keywords:
        return False

    for citation in citations:
        snippet = (citation.get("text_snippet") or "").lower()
        if any(kw in snippet for kw in expected_keywords):
            return True
    return False


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
        res = await ask_use_case.execute(query=item["question"], filters={})
        if citation_contains_expected(item, res.get("citations", [])):
            hits += 1

    hit_rate = hits / len(relevant_items)
    logger.info(f"Retrieval Hit-Rate: {hits}/{len(relevant_items)} ({hit_rate:.2%})")
    return hit_rate
