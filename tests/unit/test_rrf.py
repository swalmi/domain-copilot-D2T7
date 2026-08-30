import uuid
from datetime import date

from src.application.retrieval.hybrid_search import reciprocal_rank_fusion
from src.domain.entities.policy import CitedChunk


def make_chunk(title: str, text: str) -> CitedChunk:
    """Helper to create a CitedChunk test instance with deterministic properties."""
    return CitedChunk(
        chunk_id=uuid.uuid5(uuid.NAMESPACE_DNS, title),
        text=text,
        source_document="policy_doc.pdf",
        section=title,
        page=1,
        policy_id="POL-TEST",
        version="1.0",
        effective_date=date(2026, 1, 1),
        chunk_type="narrative",
        policy_type="home",
    )


def test_reciprocal_rank_fusion_manual_scoring() -> None:
    """Verify reciprocal rank fusion computes correct 1/(rank+k) scores and deduplicates chunks."""
    chunk_a = make_chunk("Chunk A", "Content A")
    chunk_b = make_chunk("Chunk B", "Content B")
    chunk_c = make_chunk("Chunk C", "Content C")
    chunk_d = make_chunk("Chunk D", "Content D")

    # List 1: [A (rank 1), B (rank 2), C (rank 3)]
    # List 2: [B (rank 1), D (rank 2), A (rank 3)]
    list_1 = [chunk_a, chunk_b, chunk_c]
    list_2 = [chunk_b, chunk_d, chunk_a]

    # Manual RRF scoring with k=60:
    # A: 1/(1+60) + 1/(3+60) = 1/61 + 1/63 = 0.0163934426 + 0.0158730158 = 0.0322664584
    # B: 1/(2+60) + 1/(1+60) = 1/62 + 1/61 = 0.0161290322 + 0.0163934426 = 0.0325224748
    # C: 1/(3+60) + 0 = 1/63 = 0.0158730158
    # D: 0 + 1/(2+60) = 1/62 = 0.0161290322
    # Expected order descending: B > A > D > C

    fused = reciprocal_rank_fusion([list_1, list_2], k=60)

    assert len(fused) == 4
    assert fused[0].chunk_id == chunk_b.chunk_id
    assert fused[1].chunk_id == chunk_a.chunk_id
    assert fused[2].chunk_id == chunk_d.chunk_id
    assert fused[3].chunk_id == chunk_c.chunk_id


def test_reciprocal_rank_fusion_single_list() -> None:
    """Verify RRF preserves order and deduplicates when a single list is provided."""
    chunk_a = make_chunk("Chunk A", "Content A")
    chunk_b = make_chunk("Chunk B", "Content B")

    fused = reciprocal_rank_fusion([[chunk_a, chunk_b, chunk_a]], k=60)

    assert len(fused) == 2
    assert fused[0].chunk_id == chunk_a.chunk_id
    assert fused[1].chunk_id == chunk_b.chunk_id
