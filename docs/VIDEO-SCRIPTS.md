# Video Scripts (recording aid — not a deliverable)

Two unlisted videos are required. These shot lists exist so the recording can be
done in one take each; the README's video table is where the final URLs go.

**House rules for both:** face and voice required, teach — do not read slides
aloud, show the real system (no slides of screenshots), keep edits to cuts only.

---

## 1. Product demo — 5–8 minutes

| # | Time | Screen | Say / show |
|---|---|---|---|
| 1 | 0:00–0:30 | Repo README | What insureAI is, the three principles: grounded (cites or refuses), the human holds the pen, everything observable. |
| 2 | 0:30–1:30 | Terminal → UI | `docker compose up -d && docker compose run --rm app python scripts/seed_corpus.py`, open `localhost:3000`, log in as corp. Mention 30-document / 150+ page corpus, synthetic/public only. |
| 3 | 1:30–2:40 | Ingestion page | Upload a PDF → live progress events (extract → chunk → embed → index), per-document status. Re-upload the same file → idempotent "already ingested". |
| 4 | 2:40–3:50 | Ask page | Corpus question → token streaming + citation chips → click one → exact chunk, page, policy version. Then an out-of-corpus question → **"Not enough information in the corpus"**. |
| 5 | 3:50–5:10 | Claims page | Submit a claim → HTTP 202 with `claim_id`, watch pipeline stages move live (Coverage Matcher → Exclusion Analyst → Adjudication Drafter) → `report_ready` with deterministic payout math. |
| 6 | 5:10–6:00 | Approvals page | As corp: open the queue → approve / reject / edit-and-approve → show the audit trail entry written for the decision. |
| 7 | 6:00–6:50 | Trace page | Paste the correlation id → step-by-step run: which agent, which tools, which chunks, tokens and cost for the run. |
| 8 | 6:50–7:40 | Terminal | Twist T7: `pause` → `resume` → `cancel`; replay the same `Idempotency-Key` curl twice → one claim, one job; `docker compose restart worker` mid-run → work redelivered. |
| 9 | 7:40–8:00 | SDD gap table | One honest sentence on what is deliberately not built and why. |

---

## 2. Teaching sample — 10 minutes

**Topic:** *RAG beyond the demo* (slice of `teaching/slides/rag-beyond-the-demo.md`).

| # | Time | Beat |
|---|---|---|
| 1 | 0:00–1:00 | Opening question to camera: "Your RAG demo answered confidently and was wrong. Where did it break?" — four candidate layers, we fix them one at a time. |
| 2 | 1:00–3:00 | **Grounding**: show a citation chip → chunk → source, then the refusal path and the confidence threshold. Point out that a refusal is a *correct* answer. |
| 3 | 3:00–5:00 | **Hybrid retrieval**: run the same query dense-only and hybrid; show RRF fusion and why the keyword leg exists (the `plainto_tsquery` AND-vs-OR lesson). |
| 4 | 5:00–7:00 | **Evaluation**: run `python evaluation/run_harness.py` live, read the numbers including the weak ones (faithfulness, the two retrieval misses, the injection failure) and interpret them. |
| 5 | 7:00–9:00 | **Security**: walk one indirect-injection golden item — retrieved document text tries to override policy — show what the system does today and what it should do. |
| 6 | 9:00–10:00 | Close with the five common trainee mistakes (`teaching/common-mistakes.md`) and assign lab task A from `teaching/lab-sheet.md`. |

**After recording:** paste both unlisted URLs into the README video table, then
open each in a private window to confirm it plays and the link is not public.
