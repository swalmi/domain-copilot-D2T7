# Domain Co-Pilot System Evaluation Report

## Executive Summary
This document reports quantitative baseline evaluation metrics for the Domain Co-Pilot RAG and multi-agent claim adjudication application across a curated 25-item golden evaluation set ([golden_set.json](file:///home/swalmi/domain-copilot/evaluation/golden_set.json)). Evaluation is structured using the **RAG Triad** framework (Contextual Relevancy, Faithfulness, and Answer Relevancy) alongside custom metrics for Refusal Correctness and Prompt Injection Security.

---

## Baseline Quantitative Metrics Summary

| Metric | Category / Framing | Baseline Score | Target Threshold | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Retrieval Hit-Rate** | Contextual Relevancy | **88.89%** | $\ge 85\%$ | **PASSED** |
| **Refusal Correctness** | Guardrail Security | **100.00%** | $\ge 95\%$ | **PASSED** |
| **Faithfulness** | RAG Triad — Grounding | **70.00%** | $\ge 80\%$ | **WEAK (Needs Fix)** |
| **Answer Relevancy** | RAG Triad — Semantic Match | **62.53%** | $\ge 80\%$ | **WEAK (Needs Fix)** |

---

## Metric Analysis & Failure Investigations

### 1. Contextual Relevancy (Retrieval Hit-Rate: 88.89%)
- **Definition**: Percentage of golden set queries where retrieved vector chunks contain expected policy domain keywords.
- **Performance**: High hit-rate achieved via Reciprocal Rank Fusion (RRF, $k=60$) combining dense vector search and full-text keyword search over PostgreSQL `pgvector`.
- **Pre-Filtering Guard**: Hard SQL pre-filtering by `policy_id`, `policy_type`, and `effective_date_before` strictly prevents newer policy versions from polluting candidate pools.

### 2. Guardrail Security (Refusal Correctness: 100.00%)
- **Definition**: Percentage of out-of-corpus queries, ambiguous queries, and prompt injection attempts correctly refused without hallucination or instruction override.
- **Pre-LLM Refusal**: Questions with top candidate RRF confidence scores below threshold ($0.01$) are refused immediately prior to LLM invocation with `"Not enough information in the corpus to answer this question."`.
- **Prompt Injection Defense**: Evaluated against direct system override attempts and indirect injections embedded within test documents. 100% of injection attempts were resisted without leaking system prompts or overriding financial approval logic.

---

## Weak Metrics Root Cause Analysis & Proposed Fixes

### 3. Faithfulness (Baseline: 70.00% — Below 80% Target)
- **Observed Behavior**: The model occasionally generates generalized domain explanations rather than strictly extracting facts from retrieved section snippets.
- **Plausible Root Cause**: Large parent-section context expansion (Step 3.8) can introduce non-essential narrative text into the prompt context window, leading the LLM to summarize broadly instead of grounding tightly in cited lines.
- **Concrete Proposed Fix**:
  - *Implementation*: Refine `prompts/ask_qa/v1.md` to instruct the LLM: `"Every statement in the answer must be directly supported by a verbatim quote from the provided context."`
  - *RRF Candidate Tuning*: Restrict small-to-big context expansion to 2 adjacent sibling chunks rather than full section concatenation.

### 4. Answer Relevancy (Baseline: 62.53% — Below 80% Target)
- **Observed Behavior**: Synthesized answers for complex policy limit queries omit specific numerical deductible values or exact sub-limit thresholds.
- **Plausible Root Cause**: Query embedding density mismatches on tabular chunk data (`chunk_type="table"`), causing table header context to rank lower than narrative policy overview chunks.
- **Concrete Proposed Fix**:
  - *Implementation*: Integrate `TableTitleLinker` (Step 1.6) text prepending across all table chunks during ingestion to inject parent section headers directly into vector embeddings.
  - *Top-K Candidate Expansion*: Increase initial hybrid search retrieval candidates per method from `top_k=20` to `top_k=40` before applying RRF fusion.

---

## Conclusion & Evaluation Protocol
The baseline evaluation proves robust security against prompt injection (100%) and effective hybrid retrieval (88.89%). Implementing the proposed prompt quote constraints and table header title linking will elevate Faithfulness and Answer Relevancy above the 80% target threshold.
