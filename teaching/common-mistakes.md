# Common Trainee Mistakes — one page

Five misconceptions we predict, with the correction you should give **immediately**.

---

### 1. “If the LLM returned it, it must be in the policy.”
**Wrong because:** fluency ≠ grounding; the model fills gaps from pretraining.
**Correct it:** Require a `chunk_id` on every factual claim. If citation list is empty, the answer is a refusal — teach them to read `refused` in the SSE `done` event and `min_confidence_score` in config.

---

### 2. “Let the model calculate the payout — it’s good at math.”
**Wrong because:** arithmetic hallucinations are silent and expensive (D2 risk).
**Correct it:** Show `ExclusionAnalyst` / payout code path: deductible and limit applied in Python. LLM outputs a *recommendation string*; `calculated_payout` comes from deterministic code. Ask: “where is `4500 - 500` written in source?” — if they cannot point to a file, they fail the design review.

---

### 3. “Approval is a UI button; the backend will sort it out.”
**Wrong because:** hiding buttons is not authorisation (FR-8).
**Correct it:** Have them `curl` approve as a client → expect 403. Then try corp `DELETE` on `pending_approval` → expect 409. Server-side status machine is the control; UI is convenience.

---

### 4. “More chunks in the prompt = better answers.”
**Wrong because:** noise dilutes attention; 3.7GB host OOMs on unbounded context; faithfulness drops.
**Correct it:** Point at `AskQuestionUseCase.MAX_CONTEXT_CHARS` and parent-expansion limits. Exercise: double context, watch groundedness/latency — not always better.

---

### 5. “If the demo works, evaluation is optional paperwork.”
**Wrong because:** FR-3 is the separator between shipped RAG and demoed RAG; refusal correctness only shows up on adversarial sets.
**Correct it:** Run `evaluation/run_harness.py` on day one. Record a *bad* number publicly (e.g. low hit-rate on table chunks) and drive a fix (table title linker). Teach candour: a documented failure beats a silent pass.

---

### Bonus red flag (lab)
Trainee says: “I’ll just prompt the model to always be helpful and never refuse.”  
**Stop them.** Unbounded helpfulness is OWASP LLM *excessive agency* + hallucination. Refusal is a required product behaviour with its own metric.
