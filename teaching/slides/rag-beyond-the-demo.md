# Teaching Slides — RAG Beyond the Demo (90-minute post-graduate session)

Format: 20 slides · topic: **grounded RAG + multi-agent adjudication with a human gate**
Audience: post-graduate trainees who have “demoed” RAG once.

---

## Slide 1 — Title
**RAG Beyond the Demo**
What breaks when you put retrieval-augmented generation in front of a real adjuster.
*insureAI reference implementation (D2 insurance claims).*

## Slide 2 — Learning outcomes
By the end you can:
1. Diagnose a low-groundedness answer with a trace.
2. Design hybrid retrieval + fusion for policy corpora.
3. Place an approval gate that cannot be bypassed by the model.
4. Measure refusal correctness on adversarial queries.

## Slide 3 — Demo recap (2 min cold open)
Live: ingest → ask with citation → refuse out-of-corpus.
**Prompt:** “What does our corpus say about lunar module insurance?”
**Expected:** “Not enough information in the corpus.”

## Slide 4 — Why demos lie
Demos optimise for *one pretty answer*. Production needs:
- Version/date-aware retrieval (wrong policy edition = wrong payout).
- Deterministic arithmetic (never LLM math for deductibles).
- Observability (who ran, which chunks, what it cost).
- A human who holds the pen.

## Slide 5 — Corpus reality check
Our seed corpus: ≥30 public/synthetic policy docs, 150+ pages.
Chunking decision (ADR-003): section-aware split with page metadata.
**Trainee exercise:** open `data/metadata.json` and count `policy_type` buckets.

## Slide 6 — Chunking is a product decision
| Strategy | When it wins | When it fails |
|---|---|---|
| Fixed tokens | Simple | Splits mid-clause |
| Section headings | Policy forms | Needs reliable headings |
| Parent expansion | Long coverage forms | Costs more context |

We use section-aware chunks + parent expansion at query time.

## Slide 7 — Hybrid retrieval anatomy
```
query → embed ──► dense (pgvector HNSW)
      └─► keyword (tsvector BM25)
              ↓
         RRF fusion (k=60)
              ↓
         parent expand → top-k context
```
RRF score: `Σ 1/(rank_i + 60)` — no score calibration across spaces.

## Slide 8 — Why RRF, not score blending
Dense cosine and BM25 are incomparable scales.
Blending needs tuned weights per corpus; RRF is rank-only and stable.
*Trade-off:* loses magnitude information — document it in ADR.

## Slide 9 — Version / date awareness (D2 risk)
Filter: `policy_id` + `effective_date_before=date_of_loss`.
Failure mode: claim for 2026 loss matched to a 2018 form without endorsement check.
**Live check:** `retrieval_log.json` → `filters_applied`.

## Slide 10 — Citations are contracts, not decorations
`CitedChunk`: `chunk_id`, `policy_id`, `version`, `effective_date`, `page`, `section`,
`chunk_type`, `text`. The `/ask` SSE payload exposes the snippet as **`text_snippet`**.

Two honest caveats, both measured:
- `section` is frequently a **page fallback** (`"page 9"`), not a heading — PDFs without a
  detectable heading structure get nothing better.
- Hit-rate is scored against golden **keywords**, so a correct paraphrase scores zero.
  One of our two "failures" is a correct ISO answer that the golden set marks wrong.

**A citation is a claim about evidence. Verify it points at the sentence you rely on.**

## Slide 11 — Refusal is a feature
Gate on best **dense cosine distance** (`max_cosine_distance = 0.35`), not on an RRF score.
RRF is rank-based, so every non-empty fusion scores ≥ `1/61 ≈ 0.0164` — a 0.01 floor can
never fire. Absolute distance actually discriminates.
Refuse **before** generation: saves tokens, prevents hallucination.

**And it is not enough.** Measured: `out_of_corpus` scores **0/2**.
> *"…payout limit for a lunar rover on the Moon?"* → *"is $75,000."* — no refusal.

An in-vocabulary nonsense question ("policy", "payout limit", "damage") still clears a
topical-similarity gate. See `docs/EVALUATION.md` §4.2.

## Slide 12 — Prompt injection in *indirect* form
Attacker cannot talk to the model — they edit an uploaded policy PDF.
Defence layers:
1. Tool allow-lists per agent (no free shell).
2. Instruction vs retrieved-content separation in prompts.
3. Evaluation cases with category `prompt_injection` (3 in golden set, 3/3 pass).

**Measured honestly:** the 2 direct injections were refused *before* the LLM ran.
The 1 indirect case was **not** refused — it was marked correct only because the answer
avoided three literal `forbidden_phrases`. The tool allow-list is the control actually
holding, and its check **fails open** for agents that declare no tools.

## Slide 13 — Multi-agent pipeline (D2)
```
Claim → CoverageMatcher → ExclusionAnalyst → AdjudicationDrafter
              ↑ tools: search_policies
              ↑ tools: calculate_payout (deterministic code)
              ↑ tools: draft_decision (writes gated until approve)
```
Typed contracts: `CoverageMatchResult`, `ExclusionAnalysisResult`, `AdjudicationDraft`.

## Slide 14 — Deterministic money
`calculated_payout` computed in Python from deductible + limit + exclusions.
LLM only *recommends*; it never does arithmetic.
**Anti-pattern:** asking GPT “what is 4500 − 500?”

## Slide 15 — Orchestration controls (FR-5)
- Per-step timeout + 1 retry with backoff
- Circuit breaker on active claim IDs
- Graceful degradation → plain RAG deny draft
- Pause/resume via Redis pub/sub

## Slide 16 — The human gate
Status machine:
`report_ready → pending_approval → approved | rejected`
Client submits; corp decides; edit-with-comment supported.
Corp **cannot delete** undecided claims (409) — audit trail preserved.

## Slide 17 — Observability you can teach
| Sink | Question it answers |
|---|---|
| `system_logs.txt` | What happened, when, under which correlation_id? |
| `retrieval_log.json` | Which chunks, what RRF math, what agent saw? |
| `claim_logs.json` | Full adjudication record for one claim |
| `token_usage.json` | Tokens + estimated cost per call |
| `/runs/{id}` | Ordered trace events |

## Slide 18 — Evaluation that includes the bad numbers
Harness: `evaluation/run_harness.py` · golden set 25 Q/A (7 adversarial)
Committed run: `llama3.2:1b`, 17 min for 25 cases.

| Metric | Score |
|---|---|
| Retrieval hit-rate | **90 %** (18/20) |
| Refusal correctness | **92 %** (23/25) |
| Faithfulness (lexical) | 66 % — *not a quality score* |
| Answer relevancy (lexical) | 30 % — *not a quality score* |

**Both lexical metrics are word-overlap heuristics.** Faithfulness returns **1.0 for any
refusal**, and counts a word as "grounded" if it appears *anywhere* in 6 chunks of context.
Never gate CI on them.

**The headline failure:** `out_of_corpus` **0/2**, and the fabricated dollar figures
*differ between runs* ($10,000 then $75,000) — so it is generation, not a bad chunk.
Full analysis: `docs/EVALUATION.md`.

## Slide 19 — Lab preview (hands-on, 40 min)
See `teaching/lab-sheet.md`.
Stretch: break the gate, inject into a PDF, add a metric.

## Slide 20 — Takeaways & further reading
1. Ground or refuse — never improvise.
2. Money and eligibility live in code, not prompts.
3. The approval gate is a product surface, not a checkbox.
4. If you cannot replay it, you cannot teach it.

**Repo:** see README · **ADRs:** `docs/adr/`
