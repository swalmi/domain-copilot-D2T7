import hashlib
import os
import threading
import time
from collections.abc import Callable
from datetime import date
from typing import Any, Literal


def compute_document_hash(raw_bytes: bytes) -> str:
    """Compute the SHA-256 hex digest of raw document bytes for idempotent ingestion."""
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_chunk_hash(text: str) -> str:
    """Compute the SHA-256 hex digest of a chunk's text content for idempotent deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _find_section_title(chunk: dict, id_to_chunk: dict[str, dict]) -> str | None:
    """Walk up parent_id hierarchy to locate the nearest preceding Title text."""
    curr_id = chunk.get("parent_id")
    visited = set()
    while curr_id and curr_id in id_to_chunk and curr_id not in visited:
        visited.add(curr_id)
        parent_chunk = id_to_chunk[curr_id]
        if parent_chunk.get("category") == "Title":
            return parent_chunk.get("text")
        curr_id = parent_chunk.get("parent_id")

    if chunk.get("parent_id") and chunk.get("parent_id") in id_to_chunk:
        return id_to_chunk[chunk["parent_id"]].get("text")

    return None


def load_and_chunk(
    file_path: str,
    policy_id: str,
    policy_type: Literal["auto", "home", "liability"],
    version: str,
    effective_date: date,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict]:
    """Load a PDF or DOCX file using UnstructuredLoader and return metadata-enriched chunk dicts.

    :param on_progress: Optional callback invoked with a dict describing internal
        progress **while the (potentially slow) partition runs**: a 1-second
        heartbeat during extraction, then per-element enrichment progress with
        the element/chunk id so a live terminal never waits on a silent phase.
        Runs in worker threads; keep the callback short and thread-safe.
    """
    from langchain_unstructured import UnstructuredLoader

    strategy = os.getenv("UNSTRUCTURED_PDF_STRATEGY", "hi_res")
    loader = UnstructuredLoader(
        file_path=file_path,
        chunking_strategy="by_title",
        strategy=strategy,
        max_characters=1200,
        new_after_n_chars=1000,
        combine_text_under_n_chars=200,
        multipage_sections=True,
        overlap=100,
        overlap_all=False,
    )

    def report(info: dict[str, Any]) -> None:
        if on_progress is not None:
            on_progress(info)

    report(
        {
            "stage": "partition_started",
            "strategy": strategy,
            "detail": f"Starting text/layout extraction (unstructured {strategy})…",
        }
    )

    start = time.monotonic()
    done = threading.Event()

    def heartbeat() -> None:
        while not done.is_set():
            time.sleep(1.0)
            if done.is_set():
                break
            elapsed = time.monotonic() - start
            report(
                {
                    "stage": "partitioning",
                    "elapsed_s": round(elapsed, 1),
                    "detail": f"Unstructured {strategy} partition still running… (elapsed {elapsed:.1f}s)",
                }
            )

    watcher = threading.Thread(target=heartbeat, daemon=True)
    watcher.start()
    try:
        documents = loader.load()
    finally:
        done.set()
    watcher.join(timeout=2.0)

    report(
        {
            "stage": "partition_completed",
            "elements": len(documents),
            "elapsed_s": round(time.monotonic() - start, 1),
            "detail": f"Partitioned {len(documents)} elements",
        }
    )

    raw_chunks: list[dict] = []
    for doc in documents:
        metadata = doc.metadata or {}
        raw_chunks.append(
            {
                "text": doc.page_content,
                "category": str(metadata.get("category", "")),
                "element_id": str(metadata.get("element_id", "")),
                "parent_id": metadata.get("parent_id"),
                "page_number": metadata.get("page_number"),
            }
        )

    id_to_chunk = {
        c["element_id"]: c for c in raw_chunks if c.get("element_id")
    }

    chunks: list[dict] = []
    n = len(raw_chunks)
    for idx, chunk in enumerate(raw_chunks, start=1):
        category = chunk["category"]
        chunk_type = "table" if category == "Table" else "narrative"
        section = _find_section_title(chunk, id_to_chunk)

        report(
            {
                "stage": "enriching",
                "index": idx,
                "total": n,
                "element_id": chunk.get("element_id", ""),
                "category": category,
                "detail": f"Enriching element {idx}/{n} (id={chunk.get('element_id', '')}, category={category})",
            }
        )

        enriched_chunk = {
            "text": chunk["text"],
            "category": category,
            "element_id": chunk["element_id"],
            "parent_id": chunk["parent_id"],
            "page_number": chunk["page_number"],
            "policy_id": policy_id,
            "policy_type": policy_type,
            "version": version,
            "effective_date": effective_date,
            "chunk_type": chunk_type,
            "section": section,
        }
        chunks.append(enriched_chunk)

    return chunks


def inspect_raw_unstructured_elements(file_path: str) -> list:
    """Temporarily load raw Unstructured elements before chunking for debugging.

    This helper tries to instantiate `UnstructuredLoader` with chunking disabled
    so you can inspect the raw elements returned by the underlying extractor.
    It is intended for temporary local debugging only and should not be used
    in production code.
    """
    from langchain_unstructured import UnstructuredLoader

    loader_variants = [
        {"chunking_strategy": None, "strategy": "hi_res"},
        {"chunking_strategy": "none", "strategy": "hi_res"},
        {"strategy": "hi_res"},
    ]

    for params in loader_variants:
        try:
            loader = UnstructuredLoader(file_path=file_path, **params)
            elements = loader.load()
            return elements
        except TypeError:
            continue

    loader = UnstructuredLoader(
        file_path=file_path,
        chunking_strategy="by_title",
        strategy="hi_res",
        max_characters=1200,
        new_after_n_chars=1000,
        combine_text_under_n_chars=200,
        multipage_sections=True,
        overlap=100,
        overlap_all=False,
    )

    return loader.load()
