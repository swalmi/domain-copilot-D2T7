# Learning Outcomes & Assessment Map

**Session:** RAG Beyond the Demo (90 min) · **Slides:** `slides/rag-beyond-the-demo.md` · **Lab:** `lab-sheet.md`

## Learning outcomes (measurable)

| LO | Statement | Bloom level | Evidence in session |
|---|---|---|---|
| LO1 | Explain why hybrid retrieval + RRF outperforms single-space search on policy corpora | Understand | Slides 7–8; oral Q |
| LO2 | Run a grounded answer and a correct refusal against the live system | Apply | Lab A, B |
| LO3 | Trace one claim through the multi-agent pipeline to `report_ready` | Apply | Lab C |
| LO4 | Enforce an approval gate including delete-lock and edit-on-approve | Apply/Analyze | Lab D |
| LO5 | Diagnose low groundedness using correlation_id + retrieval_log | Analyze | Lab E; stretch 3 |
| LO6 | Identify an indirect prompt-injection path and the control that stops it | Analyze/Evaluate | Slide 12; stretch 2 |
| LO7 | Reproduce a live hallucination and propose a specific pipeline fix | Analyze/Evaluate | Task B2; Slide 18; stretch 5 |
| LO8 | Use `claim_logs.json` to find a defect the API response hides | Analyze | Task C instructor note; stretch 6 |

## Assessment map

| Assessment item | LOs | Type | Weight |
|---|---|---|---|
| Lab tasks A, B1, C, D (checklist) | LO2–LO4 | Formative + summative | 45% |
| **Task B2** (reproduce the fabrication) | **LO7** | **Summative** | **20%** |
| Lab task E (trace/cost) | LO5, LO8 | Summative | 10% |
| Stretch challenge (any one) | LO6, LO7 (+ LO5) | Summative | 15% |
| Exit ticket (3 questions below) | LO1, LO6, LO7 | Formative | 10% |

### Exit ticket
1. In one sentence: when should the system refuse instead of answer?
2. Which layer computes `calculated_payout` — LLM or code? Why?
3. Name one sink you would check first if an adjuster says “the AI payout looks wrong.”
4. The system answered “$75,000” for a question about the Moon, and “$10,000” when you
   asked again. Name one change that would have prevented it.

## Mapping to product requirements

| LO | FR / requirement link |
|---|---|
| LO1 | FR-2 retrieval + fusion |
| LO2 | FR-2 citations + refusal |
| LO3 | FR-4 multi-agent + FR-5 orchestration |
| LO4 | FR-5 approval gate + human-in-the-loop principle |
| LO5 | FR-9 observability |
| LO6 | OWASP LLM Top 10 — prompt injection |
| LO7 | Confidence-gate design; `docs/EVALUATION.md` §4.2 |
| LO8 | FR-9 observability (`claim_logs.json`) |

## Timebox (90 min)

| Segment | Min |
|---|---|
| Cold-open demo | 5 |
| Slides 4–12 (retrieval + safety) | 27 |
| Slides 13–17 (agents + gate + obs) | 20 |
| Lab A, B1, C, D (parallel pairs) | 22 |
| **Task B2 + debrief** (the centrepiece) | 8 |
| Lab E + debrief | 5 |
| Exit ticket | 3 |
