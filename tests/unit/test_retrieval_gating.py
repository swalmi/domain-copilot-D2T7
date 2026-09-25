"""Tests for the calibrated refusal gate and the keyword leg.

The gate previously compared an RRF score against the literal 0.01 while the
maximum attainable score is 0.0328, so it could not fire. These tests pin the
bounded-scale arithmetic and both gate conditions.
"""

from datetime import date
from uuid import uuid4

import pytest

from src.application.retrieval.hybrid_search import (
    CANDIDATE_POOL,
    MAX_COSINE_DISTANCE,
    MAX_RRF_SCORE,
    RETRIEVAL_TOP_K,
    RRF_K,
    RetrievalConfidence,
    hybrid_search_with_confidence,
    reciprocal_rank_fusion_with_scores,
)
from src.infrastructure.vectorstore.pgvector_store import (
    KEYWORD_STOPWORDS,
    build_keyword_query,
    keyword_min_matches,
    keyword_terms,
    normalize_policy_identifiers,
)
from src.domain.entities.policy import CitedChunk


def _chunk(i: int = 0) -> CitedChunk:
    return CitedChunk(
        chunk_id=uuid4(),
        text=f"chunk {i} text about windstorm damage to the dwelling",
        source_document="ho3.txt",
        section="Section I",
        page=17 + i,
        policy_id="SHELTER-HO3",
        version="2007-01",
        effective_date=date(2007, 1, 1),
        chunk_type="narrative",
    )


class _Store:
    """Minimal vector store double with configurable leg results and distance."""

    def __init__(self, dense, keyword, distance):
        self._dense = dense
        self._keyword = keyword
        self._distance = distance

    async def search(self, query_embedding, filters, top_k):
        return self._dense

    async def keyword_search(self, query_text, filters, top_k):
        return self._keyword

    async def top_cosine_distance(self, query_embedding, filters):
        return self._distance


class _Embedder:
    async def embed(self, text):
        return [0.1, 0.2, 0.3]


def test_rrf_ratio_floor_is_above_the_structural_minimum():
    """RRF sees ranked lists, so a non-empty fusion can never score below 0.5.

    A floor under 0.5 would be dead code -- which is what the old absolute 0.01
    threshold effectively was.
    """
    for dense, keyword in (
        ([_chunk(0)], []),
        ([_chunk(i) for i in range(40)], []),
        ([_chunk(i) for i in range(40)], [_chunk(100 + i) for i in range(40)]),
    ):
        fused = reciprocal_rank_fusion_with_scores([dense, keyword], k=RRF_K)
        assert fused, "fusion unexpectedly empty"
        assert fused[0][1] / MAX_RRF_SCORE >= 0.5 - 1e-9


def test_max_rrf_score_is_bounded_by_the_k_parameter():
    """The gate must be scaled to the ceiling, which the old 0.01 ignored."""
    assert RRF_K == 60
    assert MAX_RRF_SCORE == pytest.approx(2 / 61, abs=1e-9)
    assert MAX_RRF_SCORE == pytest.approx(0.032787, abs=1e-6)
    # The same chunk ranked first in both legs attains the ceiling.
    shared = _chunk()
    fused = reciprocal_rank_fusion_with_scores([[shared], [shared]], k=RRF_K)
    assert fused[0][1] == pytest.approx(MAX_RRF_SCORE, abs=1e-6)


def test_old_literal_threshold_would_never_fire():
    """Guards the regression: 0.01 sits below every reachable score."""
    # The weakest score reachable inside a 40-wide pool is exactly 0.01,
    # so a "< 0.01" gate can only trip on results the pool cannot even return.
    assert 1 / (40 + RRF_K) == pytest.approx(0.01, abs=1e-12)
    weakest = reciprocal_rank_fusion_with_scores(
        [[_chunk(i) for i in range(40)], []], k=RRF_K
    )
    assert weakest[-1][1] >= 0.01
    # And the top hit of a full pool always clears the old threshold.
    assert weakest[0][1] > 0.01


def test_keyword_terms_drop_stopwords():
    terms = keyword_terms("Is the policy covered under the HO3?")
    assert "the" not in terms and "is" not in terms and "under" not in terms
    assert all(t not in KEYWORD_STOPWORDS for t in terms)
    # "HO3" is normalised to the corpus spelling "HO-3" so the identifier is
    # searchable at all; see test_normalize_policy_identifiers_*.
    assert "ho-3" in terms


def test_keyword_terms_keep_hyphenated_policy_ids_whole():
    """The corpus stores "HO-3" as lexemes 'ho' and '-3'.

    Splitting the token in Python yields "ho" + "3", but Postgres stores the
    numeric part as '-3', so a bare "3" matches nothing and the identifier
    cannot satisfy the minimum-overlap requirement.
    """
    assert "ho-3" in keyword_terms("Shelter HO-3 loss of use")
    assert "3" not in keyword_terms("Shelter HO-3 loss of use")
    assert "shelter" in keyword_terms("Shelter HO-3 loss of use")


