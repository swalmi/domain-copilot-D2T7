from src.infrastructure.ingestion.document_loader import (
    compute_chunk_hash,
    compute_document_hash,
)


def test_compute_document_hash_deterministic() -> None:
    """Verify that same document bytes produce identical hashes and different bytes produce distinct hashes."""
    data_a = b"PDF document content payload binary stream 1"
    data_b = b"PDF document content payload binary stream 2"

    hash_a1 = compute_document_hash(data_a)
    hash_a2 = compute_document_hash(data_a)
    hash_b = compute_document_hash(data_b)

    assert hash_a1 == hash_a2
    assert hash_a1 != hash_b
    assert len(hash_a1) == 64


def test_compute_chunk_hash_deterministic() -> None:
    """Verify that same chunk text produces identical hashes and different text produces distinct hashes."""
    text_a = "Section VII: Limits of Liability - €500 deductible"
    text_b = "Section VIII: Exclusions and Claims Procedures"

    hash_a1 = compute_chunk_hash(text_a)
    hash_a2 = compute_chunk_hash(text_a)
    hash_b = compute_chunk_hash(text_b)

    assert hash_a1 == hash_a2
    assert hash_a1 != hash_b
    assert len(hash_a1) == 64
