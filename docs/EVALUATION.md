# Evaluation Report

This document explains the evaluation harness, golden set, metrics, and instructions to reproduce evaluation numbers.

## Evaluation Approach
- Dataset: hybrid of public insurance/regulatory PDFs + synthetic `.txt` policies under `data/` (corpus manifest: `data/metadata.json`, 30 documents; page total across source PDFs ≥150). Golden set: `evaluation/golden_set.json`.
- Evaluations run by `evaluation/run_eval_scripts.py` / `evaluation/score_retrieval.py` (retrieval hit-rate, groundedness, refusal correctness).

## Golden set composition (actual)

| Category | Count | Notes |
|---|---:|---|
| `normal` | 18 | Grounded policy Q/A with expected chunk keywords |
| `prompt_injection` | 3 | ≥3 required by OWASP LLM control |
| `out_of_corpus` | 2 | Must refuse with exact refusal string |
| `ambiguous` | 1 | Under-specified; expected escalate/refuse behaviour |
| `conflicting_sources` | 1 | Conflicting policy versions; version/date-aware retrieval |
| **Total** | **25** | Adversarial (non-normal) = **7** ≥ 5 required |

## Key Metrics
- Retrieval Hit Rate: fraction of queries where at least one golden chunk is present in top-K retrieved chunks.
- Groundedness: fraction of answers where every factual claim has a citation to a retrieved chunk.
- Refusal Correctness: fraction of adversarial/out-of-corpus queries correctly refused.

## How to run the evaluation harness
1. Seed corpus: `python scripts/seed_corpus.py` (or upload via UI) after `docker compose up -d db redis ollama`.
2. Start services (backend + Ollama embeddings).
3. Run evaluation:
```bash
python evaluation/run_eval_scripts.py --golden evaluation/golden_set.json --topk 10
```

## Baseline numbers (recorded)

Re-run the harness after any chunking/retrieval change and update this table with real runs (including weak numbers).

| Metric | Baseline | Interpretation |
|---|---|---|
| Retrieval Hit Rate (top-10) | *record from harness run* | Dense+keyword RRF; table chunks historically weak → `TableTitleLinker` mitigation |
| Groundedness | *record from harness run* | Citations required on every non-refusal answer |
| Refusal Correctness | *target ≥0.8 on OOC + ambiguous* | Exact refusal string when evidence score below threshold |

## Recommendations
- Increase chunk overlap and use reranking (BM25 + dense) for better ground-truth recall.
- Add automated nightly evaluation runs and publish daily dashboards.
- **Plausible Root Cause**: Query embedding density mismatches on tabular chunk data (`chunk_type="table"`), causing table header context to rank lower than narrative policy overview chunks.
- **Concrete Proposed Fix**:
  - *Implementation*: `TableTitleLinker` prepends parent section titles to table chunks during ingestion.
  - *Top-K Candidate Expansion*: Increase initial hybrid search candidates per method from `top_k=20` to `top_k=40` before RRF fusion.

---

## Conclusion & Evaluation Protocol
The harness is part of the non-negotiable deliverable (FR-3). Template metrics above must be replaced with actual numbers from `python evaluation/run_eval_scripts.py` before submission — including bad results with an interpretation, not only successes.