def test_normalize_policy_identifiers_rescues_run_together_numbers():
    """Postgres parses "HO3" as the single lexeme 'ho3', absent from the corpus."""
    assert normalize_policy_identifiers("covered under HO3?") == "covered under HO-3?"
    assert normalize_policy_identifiers("Is fire damage covered under HO3?") == (
        "Is fire damage covered under HO-3?"
    )
    # Already-hyphenated and digit-only text is left alone.
    assert normalize_policy_identifiers("HO-3") == "HO-3"
    assert normalize_policy_identifiers("in 2007") == "in 2007"


def test_keyword_min_matches_requires_overlap():
    assert keyword_min_matches("windstorm damage to the dwelling") == 2
    assert keyword_min_matches("windstorm") == 1
    # A stopword-only question has no terms at all.
    assert keyword_min_matches("the of and") == 1


def test_build_keyword_query_falls_back_when_no_terms():
    assert build_keyword_query("the of and") is not None


@pytest.mark.asyncio
async def test_gate_passes_for_confident_retrieval():
    chunk = _chunk()
    store = _Store([chunk], [chunk], 0.20)
    _, conf = await hybrid_search_with_confidence(
        vector_store=store, embedder=_Embedder(), query="windstorm damage"
    )
    assert conf.is_confident is True
    assert conf.reason == "retrieval_confident"
    assert conf.rrf_ratio == pytest.approx(1.0, abs=1e-3)
    assert conf.top_cosine_distance == 0.20


@pytest.mark.asyncio
async def test_gate_fires_on_far_absolute_distance():
    """RRF is rank-based, so only cosine distance can catch a good-looking
    ranking of an irrelevant nearest neighbour."""
    chunk = _chunk()
    store = _Store([chunk], [chunk], 0.92)
    _, conf = await hybrid_search_with_confidence(
        vector_store=store, embedder=_Embedder(), query="lunar rover on the moon"
    )
    assert conf.is_confident is False
    assert conf.reason == "max_cosine_distance_exceeded"
    # The RRF score alone would have looked perfect.
    assert conf.rrf_ratio == pytest.approx(1.0, abs=1e-3)


@pytest.mark.asyncio
async def test_gate_fires_on_empty_retrieval():
    store = _Store([], [], None)
    results, conf = await hybrid_search_with_confidence(
        vector_store=store, embedder=_Embedder(), query="anything"
    )
    assert results == []
    assert conf.is_confident is False
    assert conf.reason == "no_results"


@pytest.mark.asyncio
async def test_low_rrf_ratio_alone_never_refuses():
    """Guards against re-introducing a ratio floor.

    A dense hit that is an exact corpus match (cosine distance 0.0) still
    scores ratio 0.5 when the lexical leg prefers other chunks. Requiring
    cross-leg agreement would refuse a correct answer, so the ratio is
    reported but never gates.
    """
    dense = [_chunk(i) for i in range(40)]
    keyword = [_chunk(100 + i) for i in range(40)]
    _, conf = await hybrid_search_with_confidence(
        vector_store=_Store(dense, keyword, 0.0),
        embedder=_Embedder(),
        query="windstorm damage",
    )
    assert conf.rrf_ratio == pytest.approx(0.5, abs=1e-3)
    assert conf.is_confident is True
    assert conf.reason == "retrieval_confident"

    # A perfect cross-leg agreement is reported as ratio 1.0.
    shared = _chunk()
    _, agree = await hybrid_search_with_confidence(
        vector_store=_Store([shared], [shared], 0.20),
        embedder=_Embedder(),
        query="windstorm damage",
    )
    assert agree.rrf_ratio == pytest.approx(1.0, abs=1e-3)


@pytest.mark.asyncio
async def test_gate_thresholds_are_configurable():
    chunk = _chunk()
    store = _Store([chunk], [chunk], 0.30)
    _, strict = await hybrid_search_with_confidence(
        vector_store=store,
        embedder=_Embedder(),
        query="q",
        max_cosine_distance=0.20,
    )
    assert strict.is_confident is False
    _, lax = await hybrid_search_with_confidence(
        vector_store=store,
        embedder=_Embedder(),
        query="q",
        max_cosine_distance=0.90,
    )
    assert lax.is_confident is True


def test_retrieval_top_k_keeps_the_lexical_leg_representative():
    """The fused list interleaves dual-leg and single-leg hits.

    Cutting at 5 used to drop the top lexical evidence entirely, so the keyword
    leg's best chunk ranked 7th and never reached the prompt.
    """
    assert RETRIEVAL_TOP_K >= 6
    assert RETRIEVAL_TOP_K <= CANDIDATE_POOL


def test_confidence_dataclass_defaults_are_sane():
    conf = RetrievalConfidence(
        top_rrf_score=0.03,
        max_rrf_score=MAX_RRF_SCORE,
        rrf_ratio=0.9,
        top_cosine_distance=None,
        is_confident=True,
        reason="retrieval_confident",
    )
    assert conf.top_cosine_distance is None
    assert MAX_COSINE_DISTANCE > 0
